"""
Esquemas Pydantic para ejercicios, rutinas, sesiones, series (con RPE/RIR y tiempos
de descanso objetivo/real), recomendaciones de sobrecarga progresiva, analítica de
descanso/densidad y conector base de nutrición.
Implementado según 01_PRD (§2), 02_TRD (§5.1), 05_Backend_Schema (§1) y Sprint 3.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

EquipmentType = Literal[
    "barbell", "dumbbell", "machine", "cable", "bodyweight", "kettlebell", "other"
]
MuscleGroup = Literal[
    "chest",
    "back_lats",
    "back_upper",
    "quads",
    "hamstrings",
    "glutes",
    "front_delts",
    "side_delts",
    "rear_delts",
    "biceps",
    "triceps",
    "calves",
    "abs",
    "forearms",
]
SetType = Literal["warmup", "working", "dropset", "failure"]
GoalPhase = Literal["cut", "maintenance", "lean_bulk"]
ProgressionState = Literal[
    "UP_WEIGHT_DOWN_REPS",
    "KEEP_WEIGHT_UP_REPS",
    "DOWN_WEIGHT_UP_REPS",
    "UP_WEIGHT_STRENGTH_SHIFT",
    "FIRST_SESSION",
]

EQUIPMENT_LABELS: Dict[str, str] = {
    "barbell": "Barra Olímpica / EZ",
    "dumbbell": "Mancuernas",
    "machine": "Máquina",
    "cable": "Polea / Cable",
    "bodyweight": "Peso Corporal / Lastre",
    "kettlebell": "Pesa Rusa (Kettlebell)",
    "other": "Otro / Libre",
}

SET_TYPE_LABELS: Dict[str, Dict[str, str]] = {
    "warmup": {"short": "W · Calentamiento", "code": "W", "color": "#94A3B8"},
    "working": {"short": "N · Serie Efectiva", "code": "N", "color": "#FF5500"},
    "dropset": {"short": "D · Dropset", "code": "D", "color": "#8B5CF6"},
    "failure": {"short": "F · Al Fallo", "code": "F", "color": "#EF4444"},
}

REST_PRESETS_SECONDS: List[int] = [60, 90, 120, 180]

WeeklyPlanStatus = Literal["planned", "completed", "rest"]

WEEKLY_PLAN_STATUS_LABELS: Dict[str, Dict[str, str]] = {
    "planned": {"label": "📅 Planificado", "color": "#3B82F6", "bg": "#3B82F61F"},
    "completed": {"label": "✅ Completado", "color": "#10B981", "bg": "#10B9811F"},
    "rest": {"label": "🧘 Descanso", "color": "#94A3B8", "bg": "#94A3B81F"},
}

SPANISH_WEEKDAYS: List[str] = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
]

WORKOUT_FOCUS_PRESETS: List[str] = [
    "Empuje · Pecho, Hombro y Tríceps (Push)",
    "Tirón · Espalda y Bíceps (Pull)",
    "Pierna Hipertrofia y Glúteo (Legs)",
    "Torso Completo (Upper Body)",
    "Tren Inferior Fuerza (Lower Body)",
    "Pecho y Espalda (Antagonistas)",
    "Hombros y Brazos (Delts & Arms)",
    "Cuerpo Completo (Full Body)",
    "Cardio / Acondicionamiento y Core",
    "Descanso Activo / Movilidad",
]


class ExerciseModel(BaseModel):
    id: Optional[str] = None
    user_id: Optional[str] = None
    name: str = Field(..., min_length=2, max_length=120)
    equipment: EquipmentType = "barbell"
    primary_muscle: MuscleGroup
    secondary_muscles: List[MuscleGroup] = Field(default_factory=list)
    movement_pattern: Literal["compound", "isolation"] = "compound"
    notes: str = ""


class WorkoutWeeklyPlanModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    plan_date: date
    day_of_week: int = Field(default=0, ge=0, le=6)
    focus_title: str = Field(default="Entrenamiento", min_length=1, max_length=120)
    routine_id: Optional[str] = None
    status: WeeklyPlanStatus = "planned"
    notes: str = ""


class WorkoutRoutineModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    name: str = Field(..., min_length=2, max_length=100)
    description: str = ""
    accent_color: str = "#FF5500"
    display_order: int = 1
    is_archived: bool = False


class WorkoutRoutineItemModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    routine_id: str
    exercise_id: str
    order_index: int = 1
    target_sets: int = Field(default=3, ge=1, le=15)
    target_rep_min: int = Field(default=8, ge=1)
    target_rep_max: int = Field(default=12, ge=1)
    target_rpe: float = Field(default=8.0, ge=5.0, le=10.0)
    progression_step_kg: float = Field(default=2.5, gt=0)
    default_rest_seconds: int = Field(default=90, ge=10, le=900)
    notes: str = ""


class WorkoutSessionModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    routine_id: Optional[str] = None
    session_title: str = Field(..., min_length=1, max_length=120)
    started_at: datetime
    ended_at: Optional[datetime] = None
    perceived_fatigue: Optional[int] = Field(default=None, ge=1, le=10)
    bodyweight_kg: Optional[float] = Field(default=None, gt=0)
    notes: str = ""


class WorkoutSetModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    session_id: str
    exercise_id: str
    set_number: int = Field(..., ge=1)
    set_type: SetType = "working"
    weight_kg: float = Field(default=0.0, ge=0.0)
    reps: int = Field(..., ge=0)
    rpe: float = Field(default=8.0, ge=5.0, le=10.0)
    rir: float = Field(default=2.0, ge=0.0, le=5.0)
    rest_target_seconds: int = Field(default=90, ge=0)
    rest_actual_seconds: int = Field(default=0, ge=0)
    is_pr: bool = False
    notes: str = ""
    performed_at: Optional[datetime] = None


class ProgressionRecommendation(BaseModel):
    exercise_id: str
    state: ProgressionState
    badge_label: str
    badge_color: str
    badge_icon: str
    headline: str
    explanation: str
    suggested_weight_kg: float
    suggested_reps: int
    suggested_rpe: float = 8.0
    suggested_rest_seconds: int = 90
    last_session_summary: str = "Sin sesiones previas registradas"
    estimated_1rm_epley: float = 0.0
    estimated_1rm_brzycki: float = 0.0
    relative_intensity_pct: float = 0.0


class RestAndDensityMetrics(BaseModel):
    total_working_sets: int = 0
    avg_rest_actual_seconds: float = 0.0
    avg_rest_target_seconds: float = 90.0
    rest_compliance_pct: float = 100.0
    work_to_rest_ratio_label: str = "1 : 3.0"
    tonnage_per_min_kg: float = 0.0
    rest_rpe_correlation: Optional[float] = None
    correlation_insight: str = "Registra más series con descanso para auditar la correlación descanso vs. RPE."


class NutritionTargetModel(BaseModel):
    user_id: str
    goal_phase: GoalPhase = "maintenance"
    daily_calories_target: int = 2400
    protein_g_target: int = 160
    carbs_g_target: int = 250
    fat_g_target: int = 75


class NutritionDailyLogModel(BaseModel):
    user_id: str
    log_date: date
    calories_kcal: int = 0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    water_ml: int = 0
    bodyweight_kg: Optional[float] = None
    notes: str = ""
