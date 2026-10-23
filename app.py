"""
TRIFECTA LifeOS — Punto de entrada principal (Entrypoint para Streamlit Cloud)
Arquitectura Mobile-First de alto contraste con Supabase Auth + RLS + Cookies.
"""
from __future__ import annotations

import streamlit as st

from src.auth.session_manager import (
    get_cookie_manager,
    init_session_state,
    restore_session_from_cookie,
)
from src.components.mobile_nav import render_mobile_header_and_nav
from src.config.settings import APP_NAME
from src.config.theme import inject_global_theme
from src.views.auth_view import render_auth_view
from src.views.finance_view import render_finance_view
from src.views.habits_view import render_habits_view
from src.views.home_hub_view import render_home_hub_view
from src.views.workout_view import render_workout_view


def main() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="⚡",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # 1. Inyectar sistema de diseño móvil de alto contraste (#0A0D14 + tarjetas glassmorphism)
    inject_global_theme()

    # 2. Inicializar estado y gestor de cookies del navegador móvil (trifecta_rt por 30 días)
    init_session_state()
    cookie_manager = get_cookie_manager()

    # 3. Verificar sesión activa o restaurar automáticamente desde cookie JWT
    is_authenticated = restore_session_from_cookie(cookie_manager)

    if not is_authenticated:
        render_auth_view(cookie_manager=cookie_manager)
        return

    # 4. Barra de control superior de un toque (4 destinos principales) + Popover de perfil/logout
    active_pillar = render_mobile_header_and_nav(cookie_manager=cookie_manager)

    # 5. Enrutamiento del pilar activo
    if active_pillar == "hub":
        render_home_hub_view()
    elif active_pillar == "workout":
        render_workout_view()
    elif active_pillar == "finance":
        render_finance_view()
    elif active_pillar == "habits":
        render_habits_view()
    else:
        render_home_hub_view()


if __name__ == "__main__":
    main()
