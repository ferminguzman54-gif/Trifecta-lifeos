"""
Tarjetas KPI de alto contraste con cifras tabulares, delta semántico y barra de progreso.
"""
from __future__ import annotations

from typing import Optional
import streamlit as st


def render_kpi_card(
    label: str,
    value: str,
    delta_text: Optional[str] = None,
    delta_positive: bool = True,
    accent_color: str = "#3B82F6",
    progress_pct: Optional[float] = None,
) -> None:
    """Renderiza una tarjeta de métrica compacta optimizada para pantalla móvil."""
    delta_color = "#22C55E" if delta_positive else "#EF4444"
    delta_html = ""
    if delta_text:
        delta_html = (
            f'<span style="font-size:0.75rem; font-weight:600; color:{delta_color}; '
            f'background:{delta_color}1F; padding:2px 8px; border-radius:999px;">{delta_text}</span>'
        )

    progress_html = ""
    if progress_pct is not None:
        clamped = max(0.0, min(100.0, float(progress_pct)))
        progress_html = (
            f'<div style="width:100%; height:6px; background:rgba(255,255,255,0.10); border-radius:999px; margin-top:8px; overflow:hidden;">'
            f'<div style="width:{clamped:.1f}%; height:100%; background:{accent_color}; border-radius:999px;"></div>'
            f'</div>'
        )

    st.markdown(
        f"""
<div style="background:#121722; border:1px solid #263044; border-radius:16px; padding:12px 14px; margin-bottom:10px;">
<div style="display:flex; justify-content:space-between; align-items:center;">
<span style="font-size:0.78rem; color:#94A3B8; font-weight:500;">{label}</span>
{delta_html}
</div>
<div class="trifecta-kpi-value" style="font-size:1.45rem; color:#F8FAFC; margin-top:4px;">{value}</div>
{progress_html}
</div>
""",
        unsafe_allow_html=True,
    )
