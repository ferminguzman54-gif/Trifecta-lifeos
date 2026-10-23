"""
Pantalla de Inicio de Sesión y Registro de Cuenta Multiusuario
según 03_Appflow_Flujo_Usuario.md (§2) y 04_UI_UX_Design_Brief.md.
"""
from __future__ import annotations

from typing import Optional
import extra_streamlit_components as stx
import streamlit as st

from src.auth.session_manager import login_user, register_user
from src.config.settings import is_supabase_configured


def render_auth_view(cookie_manager: Optional[stx.CookieManager] = None) -> None:
    """Renderiza la tarjeta centrada de Autenticación con pestañas Iniciar Sesión y Crear Cuenta."""
    st.markdown(
        """
        <div style="text-align:center; padding: 18px 8px 14px 8px;">
            <div style="
                display:inline-flex; align-items:center; justify-content:center;
                width:54px; height:54px; border-radius:16px;
                background:linear-gradient(135deg, rgba(59,130,246,0.25) 0%, rgba(139,92,246,0.25) 100%);
                border:1px solid rgba(255,255,255,0.16);
                font-size:1.65rem; margin-bottom:10px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            ">⚡</div>
            <h1 style="margin:0; font-size:1.65rem !important; font-weight:800 !important;">
                TRIFECTA <span style="color:#3B82F6;">LifeOS</span>
            </h1>
            <p style="color:#94A3B8; font-size:0.88rem; margin:6px 0 12px 0;">
                Sistema Operativo Personal · Mobile-First
            </p>
            <div style="display:flex; justify-content:center; gap:6px; flex-wrap:wrap;">
                <span class="trifecta-pillar-pill" style="background:rgba(255,85,0,0.15); color:#FF5500; border:1px solid rgba(255,85,0,0.35);">
                    🏋️ Entrenamiento
                </span>
                <span class="trifecta-pillar-pill" style="background:rgba(16,185,129,0.15); color:#10B981; border:1px solid rgba(16,185,129,0.35);">
                    💳 Finanzas
                </span>
                <span class="trifecta-pillar-pill" style="background:rgba(139,92,246,0.15); color:#8B5CF6; border:1px solid rgba(139,92,246,0.35);">
                    🎯 Hábitos y Metas
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not is_supabase_configured():
        st.warning(
            "⚙️ **Configuración pendiente de Supabase:**\n\n"
            "1. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml`.\n"
            "2. Coloca tu `SUPABASE_URL` y `SUPABASE_ANON_KEY`.\n"
            "3. Ejecuta `sql/01_schema_ddl.sql` y `sql/02_seed_catalog.sql` en el SQL Editor de Supabase."
        )

    with st.container(border=True):
        tab_login, tab_signup = st.tabs(["🔑 Iniciar Sesión", "✨ Crear Cuenta"])

        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                st.markdown("##### Accede a tu espacio privado")
                email_in = st.text_input(
                    "Correo Electrónico",
                    placeholder="tu@correo.com",
                    key="login_email",
                )
                password_in = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="••••••••",
                    key="login_password",
                )
                submitted_login = st.form_submit_button(
                    "Entrar",
                    type="primary",
                    use_container_width=True,
                )

                if submitted_login:
                    with st.spinner("Autenticando sesión segura..."):
                        ok, msg = login_user(
                            email=email_in,
                            password=password_in,
                            cookie_manager=cookie_manager,
                        )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        with tab_signup:
            with st.form("form_signup", clear_on_submit=False):
                st.markdown("##### Crea tu cuenta aislada con RLS")
                full_name_in = st.text_input(
                    "Nombre o Alias",
                    placeholder="Ej. Fermín",
                    key="signup_name",
                )
                email_reg = st.text_input(
                    "Correo Electrónico",
                    placeholder="tu@correo.com",
                    key="signup_email",
                )
                password_reg = st.text_input(
                    "Contraseña (mínimo 6 caracteres)",
                    type="password",
                    placeholder="••••••••",
                    key="signup_password",
                )
                col_curr, col_unit = st.columns(2)
                with col_curr:
                    pref_currency = st.selectbox(
                        "Moneda Base",
                        options=["MXN", "USD", "EUR", "COP", "ARS", "CLP"],
                        index=0,
                        key="signup_currency",
                    )
                with col_unit:
                    pref_unit = st.selectbox(
                        "Unidad de Peso",
                        options=["kg", "lb"],
                        index=0,
                        key="signup_weight_unit",
                    )

                submitted_signup = st.form_submit_button(
                    "Crear mi cuenta",
                    type="primary",
                    use_container_width=True,
                )

                if submitted_signup:
                    with st.spinner("Creando perfil y catálogo financiero base..."):
                        ok, msg = register_user(
                            full_name=full_name_in,
                            email=email_reg,
                            password=password_reg,
                            preferred_currency=pref_currency,
                            weight_unit=pref_unit,
                            cookie_manager=cookie_manager,
                        )
                    if ok:
                        st.success(msg)
                        if st.session_state.get("authenticated"):
                            st.rerun()
                    else:
                        st.error(msg)

    st.markdown(
        """
        <div style="text-align:center; margin-top:14px; font-size:0.76rem; color:#94A3B8;">
            🔒 Arquitectura Multiusuario con <b>Supabase Row Level Security (RLS)</b> · Sesión persistente 30 días
        </div>
        """,
        unsafe_allow_html=True,
    )
