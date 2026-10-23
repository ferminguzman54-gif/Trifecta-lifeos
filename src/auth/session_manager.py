"""
Gestión de sesión móvil (Login, Sign-up, Logout) y persistencia del refresh_token
en cookies del navegador mediante extra-streamlit-components (CookieManager).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict, Optional, Tuple

import extra_streamlit_components as stx
import streamlit as st

from .supabase_client import get_supabase_client
from ..config.settings import (
    COOKIE_EXPIRY_DAYS,
    COOKIE_NAME,
    DEFAULT_FINANCE_CATEGORIES,
    is_supabase_configured,
)


@st.cache_resource
def _get_rotation_grace_cache() -> Dict[str, Tuple[float, Any]]:
    """
    Caché en memoria de corta duración (60s) para evitar condiciones de carrera
    en la rotación de refresh_token cuando Streamlit ejecuta reruns consecutivos
    mientras el componente CookieManager sincroniza con el navegador móvil.
    """
    return {}


def get_cookie_manager() -> stx.CookieManager:
    """Inicializa y retorna la instancia única de CookieManager para la vista actual."""
    return stx.CookieManager(key="trifecta_cookie_manager")


def init_session_state() -> None:
    """Inicializa las llaves por defecto en st.session_state."""
    defaults = {
        "authenticated": False,
        "user": None,
        "user_profile": None,
        "access_token": None,
        "refresh_token": None,
        "active_pillar": "hub",
        "_logout_just_triggered": False,
    }
    for key, default_val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


def get_current_user_id() -> Optional[str]:
    """Retorna el UUID del usuario autenticado o None."""
    user = st.session_state.get("user")
    if user is not None and hasattr(user, "id"):
        return str(user.id)
    if isinstance(user, dict) and "id" in user:
        return str(user["id"])
    return None


def _ensure_user_profile_and_defaults(
    user_id: str,
    email: str,
    full_name: Optional[str] = None,
    preferred_currency: str = "MXN",
    weight_unit: str = "kg",
) -> Dict[str, Any]:
    """
    Carga el perfil del usuario desde `public.profiles`. Si por algún motivo
    el trigger SQL aún no lo creó, lo inserta junto con las categorías base.
    """
    client = get_supabase_client()
    display_name = (full_name or email.split("@")[0] or "Usuario Trifecta").strip()

    try:
        res = client.table("profiles").select("*").eq("id", user_id).execute()
        if res.data and len(res.data) > 0:
            profile = res.data[0]
            if full_name and profile.get("full_name") in ("Usuario Trifecta", email.split("@")[0]):
                upd = (
                    client.table("profiles")
                    .update(
                        {
                            "full_name": display_name,
                            "preferred_currency": preferred_currency,
                            "weight_unit": weight_unit,
                        }
                    )
                    .eq("id", user_id)
                    .execute()
                )
                if upd.data:
                    profile = upd.data[0]
        else:
            ins = (
                client.table("profiles")
                .insert(
                    {
                        "id": user_id,
                        "email": email,
                        "full_name": display_name,
                        "preferred_currency": preferred_currency,
                        "weight_unit": weight_unit,
                    }
                )
                .execute()
            )
            profile = ins.data[0] if ins.data else {
                "id": user_id,
                "email": email,
                "full_name": display_name,
                "preferred_currency": preferred_currency,
                "weight_unit": weight_unit,
            }

        # Verificar que tenga categorías financieras base
        cats = (
            client.table("finance_categories")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not cats.data:
            rows = [{"user_id": user_id, **cat} for cat in DEFAULT_FINANCE_CATEGORIES]
            client.table("finance_categories").insert(rows).execute()

        return profile
    except Exception:
        return {
            "id": user_id,
            "email": email,
            "full_name": display_name,
            "preferred_currency": preferred_currency,
            "weight_unit": weight_unit,
        }


def _set_authenticated_state(
    user: Any,
    access_token: str,
    refresh_token: str,
    cookie_manager: Optional[stx.CookieManager] = None,
    full_name: Optional[str] = None,
    preferred_currency: str = "MXN",
    weight_unit: str = "kg",
) -> None:
    """Establece el estado de sesión autenticado, inyecta el JWT y guarda la cookie de 30 días."""
    st.session_state["authenticated"] = True
    st.session_state["user"] = user
    st.session_state["access_token"] = access_token
    st.session_state["refresh_token"] = refresh_token
    st.session_state["_logout_just_triggered"] = False

    client = get_supabase_client(access_token=access_token)
    client.postgrest.auth(access_token)

    user_id = str(user.id)
    email = str(getattr(user, "email", ""))
    meta_name = None
    user_meta = getattr(user, "user_metadata", None) or {}
    if isinstance(user_meta, dict):
        meta_name = user_meta.get("full_name")

    profile = _ensure_user_profile_and_defaults(
        user_id=user_id,
        email=email,
        full_name=full_name or meta_name,
        preferred_currency=preferred_currency,
        weight_unit=weight_unit,
    )
    st.session_state["user_profile"] = profile
    st.session_state["trifecta_weights"] = {
        "habits": float(profile.get("weight_habits") or 40.0),
        "workout": float(profile.get("weight_workouts") or 35.0),
        "finance": float(profile.get("weight_finances") or 25.0),
    }

    if cookie_manager is not None and refresh_token:
        expires_at = datetime.now(timezone.utc) + timedelta(days=COOKIE_EXPIRY_DAYS)
        try:
            cookie_manager.set(
                cookie=COOKIE_NAME,
                val=refresh_token,
                expires_at=expires_at,
                key=f"set_{COOKIE_NAME}_{int(time.time() * 1000) % 100000}",
            )
        except Exception:
            pass


def restore_session_from_cookie(cookie_manager: stx.CookieManager) -> bool:
    """
    Si st.session_state['authenticated'] no está activo pero existe la cookie `trifecta_rt`,
    ejecuta `supabase.auth.refresh_session(refresh_token)` automáticamente y restaura la sesión.
    """
    init_session_state()

    if st.session_state.get("authenticated") and st.session_state.get("access_token"):
        try:
            get_supabase_client(st.session_state["access_token"])
            return True
        except Exception:
            pass

    if not is_supabase_configured():
        return False

    if st.session_state.get("_logout_just_triggered"):
        return False

    try:
        stored_rt = cookie_manager.get(cookie=COOKIE_NAME)
    except Exception:
        stored_rt = None

    if not stored_rt or not isinstance(stored_rt, str):
        return False

    grace_cache = _get_rotation_grace_cache()
    now_ts = time.time()
    # Limpiar entradas expiradas (>60s)
    for k in list(grace_cache.keys()):
        if now_ts - grace_cache[k][0] > 60.0:
            del grace_cache[k]

    try:
        client = get_supabase_client()
        if stored_rt in grace_cache:
            auth_res = grace_cache[stored_rt][1]
        else:
            auth_res = client.auth.refresh_session(stored_rt)
            if auth_res and auth_res.session:
                grace_cache[stored_rt] = (now_ts, auth_res)

        if auth_res and auth_res.session and auth_res.user:
            new_at = auth_res.session.access_token
            new_rt = auth_res.session.refresh_token
            # Solo re-escribir cookie si rotó a un token nuevo distinto
            cm_to_update = cookie_manager if new_rt != stored_rt else None
            _set_authenticated_state(
                user=auth_res.user,
                access_token=new_at,
                refresh_token=new_rt,
                cookie_manager=cm_to_update,
            )
            return True
    except Exception:
        # Si el refresh token expiró o fue revocado, limpiar cookie silenciosamente
        try:
            cookie_manager.delete(cookie=COOKIE_NAME, key="del_invalid_rt")
        except Exception:
            pass

    return False


def login_user(
    email: str,
    password: str,
    cookie_manager: Optional[stx.CookieManager] = None,
) -> Tuple[bool, str]:
    """Inicia sesión con email y contraseña en Supabase Auth y persiste la cookie móvil."""
    email_clean = (email or "").strip().lower()
    if not email_clean or not password:
        return False, "Por favor ingresa tu correo electrónico y contraseña."

    if not is_supabase_configured():
        return False, "Configura SUPABASE_URL y SUPABASE_ANON_KEY en .streamlit/secrets.toml primero."

    try:
        client = get_supabase_client()
        res = client.auth.sign_in_with_password({"email": email_clean, "password": password})
        if res and res.session and res.user:
            _get_rotation_grace_cache()[res.session.refresh_token] = (time.time(), res)
            _set_authenticated_state(
                user=res.user,
                access_token=res.session.access_token,
                refresh_token=res.session.refresh_token,
                cookie_manager=cookie_manager,
            )
            return True, "Sesión iniciada correctamente."
        return False, "No se pudo iniciar sesión. Verifica tus credenciales."
    except Exception as exc:
        msg = str(exc)
        if "Invalid login credentials" in msg:
            return False, "Correo o contraseña incorrectos."
        if "Email not confirmed" in msg:
            return False, (
                "Tu correo aún no está confirmado. Revisa tu bandeja de entrada o desactiva "
                "'Confirm email' en Supabase -> Authentication -> Providers -> Email."
            )
        return False, f"Error al iniciar sesión: {msg}"


def register_user(
    full_name: str,
    email: str,
    password: str,
    preferred_currency: str = "MXN",
    weight_unit: str = "kg",
    cookie_manager: Optional[stx.CookieManager] = None,
) -> Tuple[bool, str]:
    """
    Registra un nuevo usuario en Supabase Auth, dispara la creación de su perfil
    y categorías financieras base, e inicia sesión automáticamente.
    """
    name_clean = (full_name or "").strip()
    email_clean = (email or "").strip().lower()

    if not name_clean:
        return False, "Por favor ingresa tu nombre."
    if not email_clean or "@" not in email_clean:
        return False, "Por favor ingresa un correo electrónico válido."
    if not password or len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    if not is_supabase_configured():
        return False, "Configura SUPABASE_URL y SUPABASE_ANON_KEY en .streamlit/secrets.toml primero."

    try:
        client = get_supabase_client()
        res = client.auth.sign_up(
            {
                "email": email_clean,
                "password": password,
                "options": {
                    "data": {
                        "full_name": name_clean,
                        "preferred_currency": preferred_currency,
                        "weight_unit": weight_unit,
                    }
                },
            }
        )

        # Si Supabase devuelve sesión activa inmediata (Confirm Email desactivado)
        if res and res.session and res.user:
            _get_rotation_grace_cache()[res.session.refresh_token] = (time.time(), res)
            _set_authenticated_state(
                user=res.user,
                access_token=res.session.access_token,
                refresh_token=res.session.refresh_token,
                cookie_manager=cookie_manager,
                full_name=name_clean,
                preferred_currency=preferred_currency,
                weight_unit=weight_unit,
            )
            return True, f"¡Cuenta creada con éxito! Bienvenido, {name_clean}."

        # Si creó el usuario pero requiere login explícito o confirmación de email
        if res and res.user:
            login_ok, _ = login_user(email_clean, password, cookie_manager=cookie_manager)
            if login_ok:
                return True, f"¡Cuenta creada con éxito! Bienvenido, {name_clean}."
            return True, (
                "Cuenta registrada. Si tienes activada la confirmación por correo en Supabase, "
                "confirma el enlace enviado a tu email o inicia sesión en la pestaña 'Iniciar Sesión'."
            )

        return False, "No se pudo completar el registro en Supabase."
    except Exception as exc:
        msg = str(exc)
        if "User already registered" in msg or "already registered" in msg.lower():
            return False, "Este correo electrónico ya está registrado. Usa la pestaña 'Iniciar Sesión'."
        return False, f"Error al registrar cuenta: {msg}"


def logout_user(cookie_manager: Optional[stx.CookieManager] = None) -> None:
    """
    Cierra la sesión en Supabase Auth, elimina la cookie `trifecta_rt`,
    limpia st.session_state y todas las funciones cacheadas (@st.cache_data).
    """
    old_rt = st.session_state.get("refresh_token")
    if old_rt:
        _get_rotation_grace_cache().pop(old_rt, None)

    try:
        if is_supabase_configured():
            client = get_supabase_client()
            client.auth.sign_out()
    except Exception:
        pass

    if cookie_manager is not None:
        try:
            cookie_manager.delete(cookie=COOKIE_NAME, key="logout_delete_cookie")
        except Exception:
            pass

    st.cache_data.clear()

    for key in ["authenticated", "user", "user_profile", "access_token", "refresh_token", "_supabase_client"]:
        st.session_state[key] = None
    st.session_state["authenticated"] = False
    st.session_state["active_pillar"] = "hub"
    st.session_state["_logout_just_triggered"] = True
