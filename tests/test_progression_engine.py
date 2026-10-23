"""
Pruebas unitarias exhaustivas del motor de sobrecarga progresiva (4 reglas PRD §2.3),
fórmulas 1RM (Epley y Brzycki), analítica de descanso/densidad y agregación de volumen
ponderado (1.0 primario / 0.5 secundario) en los 8 horizontes temporales (1D a 1Y + YTD).
"""
from datetime import datetime, timedelta, timezone

from src.config.settings import TIMEFRAME_CONFIG
from src.services.progression_engine import (
    calculate_brzycki_1rm,
    calculate_epley_1rm,
    calculate_multitemporal_volume,
    calculate_relative_intensity_pct,
    calculate_rest_and_density_metrics,
    evaluate_progression_from_sessions,
)


def test_timeframe_config_has_eight_windows() -> None:
    expected_keys = {"1D", "1W", "2W", "1M", "2M", "3M", "6M", "1Y"}
    assert set(TIMEFRAME_CONFIG.keys()) == expected_keys


def test_epley_and_brzycki_1rm_formulas() -> None:
    # 100 kg x 10 reps:
    # Epley = 100 * (1 + 10/30) = 133.33 kg
    # Brzycki = 100 * (36 / 27) = 133.33 kg
    assert calculate_epley_1rm(100.0, 10) == 133.33
    assert calculate_brzycki_1rm(100.0, 10) == 133.33
    assert calculate_relative_intensity_pct(100.0, 133.33) == 75.0


def test_progression_rule_1_up_weight_down_reps() -> None:
    # Dominó el tope del rango (12, 12, 12 en rango 8-12) con RPE <= 8.5
    last_session = [
        {"set_type": "working", "weight_kg": 80.0, "reps": 12, "rpe": 8.0},
        {"set_type": "working", "weight_kg": 80.0, "reps": 12, "rpe": 8.0},
        {"set_type": "working", "weight_kg": 80.0, "reps": 12, "rpe": 8.5},
    ]
    rec = evaluate_progression_from_sessions(
        session_groups=[last_session],
        exercise_id="ex-bench",
        target_rep_min=8,
        target_rep_max=12,
        target_rpe=8.0,
        progression_step_kg=2.5,
    )
    assert rec.state == "UP_WEIGHT_DOWN_REPS"
    assert rec.suggested_weight_kg == 82.5
    assert rec.suggested_reps == 8


def test_progression_rule_2_keep_weight_up_reps() -> None:
    # Logró entre 8 y 11 reps con RPE <= 9.0 -> Mantener peso y subir repeticiones
    last_session = [
        {"set_type": "working", "weight_kg": 80.0, "reps": 9, "rpe": 8.0},
        {"set_type": "working", "weight_kg": 80.0, "reps": 9, "rpe": 8.5},
        {"set_type": "working", "weight_kg": 80.0, "reps": 9, "rpe": 8.5},
    ]
    rec = evaluate_progression_from_sessions(
        session_groups=[last_session],
        exercise_id="ex-bench",
        target_rep_min=8,
        target_rep_max=12,
        target_rpe=8.0,
        progression_step_kg=2.5,
    )
    assert rec.state == "KEEP_WEIGHT_UP_REPS"
    assert rec.suggested_weight_kg == 80.0
    assert rec.suggested_reps == 10


def test_progression_rule_3_down_weight_up_reps_on_fatigue() -> None:
    # Quedó por debajo de target_rep_min (6 reps < 8) o RPE >= 9.5 con caída > 20%
    last_session = [
        {"set_type": "working", "weight_kg": 80.0, "reps": 10, "rpe": 9.5},
        {"set_type": "working", "weight_kg": 80.0, "reps": 8, "rpe": 9.5},
        {"set_type": "working", "weight_kg": 80.0, "reps": 7, "rpe": 10.0},
    ]
    rec = evaluate_progression_from_sessions(
        session_groups=[last_session],
        exercise_id="ex-bench",
        target_rep_min=8,
        target_rep_max=12,
        target_rpe=8.0,
        progression_step_kg=2.5,
    )
    assert rec.state == "DOWN_WEIGHT_UP_REPS"
    assert rec.suggested_weight_kg < 80.0
    assert rec.suggested_reps == 14


def test_progression_rule_4_up_weight_strength_shift_on_plateau() -> None:
    # 3 sesiones consecutivas repitiendo exactamente 80 kg x 9 reps sin avanzar
    stagnant_session = [
        {"set_type": "working", "weight_kg": 80.0, "reps": 9, "rpe": 8.5},
        {"set_type": "working", "weight_kg": 80.0, "reps": 9, "rpe": 8.5},
    ]
    rec = evaluate_progression_from_sessions(
        session_groups=[stagnant_session, stagnant_session, stagnant_session],
        exercise_id="ex-bench",
        target_rep_min=8,
        target_rep_max=12,
        target_rpe=8.0,
        progression_step_kg=2.5,
    )
    assert rec.state == "UP_WEIGHT_STRENGTH_SHIFT"
    assert rec.suggested_weight_kg > 80.0
    assert rec.suggested_reps == 6


def test_weighted_muscle_volume_and_warmup_exclusion() -> None:
    now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    exercises_by_id = {
        "ex-bench": {
            "id": "ex-bench",
            "name": "Press de Banca",
            "primary_muscle": "chest",
            "secondary_muscles": ["triceps", "front_delts"],
        }
    }
    # 1 serie warmup (0.0x) + 4 series working (4.0x chest, 2.0x triceps, 2.0x front_delts)
    sets = [
        {
            "exercise_id": "ex-bench",
            "set_type": "warmup",
            "weight_kg": 50.0,
            "reps": 10,
            "performed_at": (now - timedelta(hours=2)).isoformat(),
        }
    ]
    for _ in range(4):
        sets.append(
            {
                "exercise_id": "ex-bench",
                "set_type": "working",
                "weight_kg": 100.0,
                "reps": 10,
                "performed_at": (now - timedelta(hours=1)).isoformat(),
            }
        )

    vol = calculate_multitemporal_volume(
        sets_records=sets,
        exercises_by_id=exercises_by_id,
        timeframe_code="1W",
        metric_mode="effective_sets",
        reference_now=now,
    )
    by_m = {m["muscle_code"]: m["effective_sets"] for m in vol["by_muscle"]}
    assert by_m["chest"] == 4.0
    assert by_m["triceps"] == 2.0
    assert by_m["front_delts"] == 2.0


def test_rest_and_density_metrics_and_correlation() -> None:
    sets = [
        {"set_type": "working", "weight_kg": 100.0, "reps": 10, "rpe": 9.5, "rest_target_seconds": 120, "rest_actual_seconds": 45},
        {"set_type": "working", "weight_kg": 100.0, "reps": 10, "rpe": 8.5, "rest_target_seconds": 120, "rest_actual_seconds": 90},
        {"set_type": "working", "weight_kg": 100.0, "reps": 10, "rpe": 7.5, "rest_target_seconds": 120, "rest_actual_seconds": 150},
    ]
    metrics = calculate_rest_and_density_metrics(sets)
    assert metrics.total_working_sets == 3
    assert metrics.avg_rest_actual_seconds == 95.0
    assert metrics.rest_rpe_correlation is not None
    assert metrics.rest_rpe_correlation < -0.90
