"""
Motor de Configuración de Perfil, Respaldo / Exportación de Datos (CSV y Life Snapshot JSON)
y Limpieza Segura de Registros de Prueba (Sprint 6).
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
from typing import Any, Dict, List, Tuple

import streamlit as st

from src.auth.supabase_client import get_supabase_client
from src.config.settings import APP_NAME, APP_VERSION
from src.services.card_advisor_engine import (
    clear_finance_cache,
    fetch_finance_accounts,
    fetch_finance_categories,
    fetch_finance_subscriptions,
    fetch_finance_transactions,
)
from src.services.habit_streak_engine import (
    clear_habits_cache,
    fetch_goal_milestones,
    fetch_habit_logs,
    fetch_habits,
    fetch_personal_goals,
)
from src.services.progression_engine import (
    calculate_epley_1rm,
    clear_workout_cache,
    fetch_exercises_catalog,
    fetch_workout_routine_items,
    fetch_workout_routines,
    fetch_workout_sessions,
    fetch_workout_sets,
)
from src.services.trifecta_score_engine import (
    clear_hub_snapshots_cache,
    fetch_daily_snapshots,
)


# ============================================================================
# 1. GESTIÓN REACTIVA DE PERFIL, UNIDADES Y PONDERACIÓN DEL TRIFECTA SCORE
# ============================================================================


def sync_profile_weights_to_session(profile: Dict[str, Any]) -> None:
    """Sincroniza las ponderaciones del perfil hacia `st.session_state['trifecta_weights']`."""
    w_h = float(profile.get("weight_habits") or 40.0)
    w_w = float(profile.get("weight_workouts") or 35.0)
    w_f = float(profile.get("weight_finances") or 25.0)
    total = w_h + w_w + w_f
    if total <= 0:
        w_h, w_w, w_f = 40.0, 35.0, 25.0
    else:
        w_h = round((w_h / total) * 100.0, 1)
        w_w = round((w_w / total) * 100.0, 1)
        w_f = round(100.0 - w_h - w_w, 1)

    st.session_state["trifecta_weights"] = {
        "habits": w_h,
        "workout": w_w,
        "finance": w_f,
    }


def update_user_profile_settings(
    user_id: str,
    full_name: str,
    alias: str,
    preferred_currency: str,
    weight_unit: str,
    date_format: str,
    weight_habits: float,
    weight_workouts: float,
    weight_finances: float,
) -> Tuple[bool, str]:
    """
    Actualiza el perfil y las preferencias del usuario en `public.profiles`
    y propaga los cambios de forma reactiva a `st.session_state`.
    """
    name_clean = (full_name or "").strip() or "Usuario Trifecta"
    alias_clean = (alias or "").strip()
    curr_clean = (preferred_currency or "MXN").strip().upper()
    unit_clean = "lb" if str(weight_unit).lower() == "lb" else "kg"
    fmt_clean = date_format if date_format in ("DD/MM/YYYY", "YYYY-MM-DD", "MM/DD/YYYY") else "DD/MM/YYYY"

    # Normalizar pesos para que sumen exactamente 100.0%
    raw_total = max(1.0, float(weight_habits) + float(weight_workouts) + float(weight_finances))
    norm_habits = round((float(weight_habits) / raw_total) * 100.0, 2)
    norm_workouts = round((float(weight_workouts) / raw_total) * 100.0, 2)
    norm_finances = round(max(0.0, 100.0 - norm_habits - norm_workouts), 2)

    full_payload = {
        "full_name": name_clean,
        "alias": alias_clean,
        "preferred_currency": curr_clean,
        "weight_unit": unit_clean,
        "date_format": fmt_clean,
        "weight_habits": norm_habits,
        "weight_workouts": norm_workouts,
        "weight_finances": norm_finances,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        access_token = st.session_state.get("access_token") or ""
        if user_id and access_token:
            client = get_supabase_client(access_token=access_token)
            try:
                client.table("profiles").update(full_payload).eq("id", user_id).execute()
            except Exception:
                # Fallback si aún no se ha corrido 06_sprint6_settings_and_export.sql en Supabase
                legacy_payload = {
                    "full_name": name_clean,
                    "preferred_currency": curr_clean,
                    "weight_unit": unit_clean,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                client.table("profiles").update(legacy_payload).eq("id", user_id).execute()

        current_profile = dict(st.session_state.get("user_profile") or {})
        current_profile.update(full_payload)
        st.session_state["user_profile"] = current_profile
        sync_profile_weights_to_session(current_profile)
        return True, "Preferencias de perfil y ponderaciones guardadas correctamente."
    except Exception as exc:
        return False, f"Error al actualizar preferencias: {exc}"


# ============================================================================
# 2. GENERADORES DE EXPORTACIÓN EN CSV (HÁBITOS, ENTRENAMIENTO, FINANZAS)
# ============================================================================


def build_habits_export_csv(
    habits: List[Dict[str, Any]],
    habit_logs: List[Dict[str, Any]],
) -> str:
    """Construye el archivo CSV tabular con el historial detallado de hábitos."""
    output = io.StringIO()
    output.write("\ufeff")  # BOM UTF-8 para compatibilidad directa con Excel
    writer = csv.writer(output)
    writer.writerow(
        [
            "log_date",
            "habit_name",
            "metric_type",
            "recorded_value",
            "daily_target_value",
            "unit_label",
            "progress_pct",
            "status",
            "is_fulfilled",
            "notes",
        ]
    )

    habits_by_id = {str(h.get("id")): h for h in habits}
    sorted_logs = sorted(
        habit_logs,
        key=lambda x: str(x.get("log_date") or ""),
        reverse=True,
    )

    for lg in sorted_logs:
        hid = str(lg.get("habit_id"))
        h_obj = habits_by_id.get(hid, {})
        h_name = str(h_obj.get("name", "Hábito"))
        mtype = str(h_obj.get("metric_type", "BOOLEAN")).upper()
        target_v = max(0.01, float(h_obj.get("daily_target_value") or 1.0))
        unit_lbl = str(h_obj.get("unit_label", "check"))
        rec_v = float(lg.get("recorded_value") or 0.0)
        fulfilled = bool(lg.get("is_fulfilled", False))

        if mtype == "BOOLEAN":
            pct = 100.0 if (fulfilled or rec_v >= 1.0) else 0.0
        else:
            pct = round((rec_v / target_v) * 100.0, 2)

        status = "COMPLETED" if pct >= 100.0 else ("PARTIAL" if pct > 0.0 else "PENDING")

        writer.writerow(
            [
                str(lg.get("log_date") or ""),
                h_name,
                mtype,
                f"{rec_v:.2f}",
                f"{target_v:.2f}",
                unit_lbl,
                f"{pct:.1f}",
                status,
                "TRUE" if pct >= 100.0 else "FALSE",
                str(lg.get("notes") or ""),
            ]
        )

    return output.getvalue()


def build_workouts_export_csv(
    sessions: List[Dict[str, Any]],
    sets: List[Dict[str, Any]],
    exercises: List[Dict[str, Any]],
) -> str:
    """Construye el archivo CSV tabular con todas las series y sesiones de entrenamiento."""
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(
        [
            "performed_at",
            "session_title",
            "exercise_name",
            "primary_muscle",
            "equipment",
            "set_number",
            "set_type",
            "weight_kg",
            "reps",
            "tonnage_kg",
            "estimated_1rm_epley_kg",
            "rpe",
            "rir",
            "rest_target_seconds",
            "rest_actual_seconds",
            "is_pr",
            "notes",
        ]
    )

    sess_by_id = {str(s.get("id")): s for s in sessions}
    ex_by_id = {str(e.get("id")): e for e in exercises}

    sorted_sets = sorted(
        sets,
        key=lambda s: (str(s.get("performed_at") or ""), int(s.get("set_number") or 1)),
        reverse=True,
    )

    for st_row in sorted_sets:
        sess_obj = sess_by_id.get(str(st_row.get("session_id")), {})
        ex_obj = ex_by_id.get(str(st_row.get("exercise_id")), {})

        sess_title = str(
            sess_obj.get("session_title") or sess_obj.get("title") or "Sesión de Entrenamiento"
        )
        ex_name = str(ex_obj.get("name", "Ejercicio"))
        muscle = str(ex_obj.get("primary_muscle", ""))
        equip = str(ex_obj.get("equipment", ""))

        w_kg = float(st_row.get("weight_kg") or 0.0)
        reps = int(st_row.get("reps") or 0)
        tonnage = round(w_kg * reps, 2)
        e1rm = calculate_epley_1rm(w_kg, reps)

        writer.writerow(
            [
                str(st_row.get("performed_at") or "")[:19],
                sess_title,
                ex_name,
                muscle,
                equip,
                int(st_row.get("set_number") or 1),
                str(st_row.get("set_type", "working")),
                f"{w_kg:.2f}",
                reps,
                f"{tonnage:.2f}",
                f"{e1rm:.2f}",
                f"{float(st_row.get('rpe') or 8.0):.1f}",
                f"{float(st_row.get('rir') or 2.0):.1f}",
                int(st_row.get("rest_target_seconds") or 90),
                int(st_row.get("rest_actual_seconds") or 0),
                "TRUE" if bool(st_row.get("is_pr")) else "FALSE",
                str(st_row.get("notes") or ""),
            ]
        )

    return output.getvalue()


def build_finances_export_csv(
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
) -> str:
    """Construye el archivo CSV tabular con todas las transacciones financieras."""
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(
        [
            "tx_date",
            "tx_type",
            "merchant_or_concept",
            "amount",
            "account_name",
            "institution_name",
            "category_name",
            "cashback_earned",
            "is_msi",
            "msi_months",
            "tags",
            "notes",
        ]
    )

    acc_by_id = {str(a.get("id")): a for a in accounts}
    cat_by_id = {str(c.get("id")): c for c in categories}

    sorted_txs = sorted(
        transactions,
        key=lambda t: str(t.get("tx_date") or ""),
        reverse=True,
    )

    for tx in sorted_txs:
        acc_obj = acc_by_id.get(str(tx.get("account_id")), {})
        cat_obj = cat_by_id.get(str(tx.get("category_id")), {})
        concept = str(
            tx.get("merchant_or_concept") or tx.get("merchant_or_note") or "Movimiento"
        )
        tags_val = tx.get("tags") or []
        tags_str = ",".join(str(t) for t in tags_val) if isinstance(tags_val, list) else str(tags_val)
        msi_m = int(tx.get("msi_months") or tx.get("installments_total") or 1)

        writer.writerow(
            [
                str(tx.get("tx_date") or ""),
                str(tx.get("tx_type", "expense")),
                concept,
                f"{float(tx.get('amount') or 0.0):.2f}",
                str(acc_obj.get("name", "Cuenta")),
                str(acc_obj.get("institution_name", "")),
                str(cat_obj.get("name", "Sin categoría")),
                f"{float(tx.get('cashback_earned') or 0.0):.2f}",
                "TRUE" if msi_m > 1 else "FALSE",
                msi_m,
                tags_str,
                str(tx.get("notes") or ""),
            ]
        )

    return output.getvalue()


# ============================================================================
# 3. GENERADOR DE RESPALDO CONSOLIDADO EN JSON (LIFE SNAPSHOT)
# ============================================================================


def build_consolidated_life_snapshot_dict(
    profile: Dict[str, Any],
    habits: List[Dict[str, Any]],
    habit_logs: List[Dict[str, Any]],
    goals: List[Dict[str, Any]],
    milestones: List[Dict[str, Any]],
    routines: List[Dict[str, Any]],
    routine_items: List[Dict[str, Any]],
    workout_sessions: List[Dict[str, Any]],
    workout_sets: List[Dict[str, Any]],
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    subscriptions: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    daily_snapshots: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Estructura el respaldo integral de la cuenta del usuario (Life Snapshot)
    en un diccionario jerárquico limpio listo para serializar a JSON.
    """
    return {
        "backup_metadata": {
            "application": APP_NAME,
            "version": APP_VERSION,
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "schema_format": "trifecta_life_snapshot_v1",
        },
        "user_profile_and_settings": {
            "id": profile.get("id"),
            "email": profile.get("email"),
            "full_name": profile.get("full_name"),
            "alias": profile.get("alias", ""),
            "preferred_currency": profile.get("preferred_currency", "MXN"),
            "weight_unit": profile.get("weight_unit", "kg"),
            "date_format": profile.get("date_format", "DD/MM/YYYY"),
            "trifecta_weights": {
                "weight_habits": float(profile.get("weight_habits") or 40.0),
                "weight_workouts": float(profile.get("weight_workouts") or 35.0),
                "weight_finances": float(profile.get("weight_finances") or 25.0),
            },
        },
        "summary_counts": {
            "habits_count": len(habits),
            "habit_logs_count": len(habit_logs),
            "personal_goals_count": len(goals),
            "workout_routines_count": len(routines),
            "workout_sessions_count": len(workout_sessions),
            "workout_sets_count": len(workout_sets),
            "finance_accounts_count": len(accounts),
            "finance_transactions_count": len(transactions),
            "finance_subscriptions_count": len(subscriptions),
            "daily_life_snapshots_count": len(daily_snapshots),
        },
        "pillar_1_workout": {
            "routines": routines,
            "routine_items": routine_items,
            "sessions": workout_sessions,
            "sets": workout_sets,
        },
        "pillar_2_finance": {
            "accounts": accounts,
            "categories": categories,
            "subscriptions": subscriptions,
            "transactions": transactions,
        },
        "pillar_3_habits_and_goals": {
            "habits": habits,
            "habit_logs": habit_logs,
            "personal_goals": goals,
            "goal_milestones": milestones,
        },
        "hub_daily_snapshots": daily_snapshots,
    }


def fetch_all_user_export_bundle(user_id: str, access_token: str) -> Dict[str, Any]:
    """Obtiene todos los datos del usuario para alimentar los botones de descarga CSV y JSON."""
    profile = st.session_state.get("user_profile") or {"id": user_id}
    habits = fetch_habits(user_id, access_token, include_archived=True)
    habit_logs = fetch_habit_logs(user_id, access_token, days_back=365)
    goals = fetch_personal_goals(user_id, access_token)
    milestones = fetch_goal_milestones(user_id, access_token)

    exercises = fetch_exercises_catalog(user_id, access_token)
    routines = fetch_workout_routines(user_id, access_token)
    routine_items = fetch_workout_routine_items(user_id, access_token)
    workout_sessions = fetch_workout_sessions(user_id, access_token, days_back=365)
    workout_sets = fetch_workout_sets(user_id, access_token, days_back=365)

    accounts = fetch_finance_accounts(user_id, access_token)
    categories = fetch_finance_categories(user_id, access_token)
    subscriptions = fetch_finance_subscriptions(user_id, access_token)
    transactions = fetch_finance_transactions(user_id, access_token, days_back=365)
    daily_snapshots = fetch_daily_snapshots(user_id, access_token, days_back=365)

    habits_csv = build_habits_export_csv(habits, habit_logs)
    workouts_csv = build_workouts_export_csv(workout_sessions, workout_sets, exercises)
    finances_csv = build_finances_export_csv(accounts, categories, transactions)

    snapshot_dict = build_consolidated_life_snapshot_dict(
        profile=profile,
        habits=habits,
        habit_logs=habit_logs,
        goals=goals,
        milestones=milestones,
        routines=routines,
        routine_items=routine_items,
        workout_sessions=workout_sessions,
        workout_sets=workout_sets,
        accounts=accounts,
        categories=categories,
        subscriptions=subscriptions,
        transactions=transactions,
        daily_snapshots=daily_snapshots,
    )
    snapshot_json = json.dumps(snapshot_dict, indent=2, ensure_ascii=False, default=str)

    return {
        "habits_csv": habits_csv,
        "workouts_csv": workouts_csv,
        "finances_csv": finances_csv,
        "snapshot_json": snapshot_json,
        "counts": snapshot_dict["summary_counts"],
    }


# ============================================================================
# 4. LIMPIEZA SEGURA DE REGISTROS DE PRUEBA ("Escribe BORRAR")
# ============================================================================


def purge_user_test_records(
    user_id: str,
    confirmation_text: str,
    reset_credit_card_balances: bool = True,
) -> Tuple[bool, str]:
    """
    Purga de forma segura los registros históricos de prueba creados durante los sprints:
    - Elimina: `habit_logs`, `workout_sets`, `workout_sessions`, `finance_transactions` y `daily_life_snapshots`.
    - Conserva intactos: `profiles`, `habits`, `personal_goals`, `goal_milestones`,
      `workout_routines`, `workout_routine_items`, `exercises`, `finance_accounts`,
      `finance_categories` y `finance_subscriptions`.
    Requiere escribir exactamente 'BORRAR'.
    """
    if (confirmation_text or "").strip() != "BORRAR":
        return False, "Confirmación inválida. Debes escribir exactamente BORRAR en mayúsculas."

    access_token = st.session_state.get("access_token") or ""
    if not user_id or not access_token:
        return False, "No hay una sesión autenticada activa."

    try:
        client = get_supabase_client(access_token=access_token)

        # 1. Purgar registros diarios de hábitos
        client.table("habit_logs").delete().eq("user_id", user_id).execute()

        # 2. Purgar series y sesiones de entrenamiento (conservando rutinas y ejercicios)
        client.table("workout_sets").delete().eq("user_id", user_id).execute()
        client.table("workout_sessions").delete().eq("user_id", user_id).execute()

        # 3. Purgar transacciones financieras (conservando cuentas, tarjetas y categorías)
        client.table("finance_transactions").delete().eq("user_id", user_id).execute()

        # 4. Purgar snapshots diarios del Hub (si la tabla existe)
        try:
            client.table("daily_life_snapshots").delete().eq("user_id", user_id).execute()
        except Exception:
            pass

        # 5. Opcional: reiniciar deuda utilizada en tarjetas de crédito a $0.00
        if reset_credit_card_balances:
            try:
                client.table("finance_accounts").update({"current_balance": 0.0}).eq(
                    "user_id", user_id
                ).eq("account_type", "credit_card").execute()
            except Exception:
                pass

        # Limpiar todas las cachés de los 3 pilares y del Hub
        clear_habits_cache()
        clear_workout_cache()
        clear_finance_cache()
        clear_hub_snapshots_cache()
        st.cache_data.clear()

        return (
            True,
            "Registros de prueba eliminados con éxito. Tus rutinas, metas, hábitos y cuentas base permanecen intactos.",
        )
    except Exception as exc:
        return False, f"Error durante la limpieza de registros: {exc}"
