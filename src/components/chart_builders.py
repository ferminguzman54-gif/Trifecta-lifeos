"""
Constructores Plotly con fondo transparente, márgenes compactos y tipografía móvil
según 04_UI_UX_Design_Brief.md (§3.3).
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def apply_mobile_dark_layout(fig: go.Figure, height: int = 280) -> go.Figure:
    """
    Aplica las reglas obligatorias de 04_UI_UX_Design_Brief.md §3.3:
    - paper_bgcolor="rgba(0,0,0,0)" y plot_bgcolor="rgba(0,0,0,0)"
    - margin=dict(l=8, r=8, t=28, b=8)
    - Leyenda horizontal superior (orientation="h", y=1.12)
    """
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#F8FAFC", size=12),
        margin=dict(l=8, r=8, t=28, b=8),
        height=height,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.12,
            xanchor="left",
            x=0,
            font=dict(size=11, color="#94A3B8"),
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(color="#94A3B8", size=11),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(38, 48, 68, 0.55)",
            zeroline=False,
            tickfont=dict(color="#94A3B8", size=11),
        ),
    )
    return fig


def render_mobile_plotly(fig: go.Figure, key: str | None = None) -> None:
    """Renderiza una gráfica Plotly ocultando la barra de herramientas de escritorio."""
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
        key=key,
    )
