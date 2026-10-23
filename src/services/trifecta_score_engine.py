"""
Motor Algorítmico de Puntuación Integral 'Trifecta Score', Secuenciador Inteligente
Push/Pull/Legs con Sobrecarga Progresiva, Analítica Cruzada Multitemporal y
Persistencia de Snapshots Diarios (`public.daily_life_snapshots`) — Sprint 5.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from src.auth.supabase_client import get_supabase_client
from src.models.hub_models import (
    BudgetStatusType,
    DailyLifeSnapshotModel,
    HubDailyPulse,
    NextWorkoutSuggestion,
    PPLSplitType,
    TrifectaWeights,
)
from src.services.card_advisor_engine import (
    calculate_card_cycle_dates,
    calculate_cashflow_and_budget_summary,
)
from src.services.progression_engine import get_exercise_recommendation

PUSH_MUSCLES = {"chest", "shoulders", "front_delts", "side_delts", "triceps"}
PULL_MUSCLES = {"back", "back_lats", "back_upper", "rear_delts", "biceps", "forearms"}
LEGS_MUSCLES = {"quads", "hamstrings", "glutes", "calves", "abs", "core"}

PPL_METADATA: Dict[PPLSplitType, Dict[str, str]] = {
    "PUSH": {
        "title": "PUSH · Empuje (Pecho, Hombro y Tríceps)",
        "subtitle": "Prioriza compuestos de empuje horizontal/vertical y extensión de codo.",
        "keywords": "push,empuje,pecho,hombro,triceps,chest,upper",
    },
    "PULL": {
        "title": "PULL · Tracción (Espalda, Bíceps y Deltoide Post.)",
        "subtitle": "Prioriza dominadas/jalones, remos pesados y flexión de codo.",
        "keywords": "pull,traccion,tracción,jala,espalda,biceps,back",
    },
    "LEGS": {
        "title": "LEGS · Tren Inferior & Core (Cuádriceps, Isquios y Glúteo)",
        "subtitle": "Prioriza patrón dominante de rodilla (sentadilla/prensa) y bisagra de cadera.",
        "keywords": "leg,pierna,inferior,gluteo,glúteo,sentadilla,lower",
    },
}

NEXT_PPL_ROTATION: Dict[str, PPLSplitType] = {
    "PUSH": "PULL",
    "PULL": "LEGS",
    "LEGS": "PUSH",
}


# ============================================================================
# 1. SUB-MOTORES DIARIOS POR PILAR (HÁBITOS, ENTRENAMIENTO, FINANZAS)
# ============================================================================


def compute_daily_habit_score(
    habits: List[Dict[str, Any]],
    habit_logs: List[Dict[str, Any]],
    target_date: Optional[date] = None,
) -> Tuple[float, int, int, int]:
    """
    Calcula el `habit_score` (0–100) en `target_date` promediando el porcentaje de avance
    de cada hábito activo (soportando estados parciales en hábitos numéricos).
    Retorna: (habit_score, completed_count, partial_count, total_active_habits).
    """
    ref_d = target_date or date.today()
    ref_iso = ref_d.isoformat()

    active_habits = [h for h in habits if not bool(h.get("is_archived", False))]
    total_active = len(active_habits)
    if total_active == 0:
        return 0.0, 0, 0, 0

    logs_on_day: Dict[str, Dict[str, Any]] = {}
    for lg in habit_logs:
        if str(lg.get("log_date") or "")[:10] == ref_iso:
            logs_on_day[str(lg.get("habit_id"))] = lg

    progress_sum = 0.0
    completed_count = 0
    partial_count = 0

    for h in active_habits:
        hid = str(h.get("id"))
        mtype = str(h.get("metric_type", "BOOLEAN")).upper()
        target_val = max(0.01, float(h.get("daily_target_value") or 1.0))
        lg = logs_on_day.get(hid)

        if not lg:
            pct = 0.0
        else:
            rec_val = max(0.0, float(lg.get("recorded_value") or 0.0))
            if mtype == "BOOLEAN":
                pct = 100.0 if (bool(lg.get("is_fulfilled")) or rec_val >= 1.0) else 0.0
            else:
                pct = min(100.0, round((rec_val / target_val) * 100.0, 2))

        if pct >= 100.0:
            completed_count += 1
        elif pct > 0.0:
            partial_count += 1

        progress_sum += pct

    habit_score = round(progress_sum / total_active, 2)
    return habit_score, completed_count, partial_count, total_active


def _extract_date_from_timestamp(raw_ts: Any) -> Optional[date]:
    if not raw_ts:
        return None
    try:
        return date.fromisoformat(str(raw_ts)[:10])
    except ValueError:
        return None


def compute_daily_workout_score(
    workout_sessions: List[Dict[str, Any]],
    workout_sets: List[Dict[str, Any]],
    target_date: Optional[date] = None,
) -> Tuple[float, bool, int]:
    """
    Calcula el `workout_score` (0–100) en `target_date`:
    - Si entrenó hoy (`workout_completed = True`) -> 100.0 pts.
    - Si hoy es día de descanso pero entrenó >=3 veces en los últimos 7 días -> 88.0 pts (Recuperación Activa).
    - Si entrenó 2 veces en los últimos 7 días -> 72.0 pts.
    - Si entrenó 1 vez en los últimos 7 días -> 55.0 pts.
    - Si no entrenó en los últimos 7 días -> 15.0 pts (si tiene historial previo) o 0.0 pts.
    Retorna: (workout_score, workout_completed_today, workouts_last_7d).
    """
    ref_d = target_date or date.today()
    window_start = ref_d - timedelta(days=6)

    workout_dates: set[date] = set()
    for sess in workout_sessions:
        dt = _extract_date_from_timestamp(sess.get("started_at"))
        if dt:
            workout_dates.add(dt)
    for st_row in workout_sets:
        dt = _extract_date_from_timestamp(st_row.get("performed_at"))
        if dt:
            workout_dates.add(dt)

    completed_today = ref_d in workout_dates
    workouts_7d = sum(1 for d in workout_dates if window_start <= d <= ref_d)

    if completed_today:
        score = 100.0
    elif workouts_7d >= 3:
        score = 88.0
    elif workouts_7d == 2:
        score = 72.0
    elif workouts_7d == 1:
        score = 55.0
    elif workout_dates:
        score = 15.0
    else:
        score = 0.0

    return round(score, 2), completed_today, workouts_7d


def compute_daily_finance_score(
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    target_date: Optional[date] = None,
) -> Tuple[float, BudgetStatusType, float, float, float]:
    """
    Evalúa la salud financiera en `target_date` combinando:
    - Control del presupuesto mensual (60 pts máx)
    - Salud de utilización de línea de crédito TDC <=30% (40 pts máx)
    Retorna: (finance_score, budget_status, today_expenses, budget_used_pct, cc_utilization_pct).
    """
    ref_d = target_date or date.today()
    ref_iso = ref_d.isoformat()

    # Filtrar transacciones hasta target_date para reconstrucción histórica fiel
    txs_up_to_date = [
        t for t in transactions if str(t.get("tx_date") or "")[:10] <= ref_iso
    ]
    today_expenses = sum(
        float(t.get("amount") or 0.0)
        for t in transactions
        if str(t.get("tx_date") or "")[:10] == ref_iso and str(t.get("tx_type")) == "expense"
    )

    summary = calculate_cashflow_and_budget_summary(
        accounts=accounts,
        categories=categories,
        transactions=txs_up_to_date,
        reference_date=ref_d,
    )

    total_budget = float(summary.get("total_monthly_budget") or 0.0)
    month_exp = float(summary.get("month_expenses") or 0.0)
    budget_used_pct = round((month_exp / total_budget) * 100.0, 1) if total_budget > 0 else 0.0

    cc_debt = float(summary.get("cc_debt") or 0.0)
    cc_limit = float(summary.get("cc_total_limit") or 0.0)
    cc_util_pct = round((cc_debt / cc_limit) * 100.0, 1) if cc_limit > 0 else 0.0

    # 1. Puntaje de Presupuesto (60 pts)
    if total_budget <= 0:
        budget_pts = 52.0 if accounts else 45.0
    elif budget_used_pct <= 85.0:
        budget_pts = 60.0 - (budget_used_pct / 85.0) * 6.0  # 54 a 60 pts
    elif budget_used_pct <= 100.0:
        budget_pts = 54.0 - ((budget_used_pct - 85.0) / 15.0) * 24.0  # 30 a 54 pts
    else:
        over_pct = min(100.0, budget_used_pct - 100.0)
        budget_pts = max(5.0, 30.0 - (over_pct / 100.0) * 25.0)

    # 2. Puntaje de Utilización de TDC (40 pts)
    if cc_limit <= 0:
        cc_pts = 36.0 if accounts else 30.0
    elif cc_util_pct <= 30.0:
        cc_pts = 40.0
    elif cc_util_pct <= 70.0:
        cc_pts = 40.0 - ((cc_util_pct - 30.0) / 40.0) * 20.0  # 20 a 40 pts
    else:
        cc_pts = max(4.0, 20.0 - ((cc_util_pct - 70.0) / 30.0) * 16.0)

    finance_score = round(min(100.0, max(0.0, budget_pts + cc_pts)), 2)

    if budget_used_pct > 100.0 or cc_util_pct > 75.0 or finance_score < 55.0:
        budget_status: BudgetStatusType = "CRITICAL"
    elif budget_used_pct > 85.0 or cc_util_pct > 35.0 or finance_score < 80.0:
        budget_status = "WARNING"
    else:
        budget_status = "OPTIMAL"

    return finance_score, budget_status, round(today_expenses, 2), budget_used_pct, cc_util_pct


# ============================================================================
# 2. MOTOR DE TRIFECTA SCORE PONDERADO Y CLASIFICACIÓN DE NIVEL
# ============================================================================


def calculate_weighted_trifecta_score(
    habit_score: float,
    workout_score: float,
    finance_score: float,
    weights: Optional[TrifectaWeights] = None,
) -> Tuple[float, str, str]:
    """
    Calcula el Trifecta Score (0 a 100) con el balance de pesos configurado
    (por defecto 40% Hábitos, 35% Entrenamiento, 25% Finanzas).
    Retorna: (trifecta_score, tier_label, tier_color).
    """
    w = (weights or TrifectaWeights()).normalized()
    h_s = min(100.0, max(0.0, float(habit_score)))
    w_s = min(100.0, max(0.0, float(workout_score)))
    f_s = min(100.0, max(0.0, float(finance_score)))

    score = round(
        (h_s * w.habits_weight) + (w_s * w.workout_weight) + (f_s * w.finance_weight),
        1,
    )

    if score >= 85.0:
        return score, "🔥 NIVEL ÉLITE · TRIFECTA EN SINCRONÍA", "#10B981"
    if score >= 70.0:
        return score, "⚡ NIVEL SÓLIDO · CONSISTENCIA ALTA", "#3B82F6"
    if score >= 50.0:
        return score, "⏳ EN PROGRESO · IMPULSA HOY TU DÍA", "#F59E0B"
    return score, "🛡️ RETOMAR RITMO · GANA UNA VICTORIA HOY", "#EF4444"


# ============================================================================
# 3. SUGERIDOR INTELIGENTE DE SECUENCIA PUSH / PULL / LEGS + SOBRECARGA
# ============================================================================


def _infer_ppl_split_from_text_or_muscles(
    title: str,
    primary_muscles: List[str],
) -> PPLSplitType:
    t_low = (title or "").lower()
    if any(k in t_low for k in ("push", "empuje", "pecho", "hombro")):
        return "PUSH"
    if any(k in t_low for k in ("pull", "traccion", "tracción", "espalda", "remo", "dominada")):
        return "PULL"
    if any(k in t_low for k in ("leg", "pierna", "inferior", "gluteo", "glúteo", "sentadilla")):
        return "LEGS"

    push_votes = sum(1 for m in primary_muscles if m in PUSH_MUSCLES)
    pull_votes = sum(1 for m in primary_muscles if m in PULL_MUSCLES)
    legs_votes = sum(1 for m in primary_muscles if m in LEGS_MUSCLES)

    if pull_votes > push_votes and pull_votes >= legs_votes:
        return "PULL"
    if legs_votes > push_votes and legs_votes > pull_votes:
        return "LEGS"
    return "PUSH"


def suggest_next_ppl_workout(
    user_id: str,
    routines: List[Dict[str, Any]],
    routine_items: List[Dict[str, Any]],
    sessions: List[Dict[str, Any]],
    sets: List[Dict[str, Any]],
    exercises: List[Dict[str, Any]],
    reference_date: Optional[date] = None,
) -> NextWorkoutSuggestion:
    """
    Determina la próxima sesión recomendada siguiendo la rotación Push -> Pull -> Legs
    y extrae las metas de sobrecarga progresiva para los ejercicios clave del split sugerido.
    """
    ref_d = reference_date or date.today()
    ex_by_id = {str(e["id"]): e for e in exercises}

    last_split: Optional[PPLSplitType] = None
    last_session_date: Optional[date] = None

    if sessions:
        latest_sess = sessions[0]
        last_session_date = _extract_date_from_timestamp(latest_sess.get("started_at"))
        sess_id = str(latest_sess.get("id") or "")
        sess_title = str(latest_sess.get("session_title") or latest_sess.get("title") or "")
        sess_sets = [s for s in sets if str(s.get("session_id")) == sess_id]
        sess_muscles = [
            str(ex_by_id.get(str(s.get("exercise_id")), {}).get("primary_muscle", ""))
            for s in sess_sets
        ]
        last_split = _infer_ppl_split_from_text_or_muscles(sess_title, sess_muscles)
    elif sets:
        last_session_date = _extract_date_from_timestamp(sets[0].get("performed_at"))
        recent_muscles = [
            str(ex_by_id.get(str(s.get("exercise_id")), {}).get("primary_muscle", ""))
            for s in sets[:8]
        ]
        last_split = _infer_ppl_split_from_text_or_muscles("", recent_muscles)

    next_split: PPLSplitType = NEXT_PPL_ROTATION.get(last_split or "LEGS", "PUSH")
    split_meta = PPL_METADATA[next_split]
    days_since = (ref_d - last_session_date).days if last_session_date else None

    _, completed_today, workouts_7d = compute_daily_workout_score(
        workout_sessions=sessions,
        workout_sets=sets,
        target_date=ref_d,
    )

    # Buscar si el usuario tiene una rutina guardada que coincida con next_split
    target_muscles = (
        PUSH_MUSCLES
        if next_split == "PUSH"
        else (PULL_MUSCLES if next_split == "PULL" else LEGS_MUSCLES)
    )
    recommended_routine_id: Optional[str] = None
    recommended_routine_name: Optional[str] = None

    for rt in routines:
        rid = str(rt.get("id"))
        rname = str(rt.get("name", ""))
        rt_items = [it for it in routine_items if str(it.get("routine_id")) == rid]
        rt_muscles = [
            str(ex_by_id.get(str(it.get("exercise_id")), {}).get("primary_muscle", ""))
            for it in rt_items
        ]
        inferred = _infer_ppl_split_from_text_or_muscles(rname, rt_muscles)
        if inferred == next_split:
            recommended_routine_id = rid
            recommended_routine_name = rname
            break

    if not recommended_routine_id and routines:
        recommended_routine_id = str(routines[0].get("id"))
        recommended_routine_name = str(routines[0].get("name"))

    # Seleccionar hasta 3 ejercicios representativos del split para mostrar su sobrecarga recomendada
    candidate_exercise_ids: List[str] = []
    if recommended_routine_id:
        for it in routine_items:
            if str(it.get("routine_id")) == recommended_routine_id:
                ex_id = str(it.get("exercise_id"))
                if ex_id not in candidate_exercise_ids:
                    candidate_exercise_ids.append(ex_id)

    if len(candidate_exercise_ids) < 3:
        for ex in exercises:
            if str(ex.get("primary_muscle")) in target_muscles:
                ex_id = str(ex["id"])
                if ex_id not in candidate_exercise_ids:
                    candidate_exercise_ids.append(ex_id)
                if len(candidate_exercise_ids) >= 3:
                    break

    overload_targets: List[Dict[str, Any]] = []
    for ex_id in candidate_exercise_ids[:3]:
        ex_obj = ex_by_id.get(ex_id, {})
        rec = get_exercise_recommendation(
            user_id=user_id,
            exercise_id=ex_id,
            all_user_sets=sets,
        )
        overload_targets.append(
            {
                "exercise_id": ex_id,
                "exercise_name": str(ex_obj.get("name", "Ejercicio")),
                "primary_muscle": str(ex_obj.get("primary_muscle", "")),
                "action_state": rec.state,
                "badge_text": f"{rec.badge_icon} {rec.badge_label}",
                "badge_color": rec.badge_color,
                "suggested_weight_kg": rec.suggested_weight_kg,
                "suggested_reps": rec.suggested_reps,
                "estimated_1rm_kg": rec.estimated_1rm_epley,
                "explanation": rec.explanation,
            }
        )

    return NextWorkoutSuggestion(
        next_ppl_split=next_split,
        split_title=split_meta["title"],
        split_subtitle=split_meta["subtitle"],
        last_ppl_split=last_split,
        last_session_date=last_session_date,
        days_since_last_workout=days_since,
        workouts_last_7d=workouts_7d,
        workout_completed_today=completed_today,
        recommended_routine_id=recommended_routine_id,
        recommended_routine_name=recommended_routine_name,
        overload_targets=overload_targets,
    )


# ============================================================================
# 4. PERSISTENCIA EN `daily_life_snapshots` Y SERIE MULTITEMPORAL (7D A 90D)
# ============================================================================


@st.cache_data(ttl=300)
def fetch_daily_snapshots(
    user_id: str,
    access_token: str,
    days_back: int = 90,
) -> List[Dict[str, Any]]:
    """Lee el historial de snapshots diarios persistidos del usuario en Supabase."""
    if not user_id or not access_token:
        return []
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    try:
        client = get_supabase_client(access_token=access_token)
        res = (
            client.table("daily_life_snapshots")
            .select("*")
            .eq("user_id", user_id)
            .gte("date", cutoff)
            .order("date", desc=False)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def clear_hub_snapshots_cache() -> None:
    """Invalida la caché de snapshots diarios."""
    fetch_daily_snapshots.clear()


def upsert_daily_snapshot(
    user_id: str,
    snapshot: DailyLifeSnapshotModel,
) -> Tuple[bool, str]:
    """
    Inserta o actualiza el snapshot diario en `public.daily_life_snapshots`
    respetando la restricción UNIQUE (user_id, date).
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        if not user_id or not access_token:
            return False, "Sesión no disponible."

        payload = {
            "user_id": user_id,
            "date": snapshot.date.isoformat(),
            "habit_score": round(float(snapshot.habit_score), 2),
            "workout_score": round(float(snapshot.workout_score), 2),
            "finance_score": round(float(snapshot.finance_score), 2),
            "workout_completed": bool(snapshot.workout_completed),
            "budget_status": snapshot.budget_status,
            "trifecta_score": round(float(snapshot.trifecta_score), 2),
            "metadata": snapshot.metadata or {},
        }
        client = get_supabase_client(access_token=access_token)
        client.table("daily_life_snapshots").upsert(
            payload,
            on_conflict="user_id,date",
        ).execute()
        clear_hub_snapshots_cache()
        return True, f"Snapshot del día ({snapshot.date.isoformat()}) sincronizado."
    except Exception as exc:
        return False, f"Nota: ejecuta 05_sprint5_hub_and_snapshots_migration.sql para persistir snapshots ({exc})."


def build_multitemporal_consistency_series(
    habits: List[Dict[str, Any]],
    habit_logs: List[Dict[str, Any]],
    workout_sessions: List[Dict[str, Any]],
    workout_sets: List[Dict[str, Any]],
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    saved_snapshots: Optional[List[Dict[str, Any]]] = None,
    weights: Optional[TrifectaWeights] = None,
    days_back: int = 30,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Construye la serie histórica día por día para los últimos `days_back` días,
    combinando snapshots guardados con cálculo en tiempo real y extrayendo:
    - Racha actual de consistencia (`consistency_streak_days`) y mejor racha (`best_streak_days`)
    - Promedio semanal (7D) vs mensual (30D)
    - Matriz de datos diarios para la línea de tendencia y el mapa de calor.
    """
    ref_d = reference_date or date.today()
    w = (weights or TrifectaWeights()).normalized()
    snap_by_date: Dict[str, Dict[str, Any]] = {}
    for sn in saved_snapshots or []:
        d_key = str(sn.get("date") or "")[:10]
        if d_key:
            snap_by_date[d_key] = sn

    # Calcular score financiero actual una vez como base rápida para días sin movimientos atípicos
    base_fin_score, base_budget_status, _, _, _ = compute_daily_finance_score(
        accounts=accounts,
        categories=categories,
        transactions=transactions,
        target_date=ref_d,
    )

    series_rows: List[Dict[str, Any]] = []
    for offset in range(days_back - 1, -1, -1):
        d_curr = ref_d - timedelta(days=offset)
        d_iso = d_curr.isoformat()

        h_score, h_done, h_part, _ = compute_daily_habit_score(habits, habit_logs, target_date=d_curr)
        w_score, w_done, _ = compute_daily_workout_score(workout_sessions, workout_sets, target_date=d_curr)

        if d_iso in snap_by_date and d_curr != ref_d:
            sn = snap_by_date[d_iso]
            f_score = float(sn.get("finance_score") or base_fin_score)
            b_status = str(sn.get("budget_status") or base_budget_status)
        else:
            f_score = base_fin_score
            b_status = base_budget_status

        t_score, tier_lbl, tier_col = calculate_weighted_trifecta_score(
            habit_score=h_score,
            workout_score=w_score,
            finance_score=f_score,
            weights=w,
        )

        # Se considera día consistente si trifecta_score >= 60 o si registró hábito/entreno ese día
        is_consistent = (t_score >= 60.0) or (h_done > 0) or (h_part > 0) or w_done

        series_rows.append(
            {
                "date": d_curr,
                "date_iso": d_iso,
                "label": d_curr.strftime("%d %b"),
                "weekday_idx": d_curr.weekday(),  # 0=Lun .. 6=Dom
                "habit_score": h_score,
                "workout_score": w_score,
                "finance_score": f_score,
                "trifecta_score": t_score,
                "workout_completed": w_done,
                "budget_status": b_status,
                "tier_label": tier_lbl,
                "tier_color": tier_col,
                "is_consistent": is_consistent,
            }
        )

    # Calcular racha actual y mejor racha
    current_streak = 0
    for row in reversed(series_rows):
        if row["is_consistent"]:
            current_streak += 1
        else:
            # Si es hoy y aún no registra actividad, revisar desde ayer sin romper la racha de ayer
            if row["date"] == ref_d:
                continue
            break

    best_streak = 0
    running = 0
    for row in series_rows:
        if row["is_consistent"]:
            running += 1
            best_streak = max(best_streak, running)
        else:
            running = 0

    last_7 = series_rows[-7:] if len(series_rows) >= 7 else series_rows
    avg_7d = round(sum(float(r["trifecta_score"]) for r in last_7) / len(last_7), 1) if last_7 else 0.0
    avg_30d = (
        round(sum(float(r["trifecta_score"]) for r in series_rows) / len(series_rows), 1)
        if series_rows
        else 0.0
    )

    return {
        "series": series_rows,
        "consistency_streak_days": current_streak,
        "best_consistency_streak_days": max(best_streak, current_streak),
        "avg_trifecta_7d": avg_7d,
        "avg_trifecta_30d": avg_30d,
    }


def evaluate_hub_daily_pulse(
    user_id: str,
    habits: List[Dict[str, Any]],
    habit_logs: List[Dict[str, Any]],
    routines: List[Dict[str, Any]],
    routine_items: List[Dict[str, Any]],
    workout_sessions: List[Dict[str, Any]],
    workout_sets: List[Dict[str, Any]],
    exercises: List[Dict[str, Any]],
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    saved_snapshots: Optional[List[Dict[str, Any]]] = None,
    weights: Optional[TrifectaWeights] = None,
    target_date: Optional[date] = None,
) -> Tuple[HubDailyPulse, Dict[str, Any]]:
    """
    Orquesta el cálculo integral del Command Center ('Hoy') y retorna tanto el objeto
    `HubDailyPulse` como el diccionario multitemporal de consistencia de los últimos 30 días.
    """
    ref_d = target_date or date.today()
    w = (weights or TrifectaWeights()).normalized()

    h_score, h_done, h_part, h_total = compute_daily_habit_score(habits, habit_logs, target_date=ref_d)
    w_score, w_done, _ = compute_daily_workout_score(workout_sessions, workout_sets, target_date=ref_d)
    f_score, b_status, today_exp, b_used_pct, _ = compute_daily_finance_score(
        accounts, categories, transactions, target_date=ref_d
    )

    t_score, tier_lbl, tier_col = calculate_weighted_trifecta_score(
        habit_score=h_score,
        workout_score=w_score,
        finance_score=f_score,
        weights=w,
    )

    fin_summary = calculate_cashflow_and_budget_summary(
        accounts=accounts,
        categories=categories,
        transactions=transactions,
        reference_date=ref_d,
    )
    liquid_total = round(
        float(fin_summary.get("liquid_balance") or 0.0)
        + float(fin_summary.get("investment_balance") or 0.0),
        2,
    )

    # Detectar alerta del próximo vencimiento o corte de tarjeta más cercano
    credit_cards = [
        a for a in accounts
        if str(a.get("account_type")) == "credit_card" and bool(a.get("is_active", True))
    ]
    next_alert_txt = "Sin vencimientos próximos en 14 días"
    next_alert_days: Optional[int] = None
    next_alert_col = "#10B981"

    if credit_cards:
        events_candidates: List[Tuple[int, str, str]] = []
        for cc in credit_cards:
            cname = str(cc.get("name", "TDC"))
            c_bal = float(cc.get("current_balance") or 0.0)
            cyc = calculate_card_cycle_dates(
                cutoff_day=int(cc.get("cutoff_day") or 15),
                payment_due_day=int(cc.get("payment_due_day") or 5),
                purchase_date=ref_d,
            )
            events_candidates.append(
                (
                    cyc.days_until_payment_due,
                    f"🔴 Pago límite {cname} en {cyc.days_until_payment_due}d ({cyc.payment_due_date.strftime('%d/%b')} · ${c_bal:,.0f})",
                    "#EF4444" if cyc.days_until_payment_due <= 5 else "#F59E0B",
                )
            )
            events_candidates.append(
                (
                    cyc.days_until_cutoff,
                    f"🔵 Corte {cname} en {cyc.days_until_cutoff}d ({cyc.statement_cutoff_date.strftime('%d/%b')})",
                    "#3B82F6",
                )
            )
        events_candidates.sort(key=lambda item: item[0])
        next_alert_days, next_alert_txt, next_alert_col = events_candidates[0]

    workout_sugg = suggest_next_ppl_workout(
        user_id=user_id,
        routines=routines,
        routine_items=routine_items,
        sessions=workout_sessions,
        sets=workout_sets,
        exercises=exercises,
        reference_date=ref_d,
    )

    consistency_data = build_multitemporal_consistency_series(
        habits=habits,
        habit_logs=habit_logs,
        workout_sessions=workout_sessions,
        workout_sets=workout_sets,
        accounts=accounts,
        categories=categories,
        transactions=transactions,
        saved_snapshots=saved_snapshots,
        weights=w,
        days_back=30,
        reference_date=ref_d,
    )

    pulse = HubDailyPulse(
        target_date=ref_d,
        trifecta_score=t_score,
        tier_label=tier_lbl,
        tier_color=tier_col,
        habit_score=h_score,
        workout_score=w_score,
        finance_score=f_score,
        workout_completed=w_done,
        budget_status=b_status,
        consistency_streak_days=int(consistency_data["consistency_streak_days"]),
        best_consistency_streak_days=int(consistency_data["best_consistency_streak_days"]),
        habits_completed_today=h_done,
        habits_partial_today=h_part,
        habits_total_active=h_total,
        today_expenses_amount=today_exp,
        liquid_balance=liquid_total,
        cc_debt=float(fin_summary.get("cc_debt") or 0.0),
        budget_remaining_total=float(fin_summary.get("budget_remaining_total") or 0.0),
        budget_used_pct=b_used_pct,
        next_card_alert_text=next_alert_txt,
        next_card_alert_days=next_alert_days,
        next_card_alert_color=next_alert_col,
        workout_suggestion=workout_sugg,
        weights=w,
    )
    return pulse, consistency_data
