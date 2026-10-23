"""
Renderizador HTML/CSS de tarjetas bancarias modernas tipo Apple Wallet / Revolut
según 04_UI_UX_Design_Brief.md (§3.1).
"""
from __future__ import annotations

from typing import Optional
import streamlit as st

from src.config.theme import CARD_GRADIENTS


def render_credit_card_widget(
    institution_name: str,
    alias: str,
    last_four_digits: str = "0000",
    current_balance: float = 0.0,
    credit_limit: float = 0.0,
    cashback_pct: float = 0.0,
    cutoff_day: Optional[int] = None,
    payment_due_day: Optional[int] = None,
    card_network: str = "visa",
    gradient_theme: str = "indigo_neon",
    account_type: str = "credit_card",
) -> None:
    """Dibuja una tarjeta bancaria moderna en modo oscuro con barra de utilización e indicadores de corte/pago."""
    theme = CARD_GRADIENTS.get(gradient_theme, CARD_GRADIENTS["indigo_neon"])
    network_label = card_network.upper()

    if account_type == "credit_card" and credit_limit > 0:
        utilization_pct = min(100.0, max(0.0, (current_balance / credit_limit) * 100.0))
        if utilization_pct <= 30.0:
            bar_color = "#10B981"
        elif utilization_pct <= 70.0:
            bar_color = "#F59E0B"
        else:
            bar_color = "#EF4444"

        balance_label = f"Saldo Utilizado / Límite ({utilization_pct:.0f}%)"
        amount_html = f"${current_balance:,.2f} <small>/ ${credit_limit:,.2f}</small>"
        footer_mid = f"Corte: <b>Día {cutoff_day or '--'}</b>"
        footer_right = f"Pago: <b>Día {payment_due_day or '--'}</b>"
        badge_text = f"{cashback_pct:.1f}% Cashback" if cashback_pct > 0 else network_label
    else:
        utilization_pct = 100.0
        bar_color = "#10B981"
        balance_label = "Saldo Disponible"
        amount_html = f"${current_balance:,.2f}"
        footer_mid = f"Tipo: <b>{account_type.upper()}</b>"
        footer_right = f"Red: <b>{network_label}</b>"
        badge_text = network_label

    st.markdown(
        f"""
        <div class="trifecta-cc-card" style="background: {theme['css']}; border-color: {theme['border']};">
          <div class="cc-header">
            <div>
              <span class="cc-bank">{institution_name} · {network_label}</span>
              <h4 class="cc-alias">{alias}</h4>
            </div>
            <span class="cc-badge">{badge_text}</span>
          </div>
          <div class="cc-balance-block">
            <span class="cc-label">{balance_label}</span>
            <div class="cc-amount">{amount_html}</div>
            <div class="cc-progress-bg">
              <div class="cc-progress-fill" style="width: {utilization_pct:.1f}%; background: {bar_color};"></div>
            </div>
          </div>
          <div class="cc-footer">
            <span>•••• {last_four_digits[-4:] if last_four_digits else '0000'}</span>
            <span>{footer_mid}</span>
            <span>{footer_right}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
