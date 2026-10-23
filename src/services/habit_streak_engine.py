"""
Motor de rachas (current_streak, best_streak), progreso parcial tripartito
(PENDING, PARTIAL, COMPLETED), analítica agregada (promedio semanal 7d y sumatoria
acumulada mensual), heatmaps (90d), operaciones CRUD y sincronización de Metas.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

import streamlit as st

from src.auth.supabase_client import get_supabase_client
from src.models.habit_models import (
    HABIT_STATUS_LABELS,
    GoalMilestoneModel,
    HabitAnalytics,
    HabitDailyStatus,
    HabitLogModel,
    HabitModel,
    HeatmapCell,
    PersonalGoalModel,
)


# ============================================================================
# 1. MOTOR ALGORÍTMICO DE PROGRESO PARCIAL, ESTADOS Y ANALÍTICA TEMPORAL
# ============================================================================

def calculate_completion_percentage(
    metric_type: str,
    recorded_value: float,
    daily_target_value: float,
) -> float:
    """
    Calcula el porcentaje exacto de cumplimiento: (valor_actual / meta) * 100.
    - Para NUMERIC y DURATION: (recorded_value / daily_target_value) * 100.0
    - Para BOOLEAN: 100.0 si recorded_value >= 1.0, de lo contrario 0.0
    - Para RATING: 100.0 si recorded_value >= 1.0 (valoración capturada), de lo contrario 0.0
    """
    mtype = (metric_type or "BOOLEAN").upper()
    val = max(0.0, float(recorded_value or 0.0))
    target = max(0.0001, float(daily_target_value or 1.0))

    if val <= 0.0:
        return 0.0
    if mtype == "BOOLEAN":
        return 100.0 if val >= 1.0 else 0.0
    if mtype == "RATING":
        return 100.0 if val >= 1.0 else 0.0
    # NUMERIC / DURATION: (valor_actual / meta) * 100
    return round((val / target) * 100.0, 2)


def determine_habit_daily_status(
    metric_type: str,
    recorded_value: float,
    daily_target_value: float,
) -> HabitDailyStatus:
    """
    Clasifica el avance diario en uno de los 3 estados visuales definidos:
    - 'PENDING' (Pendiente): 0% (valor_actual <= 0)
    - 'PARTIAL' (En progreso / Parcial): > 0% y < 100% (0 < valor_actual < meta)
    - 'COMPLETED' (Completado): >= 100% (valor_actual >= meta)
    """
    mtype = (metric_type or "BOOLEAN").upper()
    val = max(0.0, float(recorded_value or 0.0))
    target = max(0.0001, float(daily_target_value or 1.0))

    if val <= 0.0:
        return "PENDING"
    if mtype in ("BOOLEAN", "RATING"):
        return "COMPLETED" if val >= 1.0 else "PENDING"
    if val >= target:
        return "COMPLETED"
    return "PARTIAL"


def evaluate_habit_fulfillment(
    metric_type: str,
    recorded_value: float,
    daily_target_value: float,
) -> bool:
    """Retorna True únicamente cuando el estado diario alcanza 'COMPLETED' (>= 100%)."""
    return determine_habit_daily_status(metric_type, recorded_value, daily_target_value) == "COMPLETED"


def _parse_date(val: Any) -> Optional[date]:
    """Convierte cadenas ISO o instancias date/datetime en objetos date."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val:
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            return None
    return None


def calculate_weekly_daily_average(
    logs: List[Dict[str, Any]],
    habit_id: str,
    reference_date: Optional[date] = None,
) -> Tuple[float, int]:
    """
    Calcula el Promedio Diario Semanal (últimos 7 días naturales: [ref_date - 6d .. ref_date]).
    Retorna (promedio_diario_7d, dias_con_registro_en_7d).
    """
    ref_date = reference_date or date.today()
    start_7d = ref_date - timedelta(days=6)
    values_by_day: Dict[date, float] = {}

    for row in logs:
        if row.get("habit_id") is not None and str(row.get("habit_id")) != str(habit_id):
            continue
        d = _parse_date(row.get("log_date"))
        if d is not None and start_7d <= d <= ref_date:
            val = max(0.0, float(row.get("recorded_value") or 0.0))
            if val > 0.0:
                values_by_day[d] = val

    total_7d = sum(values_by_day.values())
    avg_7d = round(total_7d / 7.0, 2)
    return avg_7d, len(values_by_day)


def calculate_monthly_accumulated_sum(
    logs: List[Dict[str, Any]],
    habit_id: str,
    reference_date: Optional[date] = None,
) -> Tuple[float, int]:
    """
    Calcula la Sumatoria Acumulada Mensual en el mes corriente (del día 1 del mes hasta ref_date).
    Retorna (sumatoria_acumulada_mes, dias_con_registro_mes).
    """
    ref_date = reference_date or date.today()
    values_by_day: Dict[date, float] = {}

    for row in logs:
        if row.get("habit_id") is not None and str(row.get("habit_id")) != str(habit_id):
            continue
        d = _parse_date(row.get("log_date"))
        if d is not None and d.year == ref_date.year and d.month == ref_date.month and d <= ref_date:
            val = max(0.0, float(row.get("recorded_value") or 0.0))
            if val > 0.0:
                values_by_day[d] = val

    total_month = round(sum(values_by_day.values()), 2)
    return total_month, len(values_by_day)


def calculate_habit_analytics(
    habit: Dict[str, Any],
    logs: List[Dict[str, Any]],
    reference_date: Optional[date] = None,
) -> HabitAnalytics:
    """
    Calcula el paquete analítico completo de un hábito:
    - Estado diario tripartito (PENDING 0%, PARTIAL >0% y <100%, COMPLETED >=100%)
    - Porcentaje de avance diario: (valor_actual / meta) * 100
    - Promedio diario semanal (7d) y Sumatoria acumulada mensual (mes corriente)
    - current_streak, best_streak, adherencia de 30 días (%) y Heatmap de 90 días.
    """
    ref_date = reference_date or date.today()
    habit_id = str(habit.get("id", ""))
    metric_type = str(habit.get("metric_type", "BOOLEAN")).upper()
    target_val = max(0.0001, float(habit.get("daily_target_value") or 1.0))
    freq_per_week = max(1, min(7, int(habit.get("frequency_days_per_week") or 7)))

    # Mapear logs por fecha para este hábito
    logs_by_date: Dict[date, Dict[str, Any]] = {}
    for row in logs:
        if str(row.get("habit_id", "")) != habit_id and row.get("habit_id") is not None:
            continue
        d = _parse_date(row.get("log_date"))
        if d is not None:
            rec_val = max(0.0, float(row.get("recorded_value") or 0.0))
            comp_pct = calculate_completion_percentage(metric_type, rec_val, target_val)
            status = determine_habit_daily_status(metric_type, rec_val, target_val)
            fulfilled = status == "COMPLETED"
            logs_by_date[d] = {
                "recorded_value": rec_val,
                "completion_pct": comp_pct,
                "daily_status": status,
                "is_fulfilled": fulfilled,
            }

    fulfilled_dates_sorted = sorted(
        d for d, info in logs_by_date.items() if info["is_fulfilled"] and d <= ref_date
    )
    fulfilled_set = set(fulfilled_dates_sorted)

    # 1. Cálculo de Mejor Racha Histórica (best_streak)
    best_streak = 0
    running = 0
    prev_d: Optional[date] = None
    for d in fulfilled_dates_sorted:
        if prev_d is not None and (d - prev_d).days == 1:
            running += 1
        else:
            running = 1
        if running > best_streak:
            best_streak = running
        prev_d = d

    # 2. Cálculo de Racha Actual (current_streak)
    current_streak = 0
    cursor = ref_date if ref_date in fulfilled_set else (ref_date - timedelta(days=1))
    while cursor in fulfilled_set:
        current_streak += 1
        cursor -= timedelta(days=1)

    if current_streak > best_streak:
        best_streak = current_streak

    # 3. Adherencia en los últimos 30 días naturales (ponderando días parciales proporcionalmente)
    start_30d = ref_date - timedelta(days=29)
    fulfilled_30d = 0
    partial_30d = 0
    effective_days_sum_30d = 0.0

    for i in range(30):
        day_i = start_30d + timedelta(days=i)
        info_i = logs_by_date.get(day_i)
        if not info_i:
            continue
        st_i = info_i["daily_status"]
        if st_i == "COMPLETED":
            fulfilled_30d += 1
            effective_days_sum_30d += 1.0
        elif st_i == "PARTIAL":
            partial_30d += 1
            effective_days_sum_30d += min(0.99, float(info_i["completion_pct"]) / 100.0)

    expected_days_30d = max(1.0, (freq_per_week / 7.0) * 30.0)
    adherence_30d_pct = round(min(100.0, (effective_days_sum_30d / expected_days_30d) * 100.0), 1)

    # 4. Estado del día de referencia (Hoy): Pendiente (0%), En progreso (>0% y <100%), Completado (>=100%)
    today_info = logs_by_date.get(
        ref_date,
        {
            "recorded_value": 0.0,
            "completion_pct": 0.0,
            "daily_status": "PENDING",
            "is_fulfilled": False,
        },
    )
    today_val = float(today_info["recorded_value"])
    today_status: HabitDailyStatus = today_info["daily_status"]
    today_status_label = HABIT_STATUS_LABELS.get(today_status, "Pendiente")
    today_fulfilled = bool(today_info["is_fulfilled"])
    today_progress_pct = float(today_info["completion_pct"])
    today_bar_pct = round(min(100.0, max(0.0, today_progress_pct)), 2)

    # 5. Cálculos agregados temporales (Promedio diario semanal 7d y Sumatoria mensual)
    weekly_avg_7d, weekly_active_7d = calculate_weekly_daily_average(logs, habit_id, reference_date=ref_date)
    monthly_sum, monthly_active = calculate_monthly_accumulated_sum(logs, habit_id, reference_date=ref_date)

    # 6. Matriz de 90 días para el Heatmap estilo GitHub / HabitKit
    start_90d = ref_date - timedelta(days=89)
    heatmap_cells: List[HeatmapCell] = []
    for i in range(90):
        cell_date = start_90d + timedelta(days=i)
        info = logs_by_date.get(cell_date)
        rec = float(info["recorded_value"]) if info else 0.0
        comp_pct = float(info["completion_pct"]) if info else 0.0
        cell_status: HabitDailyStatus = info["daily_status"] if info else "PENDING"
        ful = bool(info["is_fulfilled"]) if info else False

        if cell_status == "COMPLETED":
            intensity = 1.0
        elif cell_status == "PARTIAL":
            intensity = min(0.88, max(0.28, comp_pct / 100.0))
        else:
            intensity = 0.0

        heatmap_cells.append(
            HeatmapCell(
                log_date=cell_date,
                date_label=cell_date.strftime("%d %b"),
                weekday=cell_date.weekday(),
                recorded_value=rec,
                completion_pct=comp_pct,
                daily_status=cell_status,
                is_fulfilled=ful,
                intensity=round(intensity, 2),
            )
        )

    return HabitAnalytics(
        habit_id=habit_id,
        current_streak=current_streak,
        best_streak=best_streak,
        adherence_30d_pct=adherence_30d_pct,
        fulfilled_days_30d=fulfilled_30d,
        partial_days_30d=partial_30d,
        today_value=today_val,
        today_fulfilled=today_fulfilled,
        today_status=today_status,
        today_status_label=today_status_label,
        today_progress_pct=today_progress_pct,
        today_bar_pct=today_bar_pct,
        weekly_daily_avg_7d=weekly_avg_7d,
        weekly_active_days_7d=weekly_active_7d,
        monthly_accumulated_sum=monthly_sum,
        monthly_active_days=monthly_active,
        heatmap_90d=heatmap_cells,
    )


def calculate_goal_progress_pct(
    milestones: List[Dict[str, Any]],
    linked_habits_adherence: Optional[List[float]] = None,
) -> float:
    """
    Calcula el porcentaje de avance global (0%–100%) de una Meta Personal
    integrando los hitos completados del Plan de Desarrollo y la adherencia de hábitos vinculados.
    """
    total_ms = len(milestones)
    completed_ms = sum(1 for m in milestones if bool(m.get("is_completed")))
    ms_pct = (completed_ms / total_ms) * 100.0 if total_ms > 0 else None

    adherences = [float(a) for a in (linked_habits_adherence or []) if a is not None]
    hab_pct = (sum(adherences) / len(adherences)) if adherences else None

    if ms_pct is not None and hab_pct is not None:
        if completed_ms == total_ms and total_ms > 0:
            return 100.0
        return round(min(100.0, (0.75 * ms_pct) + (0.25 * hab_pct)), 1)
    if ms_pct is not None:
        return round(ms_pct, 1)
    if hab_pct is not None:
        return round(min(100.0, hab_pct), 1)
    return 0.0


# ============================================================================
# 2. LECTURAS CACHEADAS CON AISLAMIENTO POR USUARIO (@st.cache_data)
# ============================================================================

@st.cache_data(ttl=300)
def fetch_habits(
    user_id: str,
    access_token: str,
    include_archived: bool = False,
) -> List[Dict[str, Any]]:
    """Lee los hábitos del usuario ordenados por is_pinned DESC y display_order ASC."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    query = (
        client.table("habits")
        .select("*")
        .eq("user_id", user_id)
    )
    if not include_archived:
        query = query.eq("is_archived", False)
    res = (
        query.order("is_pinned", desc=True)
        .order("display_order", desc=False)
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=300)
def fetch_habit_logs(
    user_id: str,
    access_token: str,
    days_back: int = 120,
) -> List[Dict[str, Any]]:
    """Lee los registros diarios de hábitos del usuario para alimentar rachas, promedios y heatmaps."""
    if not user_id or not access_token:
        return []
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("habit_logs")
        .select("*")
        .eq("user_id", user_id)
        .gte("log_date", cutoff)
        .order("log_date", desc=True)
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=300)
def fetch_personal_goals(
    user_id: str,
    access_token: str,
) -> List[Dict[str, Any]]:
    """Lee las metas personales del usuario ordenadas por display_order ASC."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("personal_goals")
        .select("*")
        .eq("user_id", user_id)
        .order("display_order", desc=False)
        .order("target_date", desc=False)
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=300)
def fetch_goal_milestones(
    user_id: str,
    access_token: str,
) -> List[Dict[str, Any]]:
    """Lee todos los hitos del plan de desarrollo del usuario ordenados por step_order ASC."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("goal_milestones")
        .select("*")
        .eq("user_id", user_id)
        .order("step_order", desc=False)
        .execute()
    )
    return res.data or []


def clear_habits_cache() -> None:
    """Invalida selectivamente las cachés del Pilar 3 tras cualquier operación de escritura."""
    fetch_habits.clear()
    fetch_habit_logs.clear()
    fetch_personal_goals.clear()
    fetch_goal_milestones.clear()
    try:
        from src.views.home_hub_view import _fetch_hub_summary_counts
        _fetch_hub_summary_counts.clear()
    except Exception:
        pass


# ============================================================================
# 3. OPERACIONES DE ESCRITURA (CRUD) PARA HÁBITOS Y REGISTROS DIARIOS
# ============================================================================

def create_habit(
    user_id: str,
    name: str,
    icon: str = "⚡",
    color_hex: str = "#8B5CF6",
    metric_type: Literal["BOOLEAN", "NUMERIC", "DURATION", "RATING"] = "BOOLEAN",
    unit_label: str = "check",
    daily_target_value: float = 1.0,
    frequency_days_per_week: int = 7,
    linked_goal_id: Optional[str] = None,
    is_pinned: bool = False,
) -> Tuple[bool, str]:
    """Valida con Pydantic e inserta un nuevo hábito personalizado en Supabase."""
    try:
        access_token = st.session_state.get("access_token") or ""
        existing = fetch_habits(user_id, access_token, include_archived=True)
        next_order = max((int(h.get("display_order") or 0) for h in existing), default=0) + 1

        validated = HabitModel(
            user_id=user_id,
            linked_goal_id=linked_goal_id or None,
            name=name.strip(),
            icon=icon.strip() or "⚡",
            color_hex=color_hex,
            metric_type=metric_type,
            unit_label=unit_label.strip() or ("check" if metric_type == "BOOLEAN" else "unid"),
            daily_target_value=float(daily_target_value),
            frequency_days_per_week=int(frequency_days_per_week),
            display_order=next_order,
            is_pinned=bool(is_pinned),
            is_archived=False,
        )

        payload = validated.model_dump(exclude={"id"})
        client = get_supabase_client(access_token=access_token)
        client.table("habits").insert(payload).execute()
        clear_habits_cache()
        return True, f"Hábito «{validated.name}» creado correctamente."
    except Exception as exc:
        return False, f"Error al crear hábito: {exc}"


def update_habit(
    user_id: str,
    habit_id: str,
    name: str,
    icon: str,
    color_hex: str,
    metric_type: Literal["BOOLEAN", "NUMERIC", "DURATION", "RATING"],
    unit_label: str,
    daily_target_value: float,
    frequency_days_per_week: int,
    linked_goal_id: Optional[str] = None,
    is_pinned: bool = False,
    is_archived: bool = False,
) -> Tuple[bool, str]:
    """Actualiza la configuración de un hábito existente y limpia la caché."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        payload = {
            "name": name.strip(),
            "icon": icon.strip() or "⚡",
            "color_hex": color_hex,
            "metric_type": metric_type,
            "unit_label": unit_label.strip() or "check",
            "daily_target_value": float(daily_target_value),
            "frequency_days_per_week": int(frequency_days_per_week),
            "linked_goal_id": linked_goal_id or None,
            "is_pinned": bool(is_pinned),
            "is_archived": bool(is_archived),
        }
        client.table("habits").update(payload).eq("id", habit_id).eq("user_id", user_id).execute()
        clear_habits_cache()
        return True, "Hábito actualizado."
    except Exception as exc:
        return False, f"Error al actualizar hábito: {exc}"


def delete_habit(user_id: str, habit_id: str) -> Tuple[bool, str]:
    """Elimina un hábito y sus registros asociados."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("habits").delete().eq("id", habit_id).eq("user_id", user_id).execute()
        clear_habits_cache()
        return True, "Hábito eliminado."
    except Exception as exc:
        return False, f"Error al eliminar hábito: {exc}"


def toggle_habit_pin(user_id: str, habit_id: str, current_pinned: bool) -> Tuple[bool, str]:
    """Fija o desfija un hábito en la parte superior del dashboard (is_pinned)."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("habits").update({"is_pinned": not current_pinned}).eq("id", habit_id).eq("user_id", user_id).execute()
        clear_habits_cache()
        return True, "Prioridad de fijado actualizada."
    except Exception as exc:
        return False, f"Error al fijar hábito: {exc}"


def move_habit_order(
    user_id: str,
    habit_id: str,
    direction: Literal["up", "down"],
) -> Tuple[bool, str]:
    """
    Reordena un hábito hacia arriba o hacia abajo en el dashboard, normalizando
    display_order de forma determinista y persistiendo en Supabase.
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        habits = fetch_habits(user_id, access_token, include_archived=False)
        if len(habits) < 2:
            return True, "Sin cambios de orden necesarios."

        target_idx = next((i for i, h in enumerate(habits) if str(h.get("id")) == str(habit_id)), None)
        if target_idx is None:
            return False, "Hábito no encontrado."

        swap_idx = target_idx - 1 if direction == "up" else target_idx + 1
        if swap_idx < 0 or swap_idx >= len(habits):
            return True, "El hábito ya está en el extremo."

        neighbor_pinned = bool(habits[swap_idx].get("is_pinned", False))
        habits[target_idx]["is_pinned"] = neighbor_pinned

        habits[target_idx], habits[swap_idx] = habits[swap_idx], habits[target_idx]

        client = get_supabase_client(access_token=access_token)
        for new_pos, h in enumerate(habits, start=1):
            client.table("habits").update(
                {
                    "display_order": new_pos,
                    "is_pinned": bool(h.get("is_pinned", False)),
                }
            ).eq("id", h["id"]).eq("user_id", user_id).execute()

        clear_habits_cache()
        return True, "Orden del dashboard actualizado."
    except Exception as exc:
        return False, f"Error al reordenar hábito: {exc}"


def upsert_habit_log(
    user_id: str,
    habit: Dict[str, Any],
    recorded_value: float,
    log_date: Optional[date] = None,
    notes: str = "",
) -> Tuple[bool, str]:
    """
    Registra o actualiza el valor de un hábito en `habit_logs` para la fecha indicada.
    Soporta valores parciales (>0 y <meta) persistiendo recorded_value con is_fulfilled=False
    y estado visual 'PARTIAL', o is_fulfilled=True cuando alcanza >=100% de la meta.
    """
    try:
        target_date = log_date or date.today()
        habit_id = str(habit["id"])
        metric_type = str(habit.get("metric_type", "BOOLEAN")).upper()
        daily_target = float(habit.get("daily_target_value") or 1.0)
        val = max(0.0, round(float(recorded_value), 2))
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)

        if val <= 0.0:
            client.table("habit_logs").delete().eq("habit_id", habit_id).eq("log_date", target_date.isoformat()).eq("user_id", user_id).execute()
            clear_habits_cache()
            if habit.get("linked_goal_id"):
                recalculate_and_persist_goal_progress(user_id, str(habit["linked_goal_id"]))
            return True, "Registro del día reiniciado (0%)."

        is_fulfilled = evaluate_habit_fulfillment(metric_type, val, daily_target)
        comp_pct = calculate_completion_percentage(metric_type, val, daily_target)
        validated = HabitLogModel(
            user_id=user_id,
            habit_id=habit_id,
            log_date=target_date,
            recorded_value=val,
            is_fulfilled=is_fulfilled,
            notes=notes,
        )

        payload = {
            "user_id": validated.user_id,
            "habit_id": validated.habit_id,
            "log_date": validated.log_date.isoformat(),
            "recorded_value": validated.recorded_value,
            "is_fulfilled": validated.is_fulfilled,
            "notes": validated.notes,
        }
        client.table("habit_logs").upsert(payload, on_conflict="habit_id,log_date").execute()
        clear_habits_cache()

        if habit.get("linked_goal_id"):
            recalculate_and_persist_goal_progress(user_id, str(habit["linked_goal_id"]))

        if is_fulfilled:
            return True, f"¡Meta completada ({comp_pct:.0f}%)!"
        return True, f"Avance parcial guardado ({comp_pct:.1f}%)."
    except Exception as exc:
        return False, f"Error al guardar registro: {exc}"


# ============================================================================
# 4. OPERACIONES CRUD PARA METAS PERSONALES Y PLANES DE DESARROLLO (HITOS)
# ============================================================================

def recalculate_and_persist_goal_progress(user_id: str, goal_id: str) -> float:
    """Recalcula el progress_pct de una meta según sus hitos y hábitos vinculados y lo guarda en Supabase."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)

        ms_res = (
            client.table("goal_milestones")
            .select("*")
            .eq("user_id", user_id)
            .eq("goal_id", goal_id)
            .execute()
        )
        milestones = ms_res.data or []

        hb_res = (
            client.table("habits")
            .select("*")
            .eq("user_id", user_id)
            .eq("linked_goal_id", goal_id)
            .eq("is_archived", False)
            .execute()
        )
        linked_habits = hb_res.data or []

        adherences: List[float] = []
        if linked_habits:
            cutoff = (date.today() - timedelta(days=35)).isoformat()
            logs_res = (
                client.table("habit_logs")
                .select("*")
                .eq("user_id", user_id)
                .gte("log_date", cutoff)
                .execute()
            )
            all_logs = logs_res.data or []
            for h in linked_habits:
                analytics = calculate_habit_analytics(h, all_logs)
                adherences.append(analytics.adherence_30d_pct)

        new_pct = calculate_goal_progress_pct(milestones, adherences)
        new_status = "completed" if (milestones and all(m.get("is_completed") for m in milestones)) else "active"

        client.table("personal_goals").update(
            {"progress_pct": new_pct, "status": new_status}
        ).eq("id", goal_id).eq("user_id", user_id).execute()

        clear_habits_cache()
        return new_pct
    except Exception:
        return 0.0


def create_personal_goal_with_milestones(
    user_id: str,
    title: str,
    life_area: str,
    target_date: date,
    description: str = "",
    milestone_titles: Optional[List[str]] = None,
    linked_habit_ids: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Crea una Meta Personal (personal_goals), inserta sus Hitos secuenciales (goal_milestones)
    y vincula los hábitos diarios seleccionados (habits.linked_goal_id).
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        existing_goals = fetch_personal_goals(user_id, access_token)
        next_order = max((int(g.get("display_order") or 0) for g in existing_goals), default=0) + 1

        validated_goal = PersonalGoalModel(
            user_id=user_id,
            title=title.strip(),
            life_area=life_area,
            description=description.strip(),
            start_date=date.today(),
            target_date=target_date,
            progress_pct=0.0,
            status="active",
            display_order=next_order,
        )

        client = get_supabase_client(access_token=access_token)
        goal_payload = {
            "user_id": validated_goal.user_id,
            "title": validated_goal.title,
            "life_area": validated_goal.life_area,
            "description": validated_goal.description,
            "start_date": validated_goal.start_date.isoformat(),
            "target_date": validated_goal.target_date.isoformat(),
            "progress_pct": 0.0,
            "status": "active",
            "display_order": validated_goal.display_order,
        }
        ins_res = client.table("personal_goals").insert(goal_payload).execute()
        if not ins_res.data:
            return False, "No se pudo crear la meta personal."

        goal_id = str(ins_res.data[0]["id"])

        clean_milestones = [m.strip() for m in (milestone_titles or []) if m and m.strip()]
        if clean_milestones:
            total_days = max(7, (target_date - date.today()).days)
            ms_rows = []
            for idx, m_title in enumerate(clean_milestones, start=1):
                fraction = idx / len(clean_milestones)
                due = date.today() + timedelta(days=int(total_days * fraction))
                validated_ms = GoalMilestoneModel(
                    user_id=user_id,
                    goal_id=goal_id,
                    title=m_title,
                    step_order=idx,
                    due_date=due,
                    is_completed=False,
                )
                ms_rows.append(
                    {
                        "user_id": validated_ms.user_id,
                        "goal_id": validated_ms.goal_id,
                        "title": validated_ms.title,
                        "step_order": validated_ms.step_order,
                        "due_date": validated_ms.due_date.isoformat() if validated_ms.due_date else None,
                        "is_completed": False,
                    }
                )
            client.table("goal_milestones").insert(ms_rows).execute()

        for h_id in (linked_habit_ids or []):
            if h_id:
                client.table("habits").update({"linked_goal_id": goal_id}).eq("id", h_id).eq("user_id", user_id).execute()

        recalculate_and_persist_goal_progress(user_id, goal_id)
        clear_habits_cache()
        return True, f"Meta «{validated_goal.title}» creada con {len(clean_milestones)} hitos."
    except Exception as exc:
        return False, f"Error al crear meta personal: {exc}"


def add_goal_milestone(
    user_id: str,
    goal_id: str,
    title: str,
    due_date: Optional[date] = None,
) -> Tuple[bool, str]:
    """Agrega un nuevo hito secuencial al Plan de Desarrollo de una meta."""
    try:
        clean_title = (title or "").strip()
        if not clean_title:
            return False, "Escribe el título del hito."

        access_token = st.session_state.get("access_token") or ""
        all_ms = fetch_goal_milestones(user_id, access_token)
        goal_ms = [m for m in all_ms if str(m.get("goal_id")) == str(goal_id)]
        next_step = max((int(m.get("step_order") or 0) for m in goal_ms), default=0) + 1

        client = get_supabase_client(access_token=access_token)
        client.table("goal_milestones").insert(
            {
                "user_id": user_id,
                "goal_id": goal_id,
                "title": clean_title,
                "step_order": next_step,
                "due_date": due_date.isoformat() if due_date else None,
                "is_completed": False,
            }
        ).execute()

        recalculate_and_persist_goal_progress(user_id, goal_id)
        return True, "Hito agregado al plan."
    except Exception as exc:
        return False, f"Error al agregar hito: {exc}"


def toggle_goal_milestone(
    user_id: str,
    milestone_id: str,
    goal_id: str,
    is_completed: bool,
) -> Tuple[bool, str]:
    """Marca o desmarca un hito del Plan de Desarrollo y recalcula el avance de la meta."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        completed_at = datetime.now(timezone.utc).isoformat() if is_completed else None
        client.table("goal_milestones").update(
            {
                "is_completed": bool(is_completed),
                "completed_at": completed_at,
            }
        ).eq("id", milestone_id).eq("user_id", user_id).execute()

        recalculate_and_persist_goal_progress(user_id, goal_id)
        return True, "Hito actualizado."
    except Exception as exc:
        return False, f"Error al actualizar hito: {exc}"


def delete_goal_milestone(
    user_id: str,
    milestone_id: str,
    goal_id: str,
) -> Tuple[bool, str]:
    """Elimina un hito de una meta y recalcula el progreso global."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("goal_milestones").delete().eq("id", milestone_id).eq("user_id", user_id).execute()
        recalculate_and_persist_goal_progress(user_id, goal_id)
        return True, "Hito eliminado."
    except Exception as exc:
        return False, f"Error al eliminar hito: {exc}"


def delete_personal_goal(user_id: str, goal_id: str) -> Tuple[bool, str]:
    """Elimina una meta personal y sus hitos en cascada."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("personal_goals").delete().eq("id", goal_id).eq("user_id", user_id).execute()
        clear_habits_cache()
        return True, "Meta personal eliminada."
    except Exception as exc:
        return False, f"Error al eliminar meta: {exc}"
