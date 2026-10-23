"""
Esquemas Pydantic para hábitos editables, registros diarios, metas personales e hitos
según 05_Backend_Schema_Supabase.md (§3) y 01_PRD_Requisitos_Producto.md (§4).
Incluye estados tripartitos (PENDING, PARTIAL, COMPLETED) y analítica cuantitativa (7d avg / mes).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

MetricType = Literal["BOOLEAN", "NUMERIC", "DURATION", "RATING"]
GoalStatus = Literal["active", "completed", "paused", "archived"]
HabitDailyStatus = Literal["PENDING", "PARTIAL", "COMPLETED"]

HABIT_STATUS_LABELS = {
    "PENDING": "Pendiente",
    "PARTIAL": "En progreso / Parcial",
    "COMPLETED": "Completado",
}

LIFE_AREAS: List[str] = [
    "Desarrollo Personal",
    "Salud y Fitness",
    "Finanzas y Patrimonio",
    "Carrera y Negocios",
    "Idiomas y Educación",
    "Mentalidad y Bienestar",
]

HABIT_COLOR_PRESETS: List[dict] = [
    {"label": "Violeta Hábitos", "hex": "#8B5CF6"},
    {"label": "Índigo Eléctrico", "hex": "#6366F1"},
    {"label": "Esmeralda Éxito", "hex": "#10B981"},
    {"label": "Naranja Energía", "hex": "#FF5500"},
    {"label": "Cian Nutrición", "hex": "#06B6D4"},
    {"label": "Azul Enfoque", "hex": "#3B82F6"},
    {"label": "Ámbar Solar", "hex": "#F59E0B"},
    {"label": "Rosa Neón", "hex": "#EC4899"},
]

HABIT_ICON_PRESETS: List[str] = [
    "⚡", "💧", "📚", "🧘", "💪", "🧠", "🇬🇧", "💤", "🥗", "💊", "🎯", "✍️", "🚶", "📵", "💰"
]


class PersonalGoalModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    title: str = Field(..., min_length=2, max_length=140)
    life_area: str = "Desarrollo Personal"
    description: str = ""
    start_date: date = Field(default_factory=date.today)
    target_date: date
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    status: GoalStatus = "active"
    display_order: int = 1


class GoalMilestoneModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    goal_id: str
    title: str = Field(..., min_length=1, max_length=160)
    step_order: int = 1
    due_date: Optional[date] = None
    is_completed: bool = False
    completed_at: Optional[datetime] = None


class HabitModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    linked_goal_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    icon: str = "⚡"
    color_hex: str = "#8B5CF6"
    metric_type: MetricType = "BOOLEAN"
    unit_label: str = "check"
    daily_target_value: float = Field(default=1.0, gt=0.0)
    frequency_days_per_week: int = Field(default=7, ge=1, le=7)
    display_order: int = 1
    is_pinned: bool = False
    is_archived: bool = False


class HabitLogModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    habit_id: str
    log_date: date = Field(default_factory=date.today)
    recorded_value: float = Field(default=1.0, ge=0.0)
    is_fulfilled: bool = True
    notes: str = ""


class HeatmapCell(BaseModel):
    log_date: date
    date_label: str
    weekday: int  # 0 = Lunes .. 6 = Domingo
    recorded_value: float = 0.0
    completion_pct: float = 0.0  # (valor_actual / meta) * 100
    daily_status: HabitDailyStatus = "PENDING"
    is_fulfilled: bool = False
    intensity: float = 0.0  # 0.0 a 1.0


class HabitAnalytics(BaseModel):
    habit_id: str
    current_streak: int = 0
    best_streak: int = 0
    adherence_30d_pct: float = 0.0
    fulfilled_days_30d: int = 0
    partial_days_30d: int = 0
    today_value: float = 0.0
    today_fulfilled: bool = False
    today_status: HabitDailyStatus = "PENDING"
    today_status_label: str = "Pendiente"
    today_progress_pct: float = 0.0        # Porcentaje exacto (valor_actual / meta) * 100
    today_bar_pct: float = 0.0             # Porcentaje acotado [0.0, 100.0] para barra visual
    weekly_daily_avg_7d: float = 0.0       # Promedio diario alcanzado en los últimos 7 días
    weekly_active_days_7d: int = 0         # Días con registro > 0 en los últimos 7 días
    monthly_accumulated_sum: float = 0.0   # Sumatoria acumulada en el mes corriente
    monthly_active_days: int = 0           # Días con registro > 0 en el mes corriente
    heatmap_90d: List[HeatmapCell] = Field(default_factory=list)
