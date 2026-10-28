"""
Motor algorítmico de sobrecarga progresiva (4 estados), cálculo de 1RM (Epley y Brzycki),
analítica de descanso inter-serie y densidad (ratio trabajo/recuperación y correlación RPE),
agregador de volumen muscular ponderado (1.0 primario / 0.5 secundario) en 8 horizontes
temporales (1D, 1W/7D, 2W/14D, 1M, 2M, 3M, 6M, YTD, 1Y) y capa CRUD en Supabase.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from src.auth.supabase_client import get_supabase_client
from src.config.settings import MUSCLE_LABELS, TIMEFRAME_CONFIG
from src.models.workout_models import (
    ExerciseModel,
    ProgressionRecommendation,
    RestAndDensityMetrics,
    WorkoutRoutineItemModel,
    WorkoutRoutineModel,
    WorkoutSetModel,
    WorkoutWeeklyPlanModel,
)

# Soporte extendido de horizontes temporales (incluye alias 7D, 14D y YTD)
EXTENDED_TIMEFRAME_CONFIG: Dict[str, Dict[str, Any]] = {
    **TIMEFRAME_CONFIG,
    "7D": {"days": 7, "freq": "D", "label": "Semanal (7d)"},
    "14D": {"days": 14, "freq": "3D", "label": "Quincenal (14d)"},
    "YTD": {"days": 365, "freq": "MS", "label": "Año en Curso (YTD)"},
}


# ============================================================================
# 1. FÓRMULAS FISIOLÓGICAS: 1RM (EPLEY / BRZYCKI), TONELAJE E INTENSIDAD
# ============================================================================

def calculate_epley_1rm(weight_kg: float, reps: int) -> float:
    """Calcula el 1RM Estimado mediante la fórmula de Epley: peso * (1 + reps / 30)."""
    w = max(0.0, float(weight_kg or 0.0))
    r = max(0, int(reps or 0))
    if w <= 0.0 or r <= 0:
        return 0.0
    if r == 1:
        return round(w, 2)
    return round(w * (1.0 + (r / 30.0)), 2)


def calculate_brzycki_1rm(weight_kg: float, reps: int) -> float:
    """Calcula el 1RM Estimado mediante la fórmula de Brzycki: peso * (36 / (37 - reps))."""
    w = max(0.0, float(weight_kg or 0.0))
    r = max(0, int(reps or 0))
    if w <= 0.0 or r <= 0:
        return 0.0
    if r == 1:
        return round(w, 2)
    capped_reps = min(36, r)
    return round(w * (36.0 / (37.0 - capped_reps)), 2)


def calculate_estimated_1rm(
    weight_kg: float,
    reps: int,
    formula: Literal["epley", "brzycki"] = "epley",
) -> float:
    """Calcula el 1RM estimado según la fórmula seleccionada ('epley' por defecto o 'brzycki')."""
    if formula == "brzycki":
        return calculate_brzycki_1rm(weight_kg, reps)
    return calculate_epley_1rm(weight_kg, reps)


def calculate_relative_intensity_pct(weight_kg: float, estimated_1rm: float) -> float:
    """Calcula la intensidad relativa (% del 1RM) de una serie."""
    w = max(0.0, float(weight_kg or 0.0))
    rm = max(0.0, float(estimated_1rm or 0.0))
    if w <= 0.0 or rm <= 0.0:
        return 0.0
    return round(min(100.0, (w / rm) * 100.0), 1)


def is_set_personal_record(
    weight_kg: float,
    reps: int,
    set_type: str,
    historical_sets: List[Dict[str, Any]],
) -> bool:
    """
    Determina si una serie efectiva bate el récord histórico (1RM Epley) del usuario
    en ese ejercicio. Las series de calentamiento ('warmup') se excluyen de récords.
    """
    if (set_type or "working") == "warmup":
        return False
    new_1rm = calculate_epley_1rm(weight_kg, reps)
    if new_1rm <= 0.0:
        return False

    working_history = [
        s for s in historical_sets
        if str(s.get("set_type", "working")) != "warmup"
        and float(s.get("weight_kg") or 0.0) > 0
        and int(s.get("reps") or 0) > 0
    ]
    if not working_history:
        return True

    max_prev_1rm = max(
        calculate_epley_1rm(float(s.get("weight_kg") or 0.0), int(s.get("reps") or 0))
        for s in working_history
    )
    return new_1rm > max_prev_1rm


def _round_to_gym_plate(weight_kg: float, step: float = 0.5) -> float:
    """Redondea cargas al incremento de discos más cercano (por defecto 0.5 kg)."""
    if weight_kg <= 0:
        return 0.0
    return round(round(weight_kg / step) * step, 2)


# ============================================================================
# 2. MOTOR ALGORÍTMICO DE SOBRECARGA PROGRESIVA (4 ESTADOS PRD §2.3)
# ============================================================================

def evaluate_progression_from_sessions(
    session_groups: List[List[Dict[str, Any]]],
    exercise_id: str,
    target_rep_min: int = 8,
    target_rep_max: int = 12,
    target_rpe: float = 8.0,
    progression_step_kg: float = 2.5,
    default_rest_seconds: int = 90,
) -> ProgressionRecommendation:
    """
    Evalúa el historial reciente de sesiones de un ejercicio (ordenadas de más reciente
    a más antigua) y emite una de las 4 prescripciones algorítmicas de sobrecarga progresiva:
    1. UP_WEIGHT_DOWN_REPS (Dominio del Rango)
    2. KEEP_WEIGHT_UP_REPS (Progreso en Rango)
    3. DOWN_WEIGHT_UP_REPS (Fatiga o Caída de Rendimiento)
    4. UP_WEIGHT_STRENGTH_SHIFT (Estancamiento en Meseta - 3 sesiones idénticas)
    """
    # Filtrar solo series efectivas (excluir 'warmup') en cada sesión
    cleaned_sessions: List[List[Dict[str, Any]]] = []
    for sess in session_groups:
        working = [
            s for s in sess
            if str(s.get("set_type", "working")) != "warmup"
            and int(s.get("reps") or 0) > 0
        ]
        if working:
            cleaned_sessions.append(working)

    if not cleaned_sessions:
        return ProgressionRecommendation(
            exercise_id=exercise_id,
            state="FIRST_SESSION",
            badge_label="🎯 Primera Sesión Base",
            badge_color="#3B82F6",
            badge_icon="🎯",
            headline=f"Establece tu carga base para {target_rep_min}–{target_rep_max} reps @ RPE {target_rpe:g}",
            explanation="Registra tu primera sesión efectiva para activar el motor de sobrecarga progresiva.",
            suggested_weight_kg=20.0,
            suggested_reps=target_rep_min,
            suggested_rpe=target_rpe,
            suggested_rest_seconds=default_rest_seconds,
            last_session_summary="Sin sesiones previas registradas",
            estimated_1rm_epley=0.0,
            estimated_1rm_brzycki=0.0,
            relative_intensity_pct=0.0,
        )

    last_sets = cleaned_sessions[0]
    weights = [float(s.get("weight_kg") or 0.0) for s in last_sets]
    reps_list = [int(s.get("reps") or 0) for s in last_sets]
    rpes = [float(s.get("rpe") or 8.0) for s in last_sets]

    ref_weight = max(weights) if weights else 0.0
    avg_reps = sum(reps_list) / len(reps_list)
    min_reps = min(reps_list)
    first_reps = reps_list[0]
    last_reps = reps_list[-1]
    avg_rpe = round(sum(rpes) / len(rpes), 1)
    max_rpe = max(rpes)

    # Mejor serie para cálculo de 1RM (Epley y Brzycki)
    best_set = max(
        last_sets,
        key=lambda s: calculate_epley_1rm(float(s.get("weight_kg") or 0.0), int(s.get("reps") or 0)),
    )
    best_w = float(best_set.get("weight_kg") or 0.0)
    best_r = int(best_set.get("reps") or 0)
    epley_1rm = calculate_epley_1rm(best_w, best_r)
    brzycki_1rm = calculate_brzycki_1rm(best_w, best_r)
    rel_intensity = calculate_relative_intensity_pct(ref_weight, epley_1rm)

    reps_str = ", ".join(str(r) for r in reps_list)
    last_summary = f"Última vez: {ref_weight:g} kg × [{reps_str}] reps @ RPE {avg_rpe:g}"

    # Verificar caída intra-sesión (> 20% entre primera y última serie)
    rep_drop_ratio = ((first_reps - last_reps) / first_reps) if first_reps > 0 else 0.0

    # Verificar estancamiento en meseta (3 sesiones consecutivas con mismo peso y mismas reps promedio)
    is_plateau = False
    if len(cleaned_sessions) >= 3:
        s0, s1, s2 = cleaned_sessions[0], cleaned_sessions[1], cleaned_sessions[2]
        w0 = max(float(x.get("weight_kg") or 0) for x in s0)
        w1 = max(float(x.get("weight_kg") or 0) for x in s1)
        w2 = max(float(x.get("weight_kg") or 0) for x in s2)
        r0 = round(sum(int(x.get("reps") or 0) for x in s0) / len(s0), 1)
        r1 = round(sum(int(x.get("reps") or 0) for x in s1) / len(s1), 1)
        r2 = round(sum(int(x.get("reps") or 0) for x in s2) / len(s2), 1)
        if abs(w0 - w1) < 0.01 and abs(w1 - w2) < 0.01 and r0 <= r1 and r1 <= r2 and min_reps < target_rep_max:
            is_plateau = True

    # REGLA 3: Fatiga o Caída de Rendimiento (DOWN_WEIGHT_UP_REPS)
    if min_reps < target_rep_min or (max_rpe >= 9.5 and rep_drop_ratio > 0.20):
        deload_w = _round_to_gym_plate(ref_weight * 0.915, step=0.5)
        if deload_w >= ref_weight and ref_weight >= progression_step_kg:
            deload_w = max(0.0, ref_weight - progression_step_kg)
        target_deload_reps = target_rep_max + 2
        return ProgressionRecommendation(
            exercise_id=exercise_id,
            state="DOWN_WEIGHT_UP_REPS",
            badge_label="🛡️ Descarga Técnica / Fatiga",
            badge_color="#F59E0B",
            badge_icon="🛡️",
            headline=f"Ajuste Inteligente: Bajar a {deload_w:g} kg × {target_deload_reps} reps",
            explanation=(
                f"{last_summary}. Se detectó fatiga acumulada o repeticiones bajo el piso del rango "
                f"({target_rep_min} reps). Prioriza control técnico y mayor descanso."
            ),
            suggested_weight_kg=deload_w,
            suggested_reps=target_deload_reps,
            suggested_rpe=max(7.0, target_rpe - 0.5),
            suggested_rest_seconds=min(300, default_rest_seconds + 30),
            last_session_summary=last_summary,
            estimated_1rm_epley=epley_1rm,
            estimated_1rm_brzycki=brzycki_1rm,
            relative_intensity_pct=rel_intensity,
        )

    # REGLA 4: Estancamiento en Meseta (UP_WEIGHT_STRENGTH_SHIFT)
    if is_plateau:
        boost_step = max(progression_step_kg, _round_to_gym_plate(ref_weight * 0.05, step=0.5))
        new_w = round(ref_weight + boost_step, 2)
        strength_reps = max(3, target_rep_min - 2)
        return ProgressionRecommendation(
            exercise_id=exercise_id,
            state="UP_WEIGHT_STRENGTH_SHIFT",
            badge_label="🔥 Ruptura de Meseta (Fuerza)",
            badge_color="#8B5CF6",
            badge_icon="🔥",
            headline=f"Ruptura de Meseta: Subir a {new_w:g} kg × {strength_reps} reps",
            explanation=(
                f"Repetiste {ref_weight:g} kg sin avanzar durante 3 sesiones consecutivas. "
                f"Aplica sobrecarga submáxima con descanso extendido."
            ),
            suggested_weight_kg=new_w,
            suggested_reps=strength_reps,
            suggested_rpe=min(9.0, target_rpe + 0.5),
            suggested_rest_seconds=max(120, default_rest_seconds + 30),
            last_session_summary=last_summary,
            estimated_1rm_epley=epley_1rm,
            estimated_1rm_brzycki=brzycki_1rm,
            relative_intensity_pct=rel_intensity,
        )

    # REGLA 1: Dominio del Rango (UP_WEIGHT_DOWN_REPS)
    if all(r >= target_rep_max for r in reps_list) and avg_rpe <= 8.5:
        new_w = round(ref_weight + progression_step_kg, 2)
        return ProgressionRecommendation(
            exercise_id=exercise_id,
            state="UP_WEIGHT_DOWN_REPS",
            badge_label="⚡ Subir Peso",
            badge_color="#10B981",
            badge_icon="⚡",
            headline=f"Sugerencia de Progreso: Subir a {new_w:g} kg (+{progression_step_kg:g} kg) × {target_rep_min} reps",
            explanation=(
                f"{last_summary}. Dominaste el tope del rango ({target_rep_max} reps) con RPE controlado. "
                f"Incrementa la carga hoy y apunta al piso del rango."
            ),
            suggested_weight_kg=new_w,
            suggested_reps=target_rep_min,
            suggested_rpe=target_rpe,
            suggested_rest_seconds=default_rest_seconds,
            last_session_summary=last_summary,
            estimated_1rm_epley=epley_1rm,
            estimated_1rm_brzycki=brzycki_1rm,
            relative_intensity_pct=rel_intensity,
        )

    # REGLA 2: Progreso en Rango (KEEP_WEIGHT_UP_REPS)
    next_reps = min(target_rep_max, int(math.floor(avg_reps)) + 1)
    if next_reps <= int(round(avg_reps)) and next_reps < target_rep_max:
        next_reps += 1
    return ProgressionRecommendation(
        exercise_id=exercise_id,
        state="KEEP_WEIGHT_UP_REPS",
        badge_label="📈 Subir Repeticiones",
        badge_color="#3B82F6",
        badge_icon="📈",
        headline=f"Sugerencia de Progreso: Mantén {ref_weight:g} kg y busca {next_reps} reps por serie",
        explanation=(
            f"{last_summary}. Conserva la carga actual y gana +1 repetición limpia por serie "
            f"hasta dominar las {target_rep_max} reps."
        ),
        suggested_weight_kg=ref_weight,
        suggested_reps=next_reps,
        suggested_rpe=target_rpe,
        suggested_rest_seconds=default_rest_seconds,
        last_session_summary=last_summary,
        estimated_1rm_epley=epley_1rm,
        estimated_1rm_brzycki=brzycki_1rm,
        relative_intensity_pct=rel_intensity,
    )


# ============================================================================
# 3. ANALÍTICA DE DESCANSO INTER-SERIE, DENSIDAD Y CORRELACIÓN RPE/RIR
# ============================================================================

def calculate_rest_and_density_metrics(
    sets: List[Dict[str, Any]],
    total_duration_minutes: Optional[float] = None,
) -> RestAndDensityMetrics:
    """
    Calcula las métricas de descanso promedio, cumplimiento de descanso objetivo,
    ratio de trabajo/recuperación (TUT estimado vs descanso real), densidad de tonelaje
    y correlación de Pearson entre tiempo de descanso y RPE percibido.
    """
    working_sets = [
        s for s in sets
        if str(s.get("set_type", "working")) != "warmup"
        and int(s.get("reps") or 0) > 0
    ]
    if not working_sets:
        return RestAndDensityMetrics()

    rest_actuals = [int(s.get("rest_actual_seconds") or 0) for s in working_sets if int(s.get("rest_actual_seconds") or 0) > 0]
    rest_targets = [int(s.get("rest_target_seconds") or 90) for s in working_sets if int(s.get("rest_target_seconds") or 0) > 0]

    avg_actual = round(sum(rest_actuals) / len(rest_actuals), 1) if rest_actuals else 0.0
    avg_target = round(sum(rest_targets) / len(rest_targets), 1) if rest_targets else 90.0

    if avg_actual > 0 and avg_target > 0:
        deviation = abs(avg_actual - avg_target) / avg_target
        compliance = round(max(0.0, 100.0 - (deviation * 100.0)), 1)
    else:
        compliance = 100.0

    # Tiempo bajo tensión estimado: ~3.5 segundos por repetición efectiva
    avg_reps = sum(int(s.get("reps") or 0) for s in working_sets) / len(working_sets)
    avg_work_sec = max(10.0, avg_reps * 3.5)
    effective_rest = avg_actual if avg_actual > 0 else avg_target
    ratio_val = round(effective_rest / avg_work_sec, 1) if avg_work_sec > 0 else 3.0
    ratio_label = f"1 : {ratio_val:g}"

    total_tonnage = sum(
        float(s.get("weight_kg") or 0.0) * int(s.get("reps") or 0)
        for s in working_sets
    )
    if total_duration_minutes and total_duration_minutes > 0:
        est_minutes = float(total_duration_minutes)
    else:
        total_sec = sum((int(s.get("reps") or 0) * 3.5) + (int(s.get("rest_actual_seconds") or 90)) for s in working_sets)
        est_minutes = max(1.0, total_sec / 60.0)
    tonnage_per_min = round(total_tonnage / est_minutes, 1)

    # Correlación entre tiempo de descanso real y RPE
    paired = [
        (float(s.get("rest_actual_seconds") or 0), float(s.get("rpe") or 8.0))
        for s in working_sets
        if float(s.get("rest_actual_seconds") or 0) > 0 and s.get("rpe") is not None
    ]
    corr_val: Optional[float] = None
    insight = "Registra al menos 3 series con tiempo de descanso para evaluar el impacto en tu RPE/RIR."

    if len(paired) >= 3:
        xs = np.array([p[0] for p in paired], dtype=float)
        ys = np.array([p[1] for p in paired], dtype=float)
        if np.std(xs) > 1e-5 and np.std(ys) > 1e-5:
            corr_val = round(float(np.corrcoef(xs, ys)[0, 1]), 2)
            if corr_val <= -0.30:
                insight = (
                    f"Correlación inversa (r = {corr_val:+.2f}): Descansos más cortos dispararon tu RPE/fatiga. "
                    f"Respetar >= {int(avg_target)}s conserva mejor tu RIR."
                )
            elif corr_val >= 0.30:
                insight = (
                    f"Correlación positiva (r = {corr_val:+.2f}): Tomaste descansos más largos en tus series "
                    f"más pesadas (RPE alto), autorregulando bien la recuperación neural."
                )
            else:
                insight = (
                    f"Estabilidad alta (r = {corr_val:+.2f}): Tu RPE se mantuvo consistente con un descanso "
                    f"promedio de {avg_actual:.0f}s."
                )
        else:
            corr_val = 0.0
            insight = f"Descanso uniforme (~{avg_actual:.0f}s) con esfuerzo RPE estable."

    return RestAndDensityMetrics(
        total_working_sets=len(working_sets),
        avg_rest_actual_seconds=avg_actual,
        avg_rest_target_seconds=avg_target,
        rest_compliance_pct=compliance,
        work_to_rest_ratio_label=ratio_label,
        tonnage_per_min_kg=tonnage_per_min,
        rest_rpe_correlation=corr_val,
        correlation_insight=insight,
    )


# ============================================================================
# 4. ANALÍTICA DE VOLUMEN PONDERADO EN LOS 8 HORIZONTES TEMPORALES (1D A 1Y)
# ============================================================================

def _parse_dt(val: Any) -> Optional[datetime]:
    """Convierte cadenas ISO o datetime a datetime con zona horaria UTC."""
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    if isinstance(val, str) and val:
        try:
            clean = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def calculate_multitemporal_volume(
    sets_records: List[Dict[str, Any]],
    exercises_by_id: Dict[str, Dict[str, Any]],
    timeframe_code: str = "1W",
    metric_mode: Literal["effective_sets", "tonnage_kg"] = "effective_sets",
    muscle_filter: str = "all",
    reference_now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Calcula el volumen muscular ponderado (1.0 músculo primario, 0.5 músculos secundarios,
    0.0 series warmup) en cualquiera de los 8 horizontes temporales:
    1D, 1W (o 7D), 2W (o 14D), 1M, 2M, 3M, 6M, YTD, 1Y.
    """
    tf_key = (timeframe_code or "1W").upper()
    tf_cfg = EXTENDED_TIMEFRAME_CONFIG.get(tf_key, TIMEFRAME_CONFIG["1W"])
    now_utc = reference_now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    if tf_key == "YTD":
        start_curr = datetime(now_utc.year, 1, 1, tzinfo=timezone.utc)
        days_span = max(1, (now_utc - start_curr).days + 1)
    else:
        days_span = int(tf_cfg["days"])
        start_curr = now_utc - timedelta(days=days_span)

    start_prev = start_curr - timedelta(days=days_span)

    # Desglosar cada serie efectiva en impactos musculares (1.0 primario, 0.5 secundarios)
    curr_impacts: List[Dict[str, Any]] = []
    prev_impacts: List[Dict[str, Any]] = []

    for s in sets_records:
        stype = str(s.get("set_type", "working")).lower()
        if stype == "warmup":
            continue

        reps = int(s.get("reps") or 0)
        weight = float(s.get("weight_kg") or 0.0)
        if reps <= 0:
            continue

        tonnage = float(s.get("tonnage_kg") or (weight * reps))
        dt = _parse_dt(s.get("performed_at"))
        if dt is None:
            continue

        ex_id = str(s.get("exercise_id") or "")
        ex = exercises_by_id.get(ex_id, {})
        prim = str(s.get("primary_muscle") or ex.get("primary_muscle") or "chest")
        secs = s.get("secondary_muscles") if "secondary_muscles" in s else (ex.get("secondary_muscles") or [])
        if not isinstance(secs, list):
            secs = []

        # Lista de aportes biomecánicos de esta serie
        contributions: List[Tuple[str, float, float, str]] = [
            (prim, 1.0, tonnage * 1.0, "Primario (1.0x)")
        ]
        for sec_m in secs:
            if sec_m and sec_m != prim:
                contributions.append((str(sec_m), 0.5, tonnage * 0.5, "Secundario (0.5x)"))

        for m_code, eff_sets, eff_tonnage, role_lbl in contributions:
            if muscle_filter != "all" and m_code != muscle_filter:
                continue
            row_impact = {
                "performed_at": dt,
                "muscle_code": m_code,
                "muscle_label": MUSCLE_LABELS.get(m_code, m_code),
                "effective_sets": eff_sets,
                "tonnage_kg": eff_tonnage,
                "role": role_lbl,
            }
            if start_curr <= dt <= now_utc:
                curr_impacts.append(row_impact)
            elif start_prev <= dt < start_curr:
                prev_impacts.append(row_impact)

    val_col = "effective_sets" if metric_mode == "effective_sets" else "tonnage_kg"
    current_total = round(sum(float(x[val_col]) for x in curr_impacts), 1)
    previous_total = round(sum(float(x[val_col]) for x in prev_impacts), 1)

    if previous_total > 0:
        delta_pct = round(((current_total - previous_total) / previous_total) * 100.0, 1)
    elif current_total > 0:
        delta_pct = 100.0
    else:
        delta_pct = 0.0

    # Escalar zona óptima de hipertrofia (10 a 20 series efectivas por semana) al periodo elegido
    scale_weeks = max(1.0 / 7.0, days_span / 7.0)
    opt_min_sets = round(10.0 * scale_weeks, 1)
    opt_max_sets = round(20.0 * scale_weeks, 1)

    # Agregación por grupo muscular
    muscle_totals: Dict[str, Dict[str, float]] = {
        m_code: {"effective_sets": 0.0, "tonnage_kg": 0.0}
        for m_code in MUSCLE_LABELS.keys()
    }
    for x in curr_impacts:
        mc = x["muscle_code"]
        if mc not in muscle_totals:
            muscle_totals[mc] = {"effective_sets": 0.0, "tonnage_kg": 0.0}
        muscle_totals[mc]["effective_sets"] += float(x["effective_sets"])
        muscle_totals[mc]["tonnage_kg"] += float(x["tonnage_kg"])

    by_muscle_list: List[Dict[str, Any]] = []
    for mc, m_label in MUSCLE_LABELS.items():
        if muscle_filter != "all" and mc != muscle_filter:
            continue
        eff_s = round(muscle_totals[mc]["effective_sets"], 1)
        ton_k = round(muscle_totals[mc]["tonnage_kg"], 1)
        if eff_s < opt_min_sets:
            zone = "Mantenimiento / Bajo (<MEV)"
            zone_color = "#94A3B8"
        elif eff_s <= opt_max_sets:
            zone = "Zona Óptima Hipertrofia (MAV)"
            zone_color = "#10B981"
        else:
            zone = "Alto Volumen / Límite MRV"
            zone_color = "#F59E0B"

        by_muscle_list.append(
            {
                "muscle_code": mc,
                "muscle_label": m_label,
                "effective_sets": eff_s,
                "tonnage_kg": ton_k,
                "value": eff_s if metric_mode == "effective_sets" else ton_k,
                "optimal_min_sets": opt_min_sets,
                "optimal_max_sets": opt_max_sets,
                "zone_label": zone,
                "zone_color": zone_color,
            }
        )

    by_muscle_list.sort(key=lambda item: float(item["value"]), reverse=True)

    # Serie temporal agrupada según la frecuencia del horizonte (1D -> H, 1W -> D, 2W -> 3D, etc.)
    timeline_rows: List[Dict[str, Any]] = []
    if curr_impacts:
        df = pd.DataFrame(curr_impacts)
        df["performed_at"] = pd.to_datetime(df["performed_at"], utc=True)
        freq_map = {
            "H": "2h",
            "D": "1D",
            "3D": "3D",
            "W-MON": "W-MON",
            "2W": "2W-MON",
            "MS": "MS",
        }
        pd_freq = freq_map.get(str(tf_cfg["freq"]), "1D")
        grouped = (
            df.set_index("performed_at")
            .resample(pd_freq)[val_col]
            .sum()
            .reset_index()
        )
        for _, row in grouped.iterrows():
            ts = row["performed_at"]
            if tf_key == "1D":
                lbl = ts.strftime("%H:%M")
            elif tf_key in ("6M", "1Y", "YTD"):
                lbl = ts.strftime("%b %Y")
            else:
                lbl = ts.strftime("%d %b")
            timeline_rows.append(
                {
                    "bucket_label": lbl,
                    "value": round(float(row[val_col]), 1),
                }
            )

    return {
        "timeframe_code": tf_key,
        "timeframe_label": tf_cfg["label"],
        "days": days_span,
        "metric_mode": metric_mode,
        "current_total": current_total,
        "previous_total": previous_total,
        "delta_pct": delta_pct,
        "optimal_min_sets": opt_min_sets,
        "optimal_max_sets": opt_max_sets,
        "by_muscle": by_muscle_list,
        "timeline": timeline_rows,
    }


# ============================================================================
# 5. LECTURAS CACHEADAS Y OPERACIONES CRUD EN SUPABASE
# ============================================================================

@st.cache_data(ttl=300)
def fetch_exercises_catalog(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    """Lee el catálogo de ejercicios globales (user_id IS NULL) y propios del usuario."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    res = client.table("exercises").select("*").order("primary_muscle").order("name").execute()
    return res.data or []


@st.cache_data(ttl=300)
def fetch_workout_routines(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    """Lee las plantillas de rutinas activas del usuario."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("workout_routines")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_archived", False)
        .order("display_order", desc=False)
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=300)
def fetch_workout_routine_items(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    """Lee los ejercicios configurados dentro de cada rutina del usuario."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("workout_routine_items")
        .select("*")
        .eq("user_id", user_id)
        .order("order_index", desc=False)
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=300)
def fetch_workout_sessions(
    user_id: str,
    access_token: str,
    days_back: int = 370,
) -> List[Dict[str, Any]]:
    """Lee el historial de sesiones de entrenamiento del usuario."""
    if not user_id or not access_token:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("workout_sessions")
        .select("*")
        .eq("user_id", user_id)
        .gte("started_at", cutoff)
        .order("started_at", desc=True)
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=300)
def fetch_workout_sets(
    user_id: str,
    access_token: str,
    days_back: int = 370,
) -> List[Dict[str, Any]]:
    """Lee el historial de series registradas por el usuario (últimos 370 días para cubrir 1Y + delta)."""
    if not user_id or not access_token:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back * 2)).isoformat()
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("workout_sets")
        .select("*")
        .eq("user_id", user_id)
        .gte("performed_at", cutoff)
        .order("performed_at", desc=True)
        .execute()
    )
    return res.data or []


def clear_workout_cache() -> None:
    """Invalida selectivamente todas las cachés del Pilar 1 tras operaciones de escritura."""
    fetch_exercises_catalog.clear()
    fetch_workout_routines.clear()
    fetch_workout_routine_items.clear()
    fetch_workout_sessions.clear()
    fetch_workout_sets.clear()
    fetch_weekly_workout_plan.clear()
    try:
        from src.views.home_hub_view import _fetch_hub_summary_counts
        _fetch_hub_summary_counts.clear()
    except Exception:
        pass


def get_exercise_recommendation(
    user_id: str,
    exercise_id: str,
    all_user_sets: List[Dict[str, Any]],
    target_rep_min: int = 8,
    target_rep_max: int = 12,
    target_rpe: float = 8.0,
    progression_step_kg: float = 2.5,
    default_rest_seconds: int = 90,
) -> ProgressionRecommendation:
    """
    Agrupa las series históricas del usuario para `exercise_id` por `session_id`
    (de la sesión más reciente a la más antigua) y ejecuta el motor de sobrecarga progresiva.
    """
    ex_sets = [
        s for s in all_user_sets
        if str(s.get("exercise_id")) == str(exercise_id)
        and str(s.get("user_id", user_id)) == str(user_id)
    ]
    # Ordenar por performed_at DESC y luego set_number ASC
    ex_sets.sort(
        key=lambda x: (str(x.get("performed_at") or ""), -int(x.get("set_number") or 1)),
        reverse=True,
    )

    sessions_ordered: List[List[Dict[str, Any]]] = []
    seen_sessions: Dict[str, List[Dict[str, Any]]] = {}
    session_order_keys: List[str] = []

    for s in ex_sets:
        sid = str(s.get("session_id") or "")
        if not sid:
            continue
        if sid not in seen_sessions:
            seen_sessions[sid] = []
            session_order_keys.append(sid)
        seen_sessions[sid].append(s)

    for sid in session_order_keys[:4]:
        s_list = sorted(seen_sessions[sid], key=lambda item: int(item.get("set_number") or 1))
        sessions_ordered.append(s_list)

    return evaluate_progression_from_sessions(
        session_groups=sessions_ordered,
        exercise_id=exercise_id,
        target_rep_min=target_rep_min,
        target_rep_max=target_rep_max,
        target_rpe=target_rpe,
        progression_step_kg=progression_step_kg,
        default_rest_seconds=default_rest_seconds,
    )


def create_custom_exercise(
    user_id: str,
    name: str,
    equipment: str,
    primary_muscle: str,
    secondary_muscles: List[str],
    movement_pattern: str = "compound",
    notes: str = "",
) -> Tuple[bool, str]:
    """Crea un ejercicio personalizado para el usuario con ponderación 1.0 primario / 0.5 secundario."""
    try:
        access_token = st.session_state.get("access_token") or ""
        validated = ExerciseModel(
            user_id=user_id,
            name=name.strip(),
            equipment=equipment,  # type: ignore[arg-type]
            primary_muscle=primary_muscle,  # type: ignore[arg-type]
            secondary_muscles=[m for m in secondary_muscles if m != primary_muscle],  # type: ignore[misc]
            movement_pattern=movement_pattern,  # type: ignore[arg-type]
            notes=notes.strip(),
        )
        payload = validated.model_dump(exclude={"id"})
        client = get_supabase_client(access_token=access_token)
        try:
            client.table("exercises").insert(payload).execute()
        except Exception:
            legacy_payload = {k: v for k, v in payload.items() if k != "notes"}
            client.table("exercises").insert(legacy_payload).execute()
        clear_workout_cache()
        return True, f"Ejercicio «{validated.name}» agregado al catálogo."
    except Exception as exc:
        return False, f"Error al crear ejercicio: {exc}"


def update_exercise_in_catalog(
    user_id: str,
    exercise_id: str,
    name: str,
    equipment: str,
    primary_muscle: str,
    secondary_muscles: List[str],
    movement_pattern: str = "compound",
    notes: str = "",
) -> Tuple[bool, str]:
    """
    Actualiza un ejercicio ya registrado en `public.exercises` conservando su `id` (UUID)
    para no romper la integridad referencial ni el historial de `workout_sets` pasados.
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        validated = ExerciseModel(
            id=exercise_id,
            user_id=user_id,
            name=name.strip(),
            equipment=equipment,  # type: ignore[arg-type]
            primary_muscle=primary_muscle,  # type: ignore[arg-type]
            secondary_muscles=[m for m in secondary_muscles if m != primary_muscle],  # type: ignore[misc]
            movement_pattern=movement_pattern,  # type: ignore[arg-type]
            notes=notes.strip(),
        )
        payload = {
            "name": validated.name,
            "equipment": validated.equipment,
            "primary_muscle": validated.primary_muscle,
            "secondary_muscles": validated.secondary_muscles,
            "movement_pattern": validated.movement_pattern,
            "notes": validated.notes,
        }
        client = get_supabase_client(access_token=access_token)
        try:
            client.table("exercises").update(payload).eq("id", exercise_id).execute()
        except Exception:
            legacy_payload = {k: v for k, v in payload.items() if k != "notes"}
            client.table("exercises").update(legacy_payload).eq("id", exercise_id).execute()

        clear_workout_cache()
        return True, f"Ejercicio «{validated.name}» actualizado sin afectar tu historial de sets."
    except Exception as exc:
        return False, f"Error al actualizar el ejercicio: {exc}"


def create_workout_routine_with_items(
    user_id: str,
    name: str,
    description: str,
    accent_color: str,
    items: List[Dict[str, Any]],
) -> Tuple[bool, str]:
    """Crea una plantilla de rutina junto con su lista ordenada de ejercicios y rangos objetivo."""
    try:
        access_token = st.session_state.get("access_token") or ""
        existing = fetch_workout_routines(user_id, access_token)
        next_order = max((int(r.get("display_order") or 0) for r in existing), default=0) + 1

        validated_routine = WorkoutRoutineModel(
            user_id=user_id,
            name=name.strip(),
            description=description.strip(),
            accent_color=accent_color,
            display_order=next_order,
            is_archived=False,
        )
        client = get_supabase_client(access_token=access_token)
        r_res = (
            client.table("workout_routines")
            .insert(validated_routine.model_dump(exclude={"id"}))
            .execute()
        )
        if not r_res.data:
            return False, "No se pudo crear la rutina."

        routine_id = str(r_res.data[0]["id"])
        item_rows = []
        for idx, it in enumerate(items, start=1):
            validated_it = WorkoutRoutineItemModel(
                user_id=user_id,
                routine_id=routine_id,
                exercise_id=str(it["exercise_id"]),
                order_index=idx,
                target_sets=int(it.get("target_sets", 3)),
                target_rep_min=int(it.get("target_rep_min", 8)),
                target_rep_max=int(it.get("target_rep_max", 12)),
                target_rpe=float(it.get("target_rpe", 8.0)),
                progression_step_kg=float(it.get("progression_step_kg", 2.5)),
                default_rest_seconds=int(it.get("default_rest_seconds", 90)),
                notes=str(it.get("notes", "")),
            )
            item_rows.append(validated_it.model_dump(exclude={"id"}))

        if item_rows:
            try:
                client.table("workout_routine_items").insert(item_rows).execute()
            except Exception:
                # Fallback compatible si aún no se ejecutó 03_sprint3_workout_rest_migration.sql
                fallback_rows = [
                    {k: v for k, v in row.items() if k != "default_rest_seconds"}
                    for row in item_rows
                ]
                client.table("workout_routine_items").insert(fallback_rows).execute()

        clear_workout_cache()
        return True, f"Rutina «{validated_routine.name}» creada con {len(item_rows)} ejercicios."
    except Exception as exc:
        return False, f"Error al crear rutina: {exc}"


def delete_workout_routine(user_id: str, routine_id: str) -> Tuple[bool, str]:
    """Elimina una plantilla de rutina del usuario."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("workout_routines").delete().eq("id", routine_id).eq("user_id", user_id).execute()
        clear_workout_cache()
        return True, "Rutina eliminada."
    except Exception as exc:
        return False, f"Error al eliminar rutina: {exc}"


def duplicate_workout_routine(
    user_id: str,
    routine_id: str,
) -> Tuple[bool, str]:
    """
    Clona cualquier rutina existente con un solo clic, creando una copia independiente
    llamada «[Nombre Original] (Copia)» en Supabase con todos sus ejercicios y parámetros precargados.
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        routines = fetch_workout_routines(user_id, access_token)
        all_items = fetch_workout_routine_items(user_id, access_token)

        src_routine = next((r for r in routines if str(r.get("id")) == str(routine_id)), None)
        if not src_routine:
            return False, "No se encontró la rutina origen para duplicar."

        orig_name = str(src_routine.get("name") or "Rutina").strip()
        copy_name = f"{orig_name} (Copia)"[:100]
        src_desc = str(src_routine.get("description") or "")
        src_color = str(src_routine.get("accent_color") or "#FF5500")

        src_items = [
            it for it in all_items if str(it.get("routine_id")) == str(routine_id)
        ]
        src_items.sort(key=lambda x: int(x.get("order_index") or 1))

        cloned_items_payload = [
            {
                "exercise_id": str(it["exercise_id"]),
                "target_sets": int(it.get("target_sets") or 3),
                "target_rep_min": int(it.get("target_rep_min") or 8),
                "target_rep_max": int(it.get("target_rep_max") or 12),
                "target_rpe": float(it.get("target_rpe") or 8.0),
                "progression_step_kg": float(it.get("progression_step_kg") or 2.5),
                "default_rest_seconds": int(it.get("default_rest_seconds") or 90),
                "notes": str(it.get("notes") or ""),
            }
            for it in src_items
        ]

        ok, _ = create_workout_routine_with_items(
            user_id=user_id,
            name=copy_name,
            description=src_desc,
            accent_color=src_color,
            items=cloned_items_payload,
        )
        if ok:
            return True, f"Rutina duplicada como «{copy_name}» ({len(cloned_items_payload)} ejercicios)."
        return False, "No se pudo duplicar la rutina."
    except Exception as exc:
        return False, f"Error al duplicar rutina: {exc}"


def update_workout_routine_with_items(
    user_id: str,
    routine_id: str,
    name: str,
    description: str,
    accent_color: str,
    items: List[Dict[str, Any]],
) -> Tuple[bool, str]:
    """
    Actualiza el encabezado de una plantilla de rutina y sincroniza su lista de ejercicios
    (ordenados mediante `order_index`, permitiendo intercalar, reordenar, editar series/descanso
    o retirar ejercicios sin afectar otras rutinas ni sesiones pasadas).
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)

        client.table("workout_routines").update(
            {
                "name": name.strip() or "Rutina",
                "description": description.strip(),
                "accent_color": accent_color or "#FF5500",
            }
        ).eq("id", routine_id).eq("user_id", user_id).execute()

        # Reemplazar los items de esta rutina con los nuevos items en el orden exacto
        client.table("workout_routine_items").delete().eq("routine_id", routine_id).eq(
            "user_id", user_id
        ).execute()

        item_rows = []
        for idx, it in enumerate(items, start=1):
            r_min = max(1, int(it.get("target_rep_min", 8)))
            r_max = max(r_min, int(it.get("target_rep_max", 12)))
            validated_it = WorkoutRoutineItemModel(
                user_id=user_id,
                routine_id=routine_id,
                exercise_id=str(it["exercise_id"]),
                order_index=idx,
                target_sets=max(1, min(15, int(it.get("target_sets", 3)))),
                target_rep_min=r_min,
                target_rep_max=r_max,
                target_rpe=min(10.0, max(5.0, float(it.get("target_rpe", 8.0)))),
                progression_step_kg=max(0.5, float(it.get("progression_step_kg", 2.5))),
                default_rest_seconds=min(900, max(10, int(it.get("default_rest_seconds", 90)))),
                notes=str(it.get("notes", "")),
            )
            item_rows.append(validated_it.model_dump(exclude={"id"}))

        if item_rows:
            try:
                client.table("workout_routine_items").insert(item_rows).execute()
            except Exception:
                fallback_rows = [
                    {k: v for k, v in row.items() if k != "default_rest_seconds"}
                    for row in item_rows
                ]
                client.table("workout_routine_items").insert(fallback_rows).execute()

        clear_workout_cache()
        return True, f"Plantilla «{name.strip()}» actualizada ({len(item_rows)} ejercicios en orden)."
    except Exception as exc:
        return False, f"Error al actualizar la rutina: {exc}"


def move_routine_item_order(
    user_id: str,
    routine_id: str,
    item_index: int,
    direction: Literal["up", "down"],
) -> Tuple[bool, str]:
    """
    Mueve un ejercicio una posición arriba ('up') o abajo ('down') dentro de una rutina
    y persiste el nuevo `order_index` en Supabase.
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        all_items = fetch_workout_routine_items(user_id, access_token)
        r_items = [it for it in all_items if str(it.get("routine_id")) == str(routine_id)]
        r_items.sort(key=lambda x: int(x.get("order_index") or 1))

        if not r_items or item_index < 0 or item_index >= len(r_items):
            return False, "Posición fuera de rango."

        target_idx = item_index - 1 if direction == "up" else item_index + 1
        if target_idx < 0 or target_idx >= len(r_items):
            return False, "El ejercicio ya está en el extremo de la rutina."

        r_items[item_index], r_items[target_idx] = r_items[target_idx], r_items[item_index]

        client = get_supabase_client(access_token=access_token)
        for new_pos, row in enumerate(r_items, start=1):
            if row.get("id"):
                client.table("workout_routine_items").update({"order_index": new_pos}).eq(
                    "id", str(row["id"])
                ).eq("user_id", user_id).execute()

        clear_workout_cache()
        return True, "Orden de ejercicios actualizado."
    except Exception as exc:
        return False, f"Error al reordenar ejercicio: {exc}"


# ============================================================================
# 6. PLANIFICADOR SEMANAL DE ENTRENAMIENTOS (CALENDARIO / AGENDA SEMANAL)
# ============================================================================

def get_monday_of_week(ref_date: Optional[date] = None) -> date:
    """Retorna el lunes (inicio de semana) correspondiente a `ref_date`."""
    d = ref_date or date.today()
    return d - timedelta(days=d.weekday())


@st.cache_data(ttl=180)
def fetch_weekly_workout_plan(
    user_id: str,
    access_token: str,
    week_start_iso: str,
) -> List[Dict[str, Any]]:
    """
    Consulta los entrenamientos planificados para la semana que inicia en `week_start_iso`.
    Si la tabla `workout_weekly_plan` aún no existe en Supabase, retorna lista vacía
    (la vista combina con el respaldo en `st.session_state`).
    """
    if not user_id or not access_token:
        return []
    try:
        start_d = date.fromisoformat(week_start_iso[:10])
    except ValueError:
        start_d = get_monday_of_week()
    end_d = start_d + timedelta(days=6)

    try:
        client = get_supabase_client(access_token=access_token)
        res = (
            client.table("workout_weekly_plan")
            .select("*")
            .eq("user_id", user_id)
            .gte("plan_date", start_d.isoformat())
            .lte("plan_date", end_d.isoformat())
            .order("plan_date", desc=False)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def upsert_weekly_workout_plan_day(
    user_id: str,
    plan_date: date,
    focus_title: str,
    routine_id: Optional[str] = None,
    status: str = "planned",
    notes: str = "",
) -> Tuple[bool, str]:
    """
    Guarda o actualiza la planificación de entrenamiento para una fecha específica
    en `public.workout_weekly_plan` (con respaldo automático en `st.session_state`).
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        validated = WorkoutWeeklyPlanModel(
            user_id=user_id,
            plan_date=plan_date,
            day_of_week=plan_date.weekday(),
            focus_title=focus_title.strip() or "Entrenamiento",
            routine_id=routine_id if routine_id else None,
            status=status,  # type: ignore[arg-type]
            notes=notes.strip(),
        )
        payload = validated.model_dump(exclude={"id"})
        payload["plan_date"] = validated.plan_date.isoformat()
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Guardar siempre en respaldo de sesión y en Supabase
        local_store: Dict[str, Dict[str, Any]] = st.session_state.setdefault(
            "local_weekly_workout_plan", {}
        )
        local_store[payload["plan_date"]] = payload

        if access_token:
            try:
                client = get_supabase_client(access_token=access_token)
                client.table("workout_weekly_plan").upsert(
                    payload,
                    on_conflict="user_id,plan_date",
                ).execute()
            except Exception:
                pass

        clear_workout_cache()
        return True, f"Plan del {plan_date.strftime('%d/%m/%Y')} guardado ({validated.focus_title})."
    except Exception as exc:
        return False, f"Error al guardar en el planificador semanal: {exc}"


def delete_weekly_workout_plan_day(
    user_id: str,
    plan_date: date,
) -> Tuple[bool, str]:
    """Elimina la programación de un día en el planificador semanal."""
    try:
        access_token = st.session_state.get("access_token") or ""
        iso_d = plan_date.isoformat()
        local_store: Dict[str, Dict[str, Any]] = st.session_state.setdefault(
            "local_weekly_workout_plan", {}
        )
        local_store.pop(iso_d, None)

        if access_token:
            try:
                client = get_supabase_client(access_token=access_token)
                client.table("workout_weekly_plan").delete().eq("user_id", user_id).eq(
                    "plan_date", iso_d
                ).execute()
            except Exception:
                pass

        clear_workout_cache()
        return True, f"Día {plan_date.strftime('%d/%m')} limpiado del planificador."
    except Exception as exc:
        return False, f"Error al limpiar día del planificador: {exc}"


def seed_starter_routines_for_user(
    user_id: str,
    exercises: List[Dict[str, Any]],
) -> Tuple[bool, str]:
    """
    Crea 3 rutinas base de hipertrofia (Push A, Pull B, Legs C) usando el catálogo global
    para que el usuario pueda entrenar de inmediato en 1 toque.
    """
    if not exercises:
        return False, "El catálogo de ejercicios está vacío. Ejecuta sql/02_seed_catalog.sql primero."

    by_name = {str(e.get("name", "")).lower(): str(e["id"]) for e in exercises}

    def _find_ex(substr: str, fallback_muscle: str) -> Optional[str]:
        for name_k, eid in by_name.items():
            if substr.lower() in name_k:
                return eid
        for e in exercises:
            if e.get("primary_muscle") == fallback_muscle:
                return str(e["id"])
        return str(exercises[0]["id"]) if exercises else None

    templates = [
        {
            "name": "Push A · Pecho, Hombro y Tríceps",
            "desc": "Énfasis en empuje horizontal/vertical y deltoides lateral",
            "color": "#FF5500",
            "items": [
                {"ex": _find_ex("banca plano", "chest"), "sets": 3, "min": 6, "max": 10, "rpe": 8.0, "step": 2.5, "rest": 150},
                {"ex": _find_ex("inclinado con mancuernas", "chest"), "sets": 3, "min": 8, "max": 12, "rpe": 8.5, "step": 2.0, "rest": 120},
                {"ex": _find_ex("militar", "front_delts"), "sets": 3, "min": 8, "max": 10, "rpe": 8.0, "step": 2.5, "rest": 120},
                {"ex": _find_ex("elevaciones laterales", "side_delts"), "sets": 4, "min": 12, "max": 15, "rpe": 8.5, "step": 1.0, "rest": 60},
                {"ex": _find_ex("extensión de tríceps", "triceps"), "sets": 3, "min": 10, "max": 14, "rpe": 8.5, "step": 2.5, "rest": 75},
            ],
        },
        {
            "name": "Pull B · Espalda Completa y Bíceps",
            "desc": "Amplitud dorsal, densidad escapular y flexores del codo",
            "color": "#3B82F6",
            "items": [
                {"ex": _find_ex("jalón al pecho", "back_lats"), "sets": 3, "min": 8, "max": 12, "rpe": 8.0, "step": 2.5, "rest": 120},
                {"ex": _find_ex("remo con barra", "back_upper"), "sets": 3, "min": 8, "max": 10, "rpe": 8.0, "step": 2.5, "rest": 150},
                {"ex": _find_ex("remo sentado", "back_upper"), "sets": 3, "min": 10, "max": 12, "rpe": 8.5, "step": 2.5, "rest": 90},
                {"ex": _find_ex("face pull", "rear_delts"), "sets": 3, "min": 12, "max": 15, "rpe": 8.0, "step": 2.0, "rest": 60},
                {"ex": _find_ex("curl de bíceps con barra", "biceps"), "sets": 3, "min": 8, "max": 12, "rpe": 8.5, "step": 2.0, "rest": 75},
            ],
        },
        {
            "name": "Legs C · Pierna Hipertrofia y Glúteo",
            "desc": "Cadena anterior, cadena posterior y pantorrillas",
            "color": "#10B981",
            "items": [
                {"ex": _find_ex("sentadilla libre", "quads"), "sets": 3, "min": 6, "max": 10, "rpe": 8.0, "step": 2.5, "rest": 180},
                {"ex": _find_ex("peso muerto rumano", "hamstrings"), "sets": 3, "min": 8, "max": 12, "rpe": 8.0, "step": 2.5, "rest": 150},
                {"ex": _find_ex("prensa de piernas", "quads"), "sets": 3, "min": 10, "max": 14, "rpe": 8.5, "step": 5.0, "rest": 120},
                {"ex": _find_ex("curl femoral", "hamstrings"), "sets": 3, "min": 10, "max": 15, "rpe": 8.5, "step": 2.5, "rest": 75},
                {"ex": _find_ex("elevación de talones", "calves"), "sets": 4, "min": 12, "max": 16, "rpe": 9.0, "step": 2.5, "rest": 60},
            ],
        },
    ]

    for tpl in templates:
        valid_items = [
            {
                "exercise_id": it["ex"],
                "target_sets": it["sets"],
                "target_rep_min": it["min"],
                "target_rep_max": it["max"],
                "target_rpe": it["rpe"],
                "progression_step_kg": it["step"],
                "default_rest_seconds": it["rest"],
            }
            for it in tpl["items"]
            if it["ex"]
        ]
        create_workout_routine_with_items(
            user_id=user_id,
            name=tpl["name"],
            description=tpl["desc"],
            accent_color=tpl["color"],
            items=valid_items,
        )

    return True, "3 Rutinas base (Push / Pull / Legs) creadas exitosamente."


def save_completed_workout_session(
    user_id: str,
    session_title: str,
    started_at: datetime,
    ended_at: datetime,
    sets_logged: List[Dict[str, Any]],
    routine_id: Optional[str] = None,
    perceived_fatigue: Optional[int] = None,
    bodyweight_kg: Optional[float] = None,
    notes: str = "",
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Guarda de forma transaccional la sesión de entrenamiento (workout_sessions)
    y todas sus series (workout_sets) incluyendo RPE, RIR, rest_target_seconds y rest_actual_seconds.
    """
    if not sets_logged:
        return False, "Registra al menos 1 serie antes de finalizar el entrenamiento.", None

    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)

        session_payload: Dict[str, Any] = {
            "user_id": user_id,
            "routine_id": routine_id if routine_id else None,
            "session_title": session_title.strip() or "Sesión de Entrenamiento",
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "perceived_fatigue": int(perceived_fatigue) if perceived_fatigue else None,
            "bodyweight_kg": float(bodyweight_kg) if bodyweight_kg and bodyweight_kg > 0 else None,
            "notes": notes.strip(),
        }
        sess_res = client.table("workout_sessions").insert(session_payload).execute()
        if not sess_res.data:
            return False, "No se pudo guardar el encabezado de la sesión.", None

        session_id = str(sess_res.data[0]["id"])
        set_rows_full: List[Dict[str, Any]] = []

        for idx, s in enumerate(sets_logged, start=1):
            rpe_val = float(s.get("rpe") or 8.0)
            rir_val = float(s.get("rir") if s.get("rir") is not None else max(0.0, 10.0 - rpe_val))
            validated_set = WorkoutSetModel(
                user_id=user_id,
                session_id=session_id,
                exercise_id=str(s["exercise_id"]),
                set_number=int(s.get("set_number") or idx),
                set_type=str(s.get("set_type", "working")),  # type: ignore[arg-type]
                weight_kg=float(s.get("weight_kg") or 0.0),
                reps=int(s.get("reps") or 0),
                rpe=rpe_val,
                rir=min(5.0, max(0.0, rir_val)),
                rest_target_seconds=int(s.get("rest_target_seconds") or 90),
                rest_actual_seconds=int(s.get("rest_actual_seconds") or 0),
                is_pr=bool(s.get("is_pr", False)),
                notes=str(s.get("notes") or ""),
                performed_at=_parse_dt(s.get("performed_at")) or datetime.now(timezone.utc),
            )
            row_dict = validated_set.model_dump(exclude={"id"})
            if isinstance(row_dict.get("performed_at"), datetime):
                row_dict["performed_at"] = row_dict["performed_at"].isoformat()
            set_rows_full.append(row_dict)

        try:
            client.table("workout_sets").insert(set_rows_full).execute()
        except Exception:
            # Fallback compatible si aún no se corrió 03_sprint3_workout_rest_migration.sql
            legacy_keys = {
                "user_id", "session_id", "exercise_id", "set_number",
                "set_type", "weight_kg", "reps", "rpe", "is_pr", "performed_at"
            }
            fallback_rows = [
                {k: v for k, v in row.items() if k in legacy_keys}
                for row in set_rows_full
            ]
            client.table("workout_sets").insert(fallback_rows).execute()

        clear_workout_cache()

        working_sets = [s for s in sets_logged if str(s.get("set_type", "working")) != "warmup"]
        total_tonnage = round(
            sum(float(s.get("weight_kg") or 0.0) * int(s.get("reps") or 0) for s in working_sets),
            1,
        )
        prs_count = sum(1 for s in working_sets if s.get("is_pr"))
        rest_metrics = calculate_rest_and_density_metrics(sets_logged)

        summary = {
            "session_id": session_id,
            "session_title": session_title,
            "total_sets": len(sets_logged),
            "working_sets": len(working_sets),
            "total_tonnage_kg": total_tonnage,
            "prs_count": prs_count,
            "avg_rest_seconds": rest_metrics.avg_rest_actual_seconds,
            "tonnage_per_min_kg": rest_metrics.tonnage_per_min_kg,
            "work_to_rest_ratio": rest_metrics.work_to_rest_ratio_label,
        }
        return True, f"¡Entrenamiento guardado! {len(working_sets)} series efectivas · {total_tonnage:,.1f} kg movidos.", summary
    except Exception as exc:
        return False, f"Error al guardar la sesión en Supabase: {exc}", None
