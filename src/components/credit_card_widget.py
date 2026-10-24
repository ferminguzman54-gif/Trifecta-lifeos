"""
Renderizador HTML/CSS de tarjetas bancarias modernas tipo Apple Wallet / Revolut
según 04_UI_UX_Design_Brief.md (§3.1) con cálculo de días restantes al corte,
días al pago, disponible en línea y ventana óptima de financiamiento.
"""
from __future__ import annotations

from typing import Optional
import streamlit as st

from src.config.theme import CARD_GRADIENTS


def _flat(html: str) -> str:
    """Colapsa HTML multilínea a una sola línea sin sangría.

    Markdown trata líneas con 4+ espacios al inicio como bloque de código, lo que
    mostraba etiquetas <div style=...> como texto crudo dentro de la tarjeta.
    """
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
    con barra de utilización de crédito, saldo disponible y días restantes para corte y pago.
    """
    theme = CARD_GRADIENTS.get(gradient_theme, CARD_GRADIENTS["indigo_neon"])
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
            f"<b style='color:#10B981;'>Disp: ${available_credit:,.2f}</b>"
        )
        amount_html = f"${current_balance:,.2f} <small>/ ${credit_limit:,.2f}</small>"

        cut_Countdown = f" ({days_until_cutoff}d)" if days_until_cutoff is not None else ""
        pay_Countdown = f" ({days_until_payment}d)" if days_until_payment is not None else ""
        footer_mid = f"Corte: <b>Día {cutoff_day or '--'}</b>{cut_Countdown}"
        footer_right = f"Pago: <b>Día {payment_due_day or '--'}</b>{pay_Countdown}"

        if cashback_pct > 0:
            badge_text = f"✨ {cashback_pct:g}% Cashback"
        elif interest_rate_cat and interest_rate_cat > 0:
            badge_text = f"CAT {interest_rate_cat:g}%"
        else:
            badge_text = network_label

        float_banner_html = ""
        if float_days_today is not None:
            if float_days_today >= 40:
                f_color = "#10B981"
                f_icon = "🔥 Ventana Óptima post-corte"
            elif float_days_today >= 27:
                f_color = "#3B82F6"
                f_icon = "✅ Buen financiamiento"
            else:
                f_color = "#F59E0B"
                f_icon = "⏳ Próxima a cortar"
            float_banner_html = _flat(
                f"""
<div style="display:flex; justify-content:space-between; align-items:center;
font-size:0.73rem; background:rgba(10,13,20,0.45);
padding:5px 10px; border-radius:9px; margin-bottom:8px;
border:1px solid rgba(255,255,255,0.10);">
<span style="color:{f_color}; font-weight:700;">{f_icon}</span>
<span>Comprando hoy: <b>{float_days_today} días sin intereses</b></span>
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
        amount_html = f"${current_balance:,.2f}"
        footer_mid = f"Liquidez Inmediata"
        footer_right = f"Red: <b>{network_label}</b>"
        badge_text = "LÍQUIDO" if account_type in ("debit", "cash") else "INVERSIÓN"
        float_banner_html = ""

    st.markdown(
        _flat(
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
{float_banner_html}
<div class="cc-footer">
<span>•••• {clean_last4}</span>
<span>{footer_mid}</span>
<span>{footer_right}</span>
</div>
</div>
"""
        ),
        unsafe_allow_html=True,
    )