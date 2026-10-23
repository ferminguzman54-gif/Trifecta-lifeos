"""
Paleta hexadecimal de alto contraste por pilar e inyección de CSS global
según 04_UI_UX_Design_Brief.md.
"""
from __future__ import annotations

from typing import Dict
import streamlit as st

# Tokens de color y superficie (04_UI_UX_Design_Brief.md §1)
PALETTE: Dict[str, str] = {
    "bg_canvas": "#0A0D14",
    "bg_surface_1": "#121722",
    "bg_surface_2": "#1A2232",
    "border_subtle": "#263044",
    "text_primary": "#F8FAFC",
    "text_muted": "#94A3B8",
    "accent_hub": "#3B82F6",
    "accent_workout": "#FF5500",
    "accent_workout_alt": "#FF2E54",
    "accent_finance": "#10B981",
    "accent_finance_alt": "#059669",
    "accent_habits": "#8B5CF6",
    "accent_habits_alt": "#6366F1",
    "accent_nutrition": "#06B6D4",
    "status_success": "#22C55E",
    "status_warning": "#F59E0B",
    "status_danger": "#EF4444",
}

# Degradados de tarjetas bancarias modernas (04_UI_UX_Design_Brief.md §3.1)
CARD_GRADIENTS: Dict[str, Dict[str, str]] = {
    "indigo_neon": {
        "label": "Índigo / Fintech",
        "css": "linear-gradient(135deg, #1E1B4B 0%, #4338CA 100%)",
        "border": "rgba(255, 255, 255, 0.16)",
    },
    "violet_nu": {
        "label": "Violeta Neón (Nu / Fintech)",
        "css": "linear-gradient(135deg, #4A00E0 0%, #8E2DE2 100%)",
        "border": "rgba(255, 255, 255, 0.18)",
    },
    "deep_blue": {
        "label": "Azul Profundo (BBVA / Citibanamex)",
        "css": "linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%)",
        "border": "rgba(255, 255, 255, 0.16)",
    },
    "crimson_red": {
        "label": "Rojo Intenso (Santander / HSBC)",
        "css": "linear-gradient(135deg, #870000 0%, #190A05 100%)",
        "border": "rgba(255, 255, 255, 0.16)",
    },
    "metallic_gold": {
        "label": "Metalizado / Platino-Oro (Amex / Invex)",
        "css": "linear-gradient(135deg, #232526 0%, #414345 100%)",
        "border": "#D4AF37",
    },
    "emerald_wealth": {
        "label": "Esmeralda Patrimonial (Ahorro / Inversión)",
        "css": "linear-gradient(135deg, #064E3B 0%, #047857 100%)",
        "border": "rgba(16, 185, 129, 0.35)",
    },
}

GLOBAL_CSS: str = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif !important;
    background-color: #0A0D14 !important;
    color: #F8FAFC !important;
}

/* Reducción de márgenes muertos en pantallas móviles y PWA (04_UI_UX_Design_Brief.md §4 + Sprint 5) */
.block-container {
    padding-top: 0.65rem !important;
    padding-bottom: 3.5rem !important;
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
    max-width: 720px !important;
}

/* Ocultar elementos nativos de desarrollo de Streamlit para experiencia PWA limpia */
header[data-testid="stHeader"] {
    display: none !important;
    height: 0px !important;
}
#MainMenu,
.stDeployButton,
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"],
footer {
    display: none !important;
    visibility: hidden !important;
}

/* Scrollbar sutil de alto contraste */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #0A0D14;
}
::-webkit-scrollbar-thumb {
    background: #263044;
    border-radius: 999px;
}

/* Tarjeta Hero del Trifecta Score (Sprint 5) */
.trifecta-hero-card {
    background: radial-gradient(circle at top right, rgba(59, 130, 246, 0.18), rgba(18, 23, 34, 0.98) 68%);
    border: 1px solid #2E3C56;
    border-radius: 20px;
    padding: 18px;
    margin-bottom: 12px;
    box-shadow: 0 14px 32px rgba(0, 0, 0, 0.50);
}
.trifecta-quick-dock {
    background: linear-gradient(135deg, rgba(18, 23, 34, 0.96) 0%, rgba(26, 34, 50, 0.96) 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 10px 12px;
    margin-bottom: 12px;
}

/* Jerarquía tipográfica móvil (04_UI_UX_Design_Brief.md §2) */
h1 {
    font-size: 1.50rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    margin-bottom: 0.5rem !important;
    color: #F8FAFC !important;
}
h2 {
    font-size: 1.22rem !important;
    font-weight: 700 !important;
    color: #F8FAFC !important;
}
h3 {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #F8FAFC !important;
}
p, label, span {
    line-height: 1.45;
}

/* Números tabulares para métricas financieras y pesos de gimnasio */
[data-testid="stMetricValue"], .trifecta-kpi-value, .cc-amount {
    font-family: 'JetBrains Mono', 'Inter', monospace !important;
    font-variant-numeric: tabular-nums !important;
    font-weight: 800 !important;
}

/* Tarjetas modernas con efecto Glassmorphism oscuro */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(180deg, rgba(18, 23, 34, 0.95) 0%, rgba(14, 18, 28, 0.98) 100%) !important;
    border: 1px solid #263044 !important;
    border-radius: 16px !important;
    padding: 14px !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35) !important;
}

/* Botones táctiles con altura mínima de 46px y bordes suaves */
.stButton > button, .stFormSubmitButton > button {
    min-height: 46px !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    transition: all 0.18s ease-in-out !important;
}
.stButton > button:active, .stFormSubmitButton > button:active {
    transform: scale(0.98) !important;
}

/* Inputs con fuente >= 16px y altura mínima 46px para evitar auto-zoom en iOS Safari */
div[data-baseweb="input"] input,
div[data-baseweb="select"] > div,
textarea {
    font-size: 16px !important;
    min-height: 46px !important;
    border-radius: 12px !important;
    background-color: #1A2232 !important;
    color: #F8FAFC !important;
}

/* Pestañas horizontales (st.tabs) estilizadas para móvil */
button[data-baseweb="tab"] {
    min-height: 44px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding-left: 10px !important;
    padding-right: 10px !important;
}

/* Estilo de la tarjeta bancaria moderna (04_UI_UX_Design_Brief.md §3.1 y §4) */
.trifecta-cc-card {
    border-radius: 18px;
    padding: 18px;
    color: #F8FAFC;
    border: 1px solid rgba(255, 255, 255, 0.16);
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.45);
    margin-bottom: 12px;
}
.cc-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 14px;
}
.cc-bank {
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    opacity: 0.8;
}
.cc-alias {
    margin: 2px 0 0 0;
    font-size: 1.05rem;
    font-weight: 700;
}
.cc-badge {
    background: rgba(255, 255, 255, 0.18);
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
}
.cc-label {
    font-size: 0.76rem;
    color: rgba(248, 250, 252, 0.75);
}
.cc-amount {
    font-size: 1.35rem;
    font-weight: 800;
    margin: 4px 0 8px 0;
}
.cc-amount small {
    font-size: 0.85rem;
    font-weight: 500;
    opacity: 0.75;
}
.cc-progress-bg {
    width: 100%;
    height: 7px;
    background: rgba(255, 255, 255, 0.15);
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 12px;
}
.cc-progress-fill {
    height: 100%;
    border-radius: 999px;
    transition: width 0.3s ease;
}
.cc-footer {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
    opacity: 0.9;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    padding-top: 10px;
}

/* Cabecera compacta móvil y badges de pilar */
.trifecta-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: rgba(18, 23, 34, 0.92);
    border: 1px solid #263044;
    border-radius: 14px;
    margin-bottom: 10px;
    backdrop-filter: blur(12px);
}
.trifecta-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 800;
    font-size: 1.02rem;
    letter-spacing: -0.02em;
    color: #F8FAFC;
}
.trifecta-pillar-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}

/* Banners de sobrecarga progresiva (04_UI_UX_Design_Brief.md §3.2) */
.trifecta-prog-banner {
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 10px;
    border-left: 4px solid #10B981;
}
</style>
"""


def inject_global_theme() -> None:
    """Inyecta la hoja de estilos CSS de alto contraste y los meta-tags PWA en Streamlit."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    try:
        from src.components.pwa_head import inject_pwa_metadata
        inject_pwa_metadata()
    except Exception:
        pass


def render_pillar_header(title: str, subtitle: str, accent_hex: str, badge_text: str) -> None:
    """Renderiza el encabezado semántico de cada módulo con su color de acento correspondiente."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {accent_hex}1F 0%, rgba(18, 23, 34, 0.95) 100%);
            border: 1px solid {accent_hex}4D;
            border-left: 4px solid {accent_hex};
            border-radius: 16px;
            padding: 14px 16px;
            margin-bottom: 14px;
        ">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span class="trifecta-pillar-pill" style="background:{accent_hex}2E; color:{accent_hex}; border:1px solid {accent_hex}55;">
                    {badge_text}
                </span>
            </div>
            <div style="font-size:1.30rem; font-weight:800; color:#F8FAFC; line-height:1.2;">{title}</div>
            <div style="font-size:0.84rem; color:#94A3B8; margin-top:3px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
