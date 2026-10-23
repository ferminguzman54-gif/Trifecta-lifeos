"""
Pruebas unitarias para el Motor de Puntuación Integral 'Trifecta Score',
la rotación inteligente Push/Pull/Legs y la serie de consistencia multitemporal (Sprint 5).
"""
from __future__ import annotations

from datetime import date, timedelta

from src.models.hub_models import TrifectaWeights
from src.services.trifecta_score_engine import (
    build_multitemporal_consistency_series,
    calculate_weighted_trifecta_score,
    compute_daily_finance_score,
    compute_daily_habit_score,
    compute_daily_workout_score,
    suggest_next_ppl_workout,
)


def test_compute_daily_habit_score_supports_partial_quantitative_progress() -> None:
    """
    Si un usuario tiene 1 hábito booleano completado (100%) y 1 hábito numérico al 50%
    (5,000 de 10,000 pasos), el habit_score del día debe ser 75.0%.
    """
    today = date(2026, 6, 15)
    habits = [
        {
            "id": "h-bool",
            "name": "Creatina 5g",
            "metric_type": "BOOLEAN",
            "daily_target_value": 1.0,
            "is_archived": False,
        },
        {
            "id": "h-num",
            "name": "10,000 Pasos",
            "metric_type": "NUMERIC",
            "daily_target_value": 10000.0,
            "is_archived": False,
        },
    ]
    logs = [
        {
            "habit_id": "h-bool",
            "log_date": today.isoformat(),
            "recorded_value": 1.0,
            "is_fulfilled": True,
        },
        {
            "habit_id": "h-num",
            "log_date": today.isoformat(),
            "recorded_value": 5000.0,
            "is_fulfilled": False,
        },
    ]
    score, completed, partial, total = compute_daily_habit_score(habits, logs, target_date=today)
    assert score == 75.0
    assert completed == 1
    assert partial == 1
    assert total == 2


def test_calculate_weighted_trifecta_score_default_40_35_25() -> None:
    """
    Verifica la ponderación 40% Hábitos + 35% Entrenamiento + 25% Finanzas:
    (80 * 0.40) + (100 * 0.35) + (90 * 0.25) = 32 + 35 + 22.5 = 89.5 (Nivel Élite).
    """
    score, tier_label, tier_color = calculate_weighted_trifecta_score(
        habit_score=80.0,
        workout_score=100.0,
        finance_score=90.0,
        weights=TrifectaWeights(habits_weight=0.40, workout_weight=0.35, finance_weight=0.25),
    )
    assert score == 89.5
    assert "ÉLITE" in tier_label
    assert tier_color == "#10B981"


def test_suggest_next_ppl_workout_rotates_push_to_pull_to_legs() -> None:
    """
    Si la última sesión registrada fue de PUSH (Empuje), el motor debe sugerir PULL (Tracción)
    para la jornada de hoy.
    """
    today = date(2026, 6, 15)
    exercises = [
        {"id": "ex-bench", "name": "Press de Banca", "primary_muscle": "chest"},
        {"id": "ex-row", "name": "Remo con Barra", "primary_muscle": "back"},
    ]
    routines = [
        {"id": "rt-push", "name": "Día A: Push (Pecho y Hombro)"},
        {"id": "rt-pull", "name": "Día B: Pull (Espalda y Bíceps)"},
    ]
    routine_items = [
        {"routine_id": "rt-push", "exercise_id": "ex-bench", "order_index": 1},
        {"routine_id": "rt-pull", "exercise_id": "ex-row", "order_index": 1},
    ]
    sessions = [
        {
            "id": "sess-1",
            "title": "Día A: Push (Pecho y Hombro)",
            "started_at": f"{(today - timedelta(days=1)).isoformat()}T18:00:00Z",
        }
    ]
    sets = [
        {
            "session_id": "sess-1",
            "exercise_id": "ex-bench",
            "set_number": 1,
            "weight_kg": 80.0,
            "reps": 10,
            "rpe": 8.0,
            "performed_at": f"{(today - timedelta(days=1)).isoformat()}T18:10:00Z",
        }
    ]

    suggestion = suggest_next_ppl_workout(
        user_id="u-1",
        routines=routines,
        routine_items=routine_items,
        sessions=sessions,
        sets=sets,
        exercises=exercises,
        reference_date=today,
    )
    assert suggestion.last_ppl_split == "PUSH"
    assert suggestion.next_ppl_split == "PULL"
    assert suggestion.recommended_routine_id == "rt-pull"
    assert len(suggestion.overload_targets) >= 1


def test_compute_daily_workout_and_finance_scores_and_consistency_series() -> None:
    """Verifica el cálculo de workout_score, finance_score y la serie multitemporal."""
    today = date(2026, 6, 15)
    sessions = [{"id": "s1", "started_at": f"{today.isoformat()}T10:00:00Z"}]
    w_score, w_done, w_7d = compute_daily_workout_score(sessions, [], target_date=today)
    assert w_done is True
    assert w_score == 100.0
    assert w_7d == 1

    accounts = [
        {
            "id": "acc-1",
            "name": "TDC Nu",
            "account_type": "credit_card",
            "current_balance": 4000.0,
            "credit_limit": 40000.0,
            "is_active": True,
        }
    ]
    categories = [
        {
            "id": "cat-1",
            "name": "Supermercado",
            "kind": "expense",
            "monthly_budget_limit": 10000.0,
        }
    ]
    transactions = [
        {
            "id": "tx-1",
            "account_id": "acc-1",
            "category_id": "cat-1",
            "tx_type": "expense",
            "amount": 1200.0,
            "tx_date": today.isoformat(),
        }
    ]
    f_score, b_status, today_exp, _, _ = compute_daily_finance_score(
        accounts, categories, transactions, target_date=today
    )
    assert f_score >= 85.0
    assert b_status == "OPTIMAL"
    assert today_exp == 1200.0

    consistency = build_multitemporal_consistency_series(
        habits=[],
        habit_logs=[],
        workout_sessions=sessions,
        workout_sets=[],
        accounts=accounts,
        categories=categories,
        transactions=transactions,
        days_back=14,
        reference_date=today,
    )
    assert len(consistency["series"]) == 14
    assert consistency["consistency_streak_days"] >= 1
