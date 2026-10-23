"""
Pruebas unitarias exhaustivas de rachas, progreso parcial tripartito
(PENDING 0%, PARTIAL >0% y <100%, COMPLETED >=100%), promedio diario semanal (7d),
sumatoria acumulada mensual, adherencia de 30 días, heatmap de 90 días
y avance de metas personales (goal_milestones + hábitos vinculados).
"""
from datetime import date, timedelta

from src.models.habit_models import HabitModel
from src.services.habit_streak_engine import (
    calculate_completion_percentage,
    calculate_goal_progress_pct,
    calculate_habit_analytics,
    calculate_monthly_accumulated_sum,
    calculate_weekly_daily_average,
    determine_habit_daily_status,
    evaluate_habit_fulfillment,
)


def test_habit_model_validation() -> None:
    habit = HabitModel(
        user_id="00000000-0000-0000-0000-000000000001",
        name="Hidratación",
        metric_type="NUMERIC",
        unit_label="Litros",
        daily_target_value=3.0,
    )
    assert habit.metric_type == "NUMERIC"
    assert habit.daily_target_value == 3.0


def test_tripartite_status_and_partial_progress_on_numeric_habit() -> None:
    # Caso 1: Pendiente (0%)
    assert calculate_completion_percentage("NUMERIC", 0.0, 10000.0) == 0.0
    assert determine_habit_daily_status("NUMERIC", 0.0, 10000.0) == "PENDING"
    assert evaluate_habit_fulfillment("NUMERIC", 0.0, 10000.0) is False

    # Caso 2: En progreso / Parcial (ej. 9,999 de 10,000 pasos = 99.99%)
    assert calculate_completion_percentage("NUMERIC", 9999.0, 10000.0) == 99.99
    assert determine_habit_daily_status("NUMERIC", 9999.0, 10000.0) == "PARTIAL"
    assert evaluate_habit_fulfillment("NUMERIC", 9999.0, 10000.0) is False

    # Caso 3: Completado (>= 100%)
    assert calculate_completion_percentage("NUMERIC", 10000.0, 10000.0) == 100.0
    assert determine_habit_daily_status("NUMERIC", 10000.0, 10000.0) == "COMPLETED"
    assert evaluate_habit_fulfillment("NUMERIC", 10000.0, 10000.0) is True


def test_weekly_daily_average_and_monthly_accumulated_sum() -> None:
    ref_day = date(2026, 10, 21)
    habit = {
        "id": "hab-steps",
        "metric_type": "NUMERIC",
        "daily_target_value": 10000.0,
        "frequency_days_per_week": 7,
    }

    # Registros dentro del mes corriente (Octubre 2026):
    # - Hace 10 días (11 Oct, fuera de la ventana de 7d pero dentro del mes): 8,000 pasos
    # - Últimos 7 días (15 al 21 Oct): 7 días con 10,000 pasos = 70,000 en 7d
    logs = [
        {"habit_id": "hab-steps", "log_date": "2026-10-11", "recorded_value": 8000.0},
    ]
    for offset in range(7):
        logs.append(
            {
                "habit_id": "hab-steps",
                "log_date": (ref_day - timedelta(days=offset)).isoformat(),
                "recorded_value": 10000.0,
            }
        )

    avg_7d, active_7d = calculate_weekly_daily_average(logs, "hab-steps", reference_date=ref_day)
    assert avg_7d == 10000.0
    assert active_7d == 7

    month_sum, active_month = calculate_monthly_accumulated_sum(logs, "hab-steps", reference_date=ref_day)
    assert month_sum == 78000.0
    assert active_month == 8

    analytics = calculate_habit_analytics(habit, logs, reference_date=ref_day)
    assert analytics.weekly_daily_avg_7d == 10000.0
    assert analytics.monthly_accumulated_sum == 78000.0
    assert analytics.today_status == "COMPLETED"


def test_calculate_habit_analytics_streaks_and_heatmap() -> None:
    ref_day = date(2026, 10, 20)
    habit = {
        "id": "hab-1",
        "metric_type": "NUMERIC",
        "daily_target_value": 3.0,
        "frequency_days_per_week": 7,
    }

    logs = []
    for offset in [24, 23, 22, 21, 20]:
        logs.append(
            {
                "habit_id": "hab-1",
                "log_date": (ref_day - timedelta(days=offset)).isoformat(),
                "recorded_value": 3.0,
                "is_fulfilled": True,
            }
        )
    for offset in [2, 1, 0]:
        logs.append(
            {
                "habit_id": "hab-1",
                "log_date": (ref_day - timedelta(days=offset)).isoformat(),
                "recorded_value": 3.2,
                "is_fulfilled": True,
            }
        )

    analytics = calculate_habit_analytics(habit, logs, reference_date=ref_day)

    assert analytics.current_streak == 3
    assert analytics.best_streak == 5
    assert analytics.fulfilled_days_30d == 8
    assert analytics.today_fulfilled is True
    assert len(analytics.heatmap_90d) == 90
    assert analytics.heatmap_90d[-1].is_fulfilled is True
    assert analytics.heatmap_90d[-1].intensity == 1.0


def test_calculate_goal_progress_pct_with_milestones_and_habits() -> None:
    milestones = [
        {"id": "m1", "is_completed": True},
        {"id": "m2", "is_completed": True},
        {"id": "m3", "is_completed": False},
    ]
    assert calculate_goal_progress_pct(milestones, []) == 66.7
    assert calculate_goal_progress_pct(milestones, [80.0]) == 70.0
    all_done = [{"id": "m1", "is_completed": True}, {"id": "m2", "is_completed": True}]
    assert calculate_goal_progress_pct(all_done, [50.0]) == 100.0
