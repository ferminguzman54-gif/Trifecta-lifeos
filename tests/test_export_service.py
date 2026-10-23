"""
Pruebas unitarias para el Motor de Exportación (CSV / Life Snapshot JSON),
sincronización de ponderaciones y protección de confirmación de borrado (Sprint 6).
"""
from __future__ import annotations

from src.services.export_service import (
    build_consolidated_life_snapshot_dict,
    build_finances_export_csv,
    build_habits_export_csv,
    build_workouts_export_csv,
    purge_user_test_records,
)


def test_build_habits_workouts_and_finances_csvs() -> None:
    """Verifica que los 3 generadores CSV produzcan encabezados y filas válidas con BOM UTF-8."""
    habits = [
        {
            "id": "h-1",
            "name": "Pasos Diarios",
            "metric_type": "NUMERIC",
            "daily_target_value": 10000.0,
            "unit_label": "pasos",
        }
    ]
    habit_logs = [
        {
            "habit_id": "h-1",
            "log_date": "2026-06-20",
            "recorded_value": 8500.0,
            "is_fulfilled": False,
            "notes": "Caminata vespertina",
        }
    ]
    habits_csv = build_habits_export_csv(habits, habit_logs)
    assert "Pasos Diarios" in habits_csv
    assert "PARTIAL" in habits_csv
    assert "85.0" in habits_csv

    sessions = [{"id": "s-1", "session_title": "Push Pesado"}]
    exercises = [
        {
            "id": "e-1",
            "name": "Press de Banca",
            "primary_muscle": "chest",
            "equipment": "barbell",
        }
    ]
    sets = [
        {
            "session_id": "s-1",
            "exercise_id": "e-1",
            "set_number": 1,
            "set_type": "working",
            "weight_kg": 100.0,
            "reps": 8,
            "rpe": 8.5,
            "rir": 1.5,
            "rest_target_seconds": 120,
            "rest_actual_seconds": 115,
            "is_pr": True,
            "performed_at": "2026-06-20T18:00:00Z",
        }
    ]
    workouts_csv = build_workouts_export_csv(sessions, sets, exercises)
    assert "Press de Banca" in workouts_csv
    assert "800.00" in workouts_csv  # Tonnage 100 * 8

    accounts = [{"id": "a-1", "name": "TDC Nu", "institution_name": "Nu México"}]
    categories = [{"id": "c-1", "name": "Supermercado"}]
    txs = [
        {
            "id": "t-1",
            "account_id": "a-1",
            "category_id": "c-1",
            "tx_type": "expense",
            "merchant_or_concept": "HEB",
            "amount": 1450.50,
            "cashback_earned": 21.76,
            "msi_months": 3,
            "tags": ["despensa", "hogar"],
            "tx_date": "2026-06-20",
        }
    ]
    finances_csv = build_finances_export_csv(accounts, categories, txs)
    assert "HEB" in finances_csv
    assert "1450.50" in finances_csv
    assert "despensa,hogar" in finances_csv


def test_build_consolidated_life_snapshot_dict_and_purge_guard() -> None:
    """Verifica la estructura del Life Snapshot JSON y el candado de confirmación 'BORRAR'."""
    snap = build_consolidated_life_snapshot_dict(
        profile={"id": "u-1", "email": "user@trifecta.app", "full_name": "Fermi", "weight_habits": 45.0},
        habits=[{"id": "h-1"}],
        habit_logs=[],
        goals=[],
        milestones=[],
        routines=[],
        routine_items=[],
        workout_sessions=[],
        workout_sets=[],
        accounts=[],
        categories=[],
        subscriptions=[],
        transactions=[],
        daily_snapshots=[],
    )
    assert snap["backup_metadata"]["schema_format"] == "trifecta_life_snapshot_v1"
    assert snap["user_profile_and_settings"]["trifecta_weights"]["weight_habits"] == 45.0
    assert snap["summary_counts"]["habits_count"] == 1

    ok, msg = purge_user_test_records("u-1", "borrar")
    assert ok is False
    assert "BORRAR" in msg
