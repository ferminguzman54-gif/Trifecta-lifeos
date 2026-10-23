"""
Modelos Pydantic para el Command Center (Hub), el Motor de Puntuación Integral
'Trifecta Score', los Snapshots Diarios (`daily_life_snapshots`) y la sugerencia
inteligente de rutina Push/Pull/Legs con sobrecarga progresiva (Sprint 5).
"""
from __future__ import annotations

from datetime import date as DateType
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

BudgetStatusType = Literal["OPTIMAL", "WARNING", "CRITICAL"]
PPLSplitType = Literal["PUSH", "PULL", "LEGS"]


class TrifectaWeights(BaseModel):
    """Balance configurable de pesos para el cálculo del Trifecta Score diario."""
    habits_weight: float = Field(default=0.40, ge=0.0, le=1.0)
    workout_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    finance_weight: float = Field(default=0.25, ge=0.0, le=1.0)

    def normalized(self) -> "TrifectaWeights":
        total = self.habits_weight + self.workout_weight + self.finance_weight
        if total <= 0:
            return TrifectaWeights(habits_weight=0.40, workout_weight=0.35, finance_weight=0.25)
        return TrifectaWeights(
            habits_weight=round(self.habits_weight / total, 4),
            workout_weight=round(self.workout_weight / total, 4),
            finance_weight=round(self.finance_weight / total, 4),
        )


class DailyLifeSnapshotModel(BaseModel):
    """Representa una fila en `public.daily_life_snapshots`."""
    id: Optional[str] = None
    user_id: str
    date: DateType = Field(default_factory=DateType.today)
    habit_score: float = Field(default=0.0, ge=0.0, le=100.0)
    workout_score: float = Field(default=0.0, ge=0.0, le=100.0)
    finance_score: float = Field(default=0.0, ge=0.0, le=100.0)
    workout_completed: bool = False
    budget_status: BudgetStatusType = "OPTIMAL"
    trifecta_score: float = Field(default=0.0, ge=0.0, le=100.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NextWorkoutSuggestion(BaseModel):
    """Sugerencia de próxima sesión según secuencia Push/Pull/Legs y sobrecarga progresiva."""
    next_ppl_split: PPLSplitType = "PUSH"
    split_title: str = "PUSH · Empuje (Pecho, Hombro y Tríceps)"
    split_subtitle: str = "Inicia tu ciclo de fuerza priorizando compuestos de empuje."
    last_ppl_split: Optional[str] = None
    last_session_date: Optional[DateType] = None
    days_since_last_workout: Optional[int] = None
    workouts_last_7d: int = 0
    workout_completed_today: bool = False
    recommended_routine_id: Optional[str] = None
    recommended_routine_name: Optional[str] = None
    overload_targets: List[Dict[str, Any]] = Field(default_factory=list)


class HubDailyPulse(BaseModel):
    """Estado ejecutivo consolidado del día para el Command Center."""
    target_date: DateType
    trifecta_score: float
    tier_label: str
    tier_color: str
    habit_score: float
    workout_score: float
    finance_score: float
    workout_completed: bool
    budget_status: BudgetStatusType
    consistency_streak_days: int = 0
    best_consistency_streak_days: int = 0
    habits_completed_today: int = 0
    habits_partial_today: int = 0
    habits_total_active: int = 0
    today_expenses_amount: float = 0.0
    liquid_balance: float = 0.0
    cc_debt: float = 0.0
    budget_remaining_total: float = 0.0
    budget_used_pct: float = 0.0
    next_card_alert_text: str = "Sin vencimientos próximos en 14 días"
    next_card_alert_days: Optional[int] = None
    next_card_alert_color: str = "#10B981"
    workout_suggestion: NextWorkoutSuggestion
    weights: TrifectaWeights
