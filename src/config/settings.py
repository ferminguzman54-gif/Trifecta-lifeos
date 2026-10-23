"""
Carga segura de secretos (st.secrets / variables de entorno) y constantes globales
según 02_TRD_Requisitos_Tecnicos.md.
"""
from __future__ import annotations

import os
from typing import Any, Dict

import streamlit as st

APP_NAME: str = "TRIFECTA LifeOS"
APP_SUBTITLE: str = "Entrenamiento · Finanzas · Hábitos"
APP_VERSION: str = "1.0.0-sprint1"

# Persistencia de sesión móvil en navegador (CookieManager)
COOKIE_NAME: str = "trifecta_rt"
COOKIE_EXPIRY_DAYS: int = 30

# Destinos principales del Selector Segmentado Superior Fijo (03_Appflow_Flujo_Usuario.md)
NAV_DESTINATIONS: Dict[str, Dict[str, str]] = {
    "hub": {
        "key": "hub",
        "label": "⚡ Hub",
        "full_title": "Command Center",
        "accent": "#3B82F6",
    },
    "workout": {
        "key": "workout",
        "label": "🏋️ Entreno",
        "full_title": "Entrenamiento Físico",
        "accent": "#FF5500",
    },
    "finance": {
        "key": "finance",
        "label": "💳 Finanzas",
        "full_title": "Finanzas Personales",
        "accent": "#10B981",
    },
    "habits": {
        "key": "habits",
        "label": "🎯 Hábitos",
        "full_title": "Hábitos y Metas",
        "accent": "#8B5CF6",
    },
}

# Mapeo exacto de los 8 filtros temporales (02_TRD_Requisitos_Tecnicos.md §5.1)
TIMEFRAME_CONFIG: Dict[str, Dict[str, Any]] = {
    "1D": {"days": 1,   "freq": "H",     "label": "Diario (Hoy)"},
    "1W": {"days": 7,   "freq": "D",     "label": "Semanal (7d)"},
    "2W": {"days": 15,  "freq": "3D",    "label": "Quincenal (15d)"},
    "1M": {"days": 30,  "freq": "W-MON", "label": "Mensual (30d)"},
    "2M": {"days": 60,  "freq": "2W",    "label": "Bimestral (60d)"},
    "3M": {"days": 90,  "freq": "W-MON", "label": "Trimestral (90d)"},
    "6M": {"days": 180, "freq": "MS",    "label": "Semestral (6m)"},
    "1Y": {"days": 365, "freq": "MS",    "label": "Anual (12m)"},
}

# Etiquetas en español para los 14 grupos musculares del esquema SQL
MUSCLE_LABELS: Dict[str, str] = {
    "chest": "Pecho",
    "back_lats": "Espalda (Dorsales)",
    "back_upper": "Espalda Alta / Trapecio",
    "quads": "Cuádriceps",
    "hamstrings": "Isquiotibiales",
    "glutes": "Glúteos",
    "front_delts": "Hombro Anterior",
    "side_delts": "Hombro Lateral",
    "rear_delts": "Hombro Posterior",
    "biceps": "Bíceps",
    "triceps": "Tríceps",
    "calves": "Pantorrillas",
    "abs": "Abdominales",
    "forearms": "Antebrazos",
}

DEFAULT_FINANCE_CATEGORIES = [
    {"name": "Supermercado y Despensa", "kind": "expense", "monthly_budget_limit": 5000.0, "icon": "🛒", "color_hex": "#10B981", "is_essential": True},
    {"name": "Vivienda y Servicios", "kind": "expense", "monthly_budget_limit": 8000.0, "icon": "🏠", "color_hex": "#3B82F6", "is_essential": True},
    {"name": "Transporte y Gasolina", "kind": "expense", "monthly_budget_limit": 3000.0, "icon": "🚗", "color_hex": "#F59E0B", "is_essential": True},
    {"name": "Restaurantes y Café", "kind": "expense", "monthly_budget_limit": 2500.0, "icon": "🍽️", "color_hex": "#EC4899", "is_essential": False},
    {"name": "Salud, Gym y Suplementos", "kind": "expense", "monthly_budget_limit": 2000.0, "icon": "💪", "color_hex": "#FF5500", "is_essential": True},
    {"name": "Suscripciones y Digital", "kind": "expense", "monthly_budget_limit": 1000.0, "icon": "📱", "color_hex": "#8B5CF6", "is_essential": False},
    {"name": "Compras y Tecnología", "kind": "expense", "monthly_budget_limit": 3000.0, "icon": "🛍️", "color_hex": "#06B6D4", "is_essential": False},
    {"name": "Educación y Desarrollo", "kind": "expense", "monthly_budget_limit": 1500.0, "icon": "📚", "color_hex": "#6366F1", "is_essential": True},
    {"name": "Nómina / Sueldo Principal", "kind": "income", "monthly_budget_limit": 0.0, "icon": "💰", "color_hex": "#22C55E", "is_essential": True},
    {"name": "Proyectos / Honorarios", "kind": "income", "monthly_budget_limit": 0.0, "icon": "🚀", "color_hex": "#10B981", "is_essential": False},
    {"name": "Rendimientos y Cashback", "kind": "income", "monthly_budget_limit": 0.0, "icon": "📈", "color_hex": "#06B6D4", "is_essential": False},
    {"name": "Pago de Tarjeta / Transferencia", "kind": "transfer", "monthly_budget_limit": 0.0, "icon": "🔄", "color_hex": "#94A3B8", "is_essential": True},
]


def _get_secret(key: str, default: str = "") -> str:
    """Obtiene una variable desde st.secrets o variables de entorno de forma segura."""
    try:
        if key in st.secrets:
            val = str(st.secrets[key]).strip()
            if val:
                return val
    except Exception:
        pass
    return os.environ.get(key, default).strip()


def get_supabase_url() -> str:
    """Retorna SUPABASE_URL configurado en secrets.toml o entorno."""
    return _get_secret("SUPABASE_URL", "")


def get_supabase_key() -> str:
    """Retorna SUPABASE_ANON_KEY (o SUPABASE_KEY como alias compatible)."""
    key = _get_secret("SUPABASE_ANON_KEY", "")
    if not key:
        key = _get_secret("SUPABASE_KEY", "")
    return key


def is_supabase_configured() -> bool:
    """Verifica que las credenciales de Supabase estén configuradas y no sean el placeholder."""
    url = get_supabase_url()
    key = get_supabase_key()
    if not url or not key:
        return False
    if "tu-proyecto-id.supabase.co" in url or key.startswith("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."):
        return False
    return True
