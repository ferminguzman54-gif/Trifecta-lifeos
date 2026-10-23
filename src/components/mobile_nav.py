"""
Cabecera compacta móvil, Popover de Avatar con acceso a Ajustes/Respaldo y
Selector Superior Fijo de 4 destinos según 03_Appflow_Flujo_Usuario.md (§1 y §2) y Sprint 6.
"""
from __future__ import annotations

from typing import Optional
import extra_streamlit_components as stx
import streamlit as st

from src.auth.session_manager import logout_user
from src.config.settings import NAV_DESTINATIONS

SETTINGS_META = {
    "key": "settings",
    "label": "⚙️ Ajustes",
    "full_title": "Ajustes, Perfil & Respaldo",
    "accent": "#3B82F6",
}


def render_mobile_header_and_nav(cookie_manager: Optional[stx.CookieManager] = None) -> str:
    """
    Renderiza la barra superior compacta con el avatar del usuario en la esquina superior derecha
    (con acceso táctil a Ajustes/Exportación y Cerrar Sesión) y la barra de navegación de 4 pilares.
    """
    profile = st.session_state.get("user_profile") or {}
    user_obj = st.session_state.get("user")
    full_name = profile.get("full_name") or getattr(user_obj, "email", "Usuario")
    alias = (profile.get("alias") or "").strip()
    short_name = (alias if alias else str(full_name).split(" ")[0])[:14]
    email = profile.get("email") or getattr(user_obj, "email", "")
    currency = profile.get("preferred_currency", "MXN")
    weight_unit = profile.get("weight_unit", "kg")
    date_fmt = profile.get("date_format", "DD/MM/YYYY")

    active_key = st.session_state.get("active_pillar", "hub")
    if active_key not in NAV_DESTINATIONS and active_key != "settings":
        active_key = "hub"
        st.session_state["active_pillar"] = "hub"

    active_meta = SETTINGS_META if active_key == "settings" else NAV_DESTINATIONS[active_key]

    # Fila superior: Marca + Popover de Avatar de Usuario en esquina superior derecha
    col_brand, col_user = st.columns([0.64, 0.36], vertical_alignment="center")

    with col_brand:
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:8px; padding:4px 0;">
                <span style="
                    display:inline-flex; align-items:center; justify-content:center;
                    width:30px; height:30px; border-radius:9px;
                    background:{active_meta['accent']}26; border:1px solid {active_meta['accent']}66;
                    font-size:1rem;
                ">⚡</span>
                <div>
                    <div style="font-weight:800; font-size:1.0rem; letter-spacing:-0.02em; color:#F8FAFC; line-height:1.1;">
                        TRIFECTA <span style="color:{active_meta['accent']}; font-weight:700;">LifeOS</span>
                    </div>
                    <div style="font-size:0.72rem; color:#94A3B8; line-height:1.1;">
                        {active_meta['full_title']}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_user:
        with st.popover(f"👤 {short_name}", use_container_width=True):
            st.markdown(f"**{full_name}**" + (f" (`@{alias}`)" if alias else ""))
            if email:
                st.caption(f"📧 `{email}`")
            st.caption(f"💱 **{currency}** · ⚖️ **{weight_unit}** · 📅 `{date_fmt}`")
            st.divider()
            if st.button(
                "⚙️ Ajustes, Perfil & Respaldo",
                use_container_width=True,
                key="btn_top_open_settings",
            ):
                st.session_state["active_pillar"] = "settings"
                st.rerun()
            if st.button(
                "🚪 Cerrar Sesión",
                type="primary",
                use_container_width=True,
                key="btn_top_logout",
            ):
                logout_user(cookie_manager=cookie_manager)
                st.rerun()

    # Selector Superior Fijo con los 4 destinos principales
    keys_order = ["hub", "workout", "finance", "habits"]
    labels_map = {k: NAV_DESTINATIONS[k]["label"] for k in keys_order}

    nav_cols = st.columns(4)
    for idx, k in enumerate(keys_order):
        with nav_cols[idx]:
            btn_type = "primary" if k == active_key else "secondary"
            if st.button(labels_map[k], key=f"nav_btn_{k}", type=btn_type, use_container_width=True):
                st.session_state["active_pillar"] = k
                st.rerun()

    return st.session_state["active_pillar"]
