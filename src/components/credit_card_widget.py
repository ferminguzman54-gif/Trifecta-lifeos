"""
Renderizador HTML/CSS de tarjetas bancarias modernas tipo Apple Wallet / Revolut
según 04_UI_UX_Design_Brief.md (§3.1) con cálculo de días restantes al corte,
días al pago, disponible en línea, ventana óptima de financiamiento y alto contraste
tipográfico para todas las carátulas (incluyendo Obsidian Gold, Emerald Minimal,
Cyberpunk Cyan, Sunset Orange, Titanium Silver y Rose Velvet).
"""
from __future__ import annotations

from typing import Optional
import streamlit as st

from src.config.theme import CARD_GRADIENTS


def _flat(html: str) -> str:
    """Colapsa HTML multilínea a una sola línea sin sangría."""
    return " ".join(line.strip() for line in str(html).splitlines() if line.strip())


def render_credit_card_widget(
    institution_name: str,
    alias: str,
    last_four_digits: str = "0000",
    current_balance: float = 0.0,
    credit_limit: float = 0.0,
    cashback_pct: float = 0.0,
    cutoff_day: Optional[int] = None,
    payment_due_day: Optional[int] = None,
    days_until_cutoff: Optional[int] = None,
    days_until_payment: Optional[int] = None,
    float_days_today: Optional[int] = None,
    interest_rate_cat: Optional[float] = None,
    card_network: str = "visa",
    gradient_theme: str = "indigo_neon",
    account_type: str = "credit_card",
) -> None:
    """
    Dibuja una tarjeta bancaria moderna en modo oscuro inspirada en Apple Wallet / Revolut
    con barra de utilización de crédito, saldo disponible, contraste tipográfico garantizado
    y badges legibles de cashback/CAT.
    """
    theme = CARD_GRADIENTS.get(gradient_theme, CARD_GRADIENTS["indigo_neon"])
    text_col = theme.get("text_color", "#F8FAFC")
    muted_col = theme.get("muted_color", "#E2E8F0")
    badge_bg = theme.get("badge_bg", "rgba(10, 13, 20, 0.62)")
    badge_border = theme.get("badge_border", "rgba(255, 255, 255, 0.30)")
    badge_txt_col = theme.get("badge_text_color", "#F8FAFC")

    network_label = (card_network or "visa").upper()
    clean_last4 = (last_four_digits or "0000")[-4:]

    if account_type == "credit_card" and credit_limit > 0:
        available_credit = max(0.0, credit_limit - current_balance)
        utilization_pct = min(100.0, max(0.0, (current_balance / credit_limit) * 100.0))
        if utilization_pct <= 30.0:
            bar_color = "#10B981"
            health_txt = "Óptimo ≤30%"
        elif utilization_pct <= 70.0:
            bar_color = "#F59E0B"
            health_txt = "Moderado"
        else:
            bar_color = "#EF4444"
            health_txt = "Alerta >70%"

        balance_label = (
            f"Utilizado ({utilization_pct:.0f}% · {health_txt}) · "
            f"<b style='color:#34D399;'>Disp: ${available_credit:,.2f}</b>"
        )
        amount_html = (
            f"<span style='color:{text_col};'>${current_balance:,.2f}</span> "
            f"<small style='color:{muted_col}; opacity:0.9;'>/ ${credit_limit:,.2f}</small>"
        )

        cut_countdown = f" ({days_until_cutoff}d)" if days_until_cutoff is not None else ""
        pay_countdown = f" ({days_until_payment}d)" if days_until_payment is not None else ""
        footer_mid = f"Corte: <b style='color:{text_col};'>Día {cutoff_day or '--'}</b>{cut_countdown}"
        footer_right = f"Pago: <b style='color:{text_col};'>Día {payment_due_day or '--'}</b>{pay_countdown}"

        if cashback_pct > 0:
            badge_text = f"✨ {cashback_pct:g}% Cashback"
        elif interest_rate_cat and interest_rate_cat > 0:
            badge_text = f"CAT {interest_rate_cat:g}%"
        else:
            badge_text = network_label

        float_banner_html = ""
        if float_days_today is not None:
            if float_days_today >= 40:
                f_color = "#34D399"
                f_icon = "🔥 Ventana Óptima post-corte"
            elif float_days_today >= 27:
                f_color = "#60A5FA"
                f_icon = "✅ Buen financiamiento"
            else:
                f_color = "#FBBF24"
                f_icon = "⏳ Próxima a cortar"
            float_banner_html = _flat(
                f"""
<div style="display:flex; justify-content:space-between; align-items:center; font-size:0.73rem; background:rgba(10,13,20,0.58); padding:5px 10px; border-radius:9px; margin-bottom:8px; border:1px solid rgba(255,255,255,0.16); color:{text_col};">
<span style="color:{f_color}; font-weight:700;">{f_icon}</span>
<span style="color:{muted_col};">Comprando hoy: <b style="color:{text_col};">{float_days_today} días sin intereses</b></span>
</div>
"""
            )
    else:
        utilization_pct = 100.0
        bar_color = "#10B981"
        type_map = {
            "debit": "Cuenta de Débito / Liquidez",
            "cash": "Efectivo Disponible",
            "investment": "Capital en Inversión / Ahorro",
        }
        balance_label = type_map.get(account_type, "Saldo Disponible")
        amount_html = f"<span style='color:{text_col};'>${current_balance:,.2f}</span>"
        footer_mid = "Liquidez Inmediata"
        footer_right = f"Red: <b style='color:{text_col};'>{network_label}</b>"
        badge_text = "LÍQUIDO" if account_type in ("debit", "cash") else "INVERSIÓN"
        float_banner_html = ""

    st.markdown(
        _flat(
            f"""
<div class="trifecta-cc-card" style="background: {theme['css']}; border-color: {theme['border']}; color: {text_col}; text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);">
<div class="cc-header">
<div>
<span class="cc-bank" style="color: {muted_col}; opacity: 0.92; font-weight: 600;">{institution_name} · {network_label}</span>
<h4 class="cc-alias" style="color: {text_col};">{alias}</h4>
</div>
<span class="cc-badge" style="background: {badge_bg}; color: {badge_txt_col}; border: 1px solid {badge_border}; backdrop-filter: blur(6px); font-weight: 700;">{badge_text}</span>
</div>
<div class="cc-balance-block">
<span class="cc-label" style="color: {muted_col};">{balance_label}</span>
<div class="cc-amount" style="color: {text_col};">{amount_html}</div>
<div class="cc-progress-bg" style="background: rgba(10, 13, 20, 0.38);">
<div class="cc-progress-fill" style="width: {utilization_pct:.1f}%; background: {bar_color};"></div>
</div>
</div>
{float_banner_html}
<div class="cc-footer" style="color: {muted_col}; border-top: 1px solid rgba(255, 255, 255, 0.18);">
<span style="color: {text_col}; font-weight: 600;">•••• {clean_last4}</span>
<span>{footer_mid}</span>
<span>{footer_right}</span>
</div>
</div>
"""
        ),
        unsafe_allow_html=True,
    )
