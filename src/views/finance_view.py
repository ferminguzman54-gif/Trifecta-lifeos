"""
Módulo 2: Finanzas Personales (Flujo y Dashboard, Tarjetas y Simulador TDC, Calendario y Suscripciones)
según 03_Appflow_Flujo_Usuario.md (§5) y 04_UI_UX_Design_Brief.md (§3.1).
"""
from __future__ import annotations

from typing import Any, Dict, List
import streamlit as st

from src.auth.session_manager import get_current_user_id
from src.auth.supabase_client import get_supabase_client
from src.components.credit_card_widget import render_credit_card_widget
from src.config.theme import PALETTE, render_pillar_header


@st.cache_data(ttl=300)
def _fetch_user_finance_categories(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    """Consulta las categorías financieras exclusivas del usuario autenticado (RLS)."""
    try:
        client = get_supabase_client(access_token=access_token)
        res = (
            client.table("finance_categories")
            .select("*")
            .eq("user_id", user_id)
            .order("kind")
            .order("name")
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def render_finance_view() -> None:
    """Renderiza el esqueleto navegable móvil del Pilar 2: Finanzas Personales."""
    render_pillar_header(
        title="Finanzas Personales",
        subtitle="Flujo de caja, billetera moderna y recomendador inteligente de TDC",
        accent_hex=PALETTE["accent_finance"],
        badge_text="💳 Pilar 2 · Smart Liquidity & Credit",
    )

    tab_flow, tab_cards, tab_calendar = st.tabs(
        ["💸 Flujo y Dashboard", "💳 Tarjetas y Simulador TDC", "📅 Calendario y PDF"]
    )

    with tab_flow:
        user_id = get_current_user_id() or ""
        access_token = st.session_state.get("access_token") or ""
        categories = _fetch_user_finance_categories(user_id, access_token) if user_id and access_token else []

        with st.container(border=True):
            st.markdown(f"#### 🗂️ Categorías y Presupuestos del Usuario ({len(categories)} activas)")
            st.caption(
                "Categorías aisladas por `user_id` mediante Supabase RLS. En el Sprint 4 se activará "
                "el modal `@st.dialog` de captura en 3 toques y las gráficas de flujo neto."
            )
            for cat in categories[:8]:
                budget = float(cat.get("monthly_budget_limit") or 0.0)
                budget_str = f"Presupuesto: ${budget:,.0f}/mes" if budget > 0 else f"Tipo: {cat.get('kind')}"
                st.markdown(
                    f"""
                    <div style="
                        display:flex; justify-content:space-between; align-items:center;
                        padding:8px 12px; border-radius:10px; background:#1A2232;
                        border:1px solid #263044; margin-bottom:6px;
                    ">
                        <span style="font-size:0.88rem; font-weight:600; color:#F8FAFC;">
                            {cat.get('icon', '💳')} {cat.get('name')}
                        </span>
                        <span style="font-size:0.78rem; color:#10B981; font-family:'JetBrains Mono', monospace;">
                            {budget_str}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with tab_cards:
        st.markdown("#### 💳 Vista Previa de Billetera Digital (`credit_card_widget.py`)")
        render_credit_card_widget(
            institution_name="NU MÉXICO",
            alias="TDC Principal (Demo UI)",
            last_four_digits="9042",
            current_balance=8400.00,
            credit_limit=40000.00,
            cashback_pct=1.5,
            cutoff_day=15,
            payment_due_day=5,
            card_network="mastercard",
            gradient_theme="indigo_neon",
            account_type="credit_card",
        )
        with st.container(border=True):
            st.markdown("##### 🧠 Simulador «¿Con qué tarjeta pago hoy?» (Sprint 4)")
            st.caption(
                "Evaluará automáticamente: **45%** Días de financiamiento gratuito (`float_days`), "
                "**25%** Retorno Cashback, **20%** Salud de utilización (`<=30%`) y **10%** Ajuste al presupuesto."
            )

    with tab_calendar:
        with st.container(border=True):
            st.markdown("#### 📅 Calendario Financiero y Suscripciones")
            st.caption(
                "En el Sprint 4 se integrará la cuadrícula mensual de fechas de corte, fechas límite de pago "
                "y cobros recurrentes, además del conector para importación asistida de PDF en Fase 2."
            )
