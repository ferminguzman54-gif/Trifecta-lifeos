"""
Módulo 1: Entrenamiento Físico, Motor Algorítmico de Sobrecarga Progresiva,
Cronómetro de Descanso Inteligente (Client-Side HTML5/JS) y Analítica Multitemporal (1D a 1Y).
Implementado según 01_PRD (§2), 02_TRD (§5.1), 03_Appflow (§4), 04_UI_UX (§3.2-3.3) y Sprint 3.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

import plotly.graph_objects as go
import streamlit as st

from src.auth.session_manager import get_current_user_id
from src.components.chart_builders import apply_mobile_dark_layout, render_mobile_plotly
from src.components.rest_timer_widget import render_client_rest_timer
from src.config.settings import MUSCLE_LABELS
from src.config.theme import PALETTE, render_pillar_header
from src.models.workout_models import (
    EQUIPMENT_LABELS,
    REST_PRESETS_SECONDS,
    SET_TYPE_LABELS,
)
from src.services.progression_engine import (
    EXTENDED_TIMEFRAME_CONFIG,
    calculate_brzycki_1rm,
    calculate_epley_1rm,
    calculate_multitemporal_volume,
    calculate_relative_intensity_pct,
    calculate_rest_and_density_metrics,
    create_custom_exercise,
    create_workout_routine_with_items,
    delete_workout_routine,
    fetch_exercises_catalog,
    fetch_workout_routine_items,
    fetch_workout_routines,
    fetch_workout_sessions,
    fetch_workout_sets,
    get_exercise_recommendation,
    is_set_personal_record,
    save_completed_workout_session,
    seed_starter_routines_for_user,
)


# ============================================================================
# 1. ESTADO DE SESIÓN EN VIVO (st.session_state["active_workout"])
# ============================================================================

def render_kpi_card(
    label: str,
    value: str,
    delta_text: str = "",
    delta_positive: bool = True,
    accent_color: str = "#3B82F6",
) -> None:
    """Tarjeta KPI. El HTML va pegado a la columna 0 para que Markdown no lo trate como bloque de código."""
    d_col = "#10B981" if delta_positive else "#EF4444"
    delta_html = (
        f'<div style="display:inline-block; margin-top:6px; padding:2px 8px; border-radius:999px; font-size:0.70rem; font-weight:700; white-space:nowrap; color:{d_col}; background:{d_col}1F; border:1px solid {d_col}55;">{delta_text}</div>'
        if delta_text
        else ""
    )
    st.markdown(
f"""
<div style="background:#121722; border:1px solid #263044; border-left:4px solid {accent_color}; border-radius:12px; padding:10px 12px; margin-bottom:6px;">
<div style="font-size:0.68rem; color:#94A3B8; text-transform:uppercase; letter-spacing:0.05em;">{label}</div>
<div class="trifecta-kpi-value" style="font-size:1.35rem; font-weight:800; color:#F8FAFC; margin-top:4px;">{value}</div>
{delta_html}
</div>
""",
        unsafe_allow_html=True,
    )


def _start_active_workout(
    routine: Optional[Dict[str, Any]],
    routine_items: List[Dict[str, Any]],
    exercises_by_id: Dict[str, Dict[str, Any]],
) -> None:
    """Inicializa una sesión de entrenamiento en vivo en memoria."""
    if routine:
        title = str(routine.get("name", "Rutina"))
        rid = str(routine["id"])
        planned_items = [it for it in routine_items if str(it.get("routine_id")) == rid]
    else:
        title = "Sesión Libre de Entrenamiento"
        rid = None
        planned_items = []

    first_ex_id = (
        str(planned_items[0]["exercise_id"])
        if planned_items
        else (next(iter(exercises_by_id.keys()), "") if exercises_by_id else "")
    )
    first_rest = int(planned_items[0].get("default_rest_seconds") or 90) if planned_items else 90

    st.session_state["active_workout"] = {
        "routine_id": rid,
        "session_title": title,
        "started_at": datetime.now(timezone.utc),
        "planned_items": planned_items,
        "selected_exercise_id": first_ex_id,
        "sets": [],
        "rest_target_s": first_rest,
        "rest_timer_start_ms": 0,
        "rest_timer_running": False,
        "last_set_saved_epoch": None,
        "prefill_weight": None,
        "prefill_reps": None,
        "prefill_rpe": None,
    }


# ============================================================================
# 2. MODALES NATIVOS (@st.dialog) PARA CREAR EJERCICIOS Y RUTINAS
# ============================================================================

@st.dialog("➕ Nuevo Ejercicio Personalizado")
def _open_create_exercise_dialog(user_id: str) -> None:
    """Modal móvil para agregar un ejercicio personalizado con músculos primario (1.0x) y secundarios (0.5x)."""
    st.caption("El motor ponderará 1.0 serie efectiva al músculo primario y 0.5 a cada músculo secundario.")
    with st.form("form_create_custom_exercise", clear_on_submit=False):
        name_in = st.text_input("Nombre del Ejercicio", placeholder="Ej. Press Pendular / Remo Meadows")
        col_eq, col_pat = st.columns(2)
        with col_eq:
            eq_in = st.selectbox(
                "Equipo",
                options=list(EQUIPMENT_LABELS.keys()),
                format_func=lambda k: EQUIPMENT_LABELS.get(k, k),
            )
        with col_pat:
            pat_in = st.selectbox(
                "Patrón Biomecánico",
                options=["compound", "isolation"],
                format_func=lambda p: "Compuesto (Multiarticular)" if p == "compound" else "Aislamiento (Monoarticular)",
            )

        prim_in = st.selectbox(
            "Músculo Primario (Factor 1.0x)",
            options=list(MUSCLE_LABELS.keys()),
            format_func=lambda m: MUSCLE_LABELS.get(m, m),
        )
        sec_in = st.multiselect(
            "Músculos Secundarios (Factor 0.5x)",
            options=[m for m in MUSCLE_LABELS.keys() if m != prim_in],
            format_func=lambda m: MUSCLE_LABELS.get(m, m),
        )

        submitted = st.form_submit_button("💾 Guardar Ejercicio", type="primary", use_container_width=True)
        if submitted:
            if not name_in.strip():
                st.error("Ingresa el nombre del ejercicio.")
            else:
                ok, msg = create_custom_exercise(
                    user_id=user_id,
                    name=name_in,
                    equipment=eq_in,
                    primary_muscle=prim_in,
                    secondary_muscles=sec_in,
                    movement_pattern=pat_in,
                )
                if ok:
                    st.toast(msg, icon="🏋️")
                    st.rerun()
                else:
                    st.error(msg)


@st.dialog("📋 Nueva Plantilla de Rutina")
def _open_create_routine_dialog(user_id: str, exercises: List[Dict[str, Any]]) -> None:
    """Modal móvil para construir una plantilla de rutina con rangos de repeticiones, RPE y descanso."""
    st.caption("Selecciona los ejercicios y define el rango objetivo para el motor de sobrecarga progresiva.")
    ex_map = {
        str(e["id"]): f"{e.get('name')} ({MUSCLE_LABELS.get(str(e.get('primary_muscle')), '')})"
        for e in exercises
    }

    with st.form("form_create_workout_routine", clear_on_submit=False):
        r_name = st.text_input("Nombre de la Rutina", placeholder="Ej. Upper Body Hipertrofia / Push A")
        r_desc = st.text_input("Enfoque / Notas", placeholder="Ej. Énfasis pectoral superior y espalda")

        selected_ex_ids = st.multiselect(
            "Ejercicios de la Rutina (en orden de ejecución)",
            options=list(ex_map.keys()),
            format_func=lambda k: ex_map.get(k, k),
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            def_sets = st.number_input("Series / ej.", min_value=1, max_value=10, value=3)
        with c2:
            def_rep_min = st.number_input("Reps Mín.", min_value=1, max_value=30, value=8)
        with c3:
            def_rep_max = st.number_input("Reps Máx.", min_value=1, max_value=40, value=12)

        c4, c5, c6 = st.columns(3)
        with c4:
            def_rpe = st.number_input("RPE Obj.", min_value=6.0, max_value=10.0, value=8.0, step=0.5)
        with c5:
            def_step = st.number_input("Salto (kg)", min_value=0.5, max_value=10.0, value=2.5, step=0.5)
        with c6:
            def_rest = st.selectbox("Descanso (s)", options=[60, 90, 120, 150, 180], index=1)

        submitted = st.form_submit_button("🚀 Crear Rutina", type="primary", use_container_width=True)
        if submitted:
            if not r_name.strip():
                st.error("Ingresa un nombre para la rutina.")
            elif not selected_ex_ids:
                st.error("Selecciona al menos 1 ejercicio para la rutina.")
            else:
                items_payload = [
                    {
                        "exercise_id": eid,
                        "target_sets": int(def_sets),
                        "target_rep_min": int(def_rep_min),
                        "target_rep_max": max(int(def_rep_min), int(def_rep_max)),
                        "target_rpe": float(def_rpe),
                        "progression_step_kg": float(def_step),
                        "default_rest_seconds": int(def_rest),
                    }
                    for eid in selected_ex_ids
                ]
                ok, msg = create_workout_routine_with_items(
                    user_id=user_id,
                    name=r_name,
                    description=r_desc,
                    accent_color="#FF5500",
                    items=items_payload,
                )
                if ok:
                    st.toast(msg, icon="✅")
                    st.rerun()
                else:
                    st.error(msg)


# ============================================================================
# 3. PESTAÑA 1: ENTRENAR AHORA / SESIÓN EN VIVO (@st.fragment)
# ============================================================================

@st.fragment
def _render_live_workout_fragment(
    user_id: str,
    exercises: List[Dict[str, Any]],
    all_historical_sets: List[Dict[str, Any]],
) -> None:
    """
    Fragmento reactivo (@st.fragment) para registrar series en vivo en el gimnasio,
    con autocompletado de cargas previas, banner de sobrecarga progresiva y
    temporizador de descanso inter-serie en primer plano.
    """
    active: Dict[str, Any] = st.session_state.get("active_workout")
    if not active:
        return

    exercises_by_id = {str(e["id"]): e for e in exercises}
    planned_items: List[Dict[str, Any]] = active.get("planned_items") or []
    planned_by_ex = {str(it["exercise_id"]): it for it in planned_items}

    # Resumen rápido de la sesión en curso
    logged_sets: List[Dict[str, Any]] = active.get("sets") or []
    working_logged = [s for s in logged_sets if s.get("set_type") != "warmup"]
    live_tonnage = sum(float(s.get("weight_kg") or 0) * int(s.get("reps") or 0) for s in working_logged)
    live_prs = sum(1 for s in working_logged if s.get("is_pr"))

    st.markdown(
        f"""
        <div style="
            background:linear-gradient(135deg, rgba(255,85,0,0.16) 0%, rgba(18,23,34,0.96) 100%);
            border:1px solid rgba(255,85,0,0.45); border-radius:16px;
            padding:12px 14px; margin-bottom:10px;
        ">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span class="trifecta-pillar-pill" style="background:#FF550033; color:#FF5500;">
                        🔴 SESIÓN EN VIVO
                    </span>
                    <div style="font-size:1.08rem; font-weight:800; color:#F8FAFC; margin-top:4px;">
                        {active.get('session_title')}
                    </div>
                </div>
                <div style="text-align:right; font-family:'JetBrains Mono', monospace;">
                    <div style="font-size:1.05rem; font-weight:800; color:#FF5500;">{live_tonnage:,.0f} kg</div>
                    <div style="font-size:0.74rem; color:#94A3B8;">
                        {len(working_logged)} series ef. · 🏆 {live_prs} PRs
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. VISOR DEL TEMPORIZADOR DE DESCANSO INTELIGENTE EN PRIMER PLANO (Client-Side HTML5/JS)
    curr_ex_id = str(active.get("selected_exercise_id") or "")
    curr_ex = exercises_by_id.get(curr_ex_id, {})
    curr_ex_name = str(curr_ex.get("name", "Ejercicio Activo"))

    render_client_rest_timer(
        target_seconds=int(active.get("rest_target_s") or 90),
        start_epoch_ms=int(active.get("rest_timer_start_ms") or 0),
        auto_running=bool(active.get("rest_timer_running", False)),
        exercise_label=f"Descanso · {curr_ex_name[:26]}",
    )

    # Selector rápido de objetivo de descanso (Presets 60s, 90s, 120s, 180s + Manual libre)
    with st.expander("⚙️ Ajustar Tiempo Objetivo de Descanso (Presets o Selector Manual Libre)", expanded=False):
        pcols = st.columns(5)
        for idx, preset_s in enumerate(REST_PRESETS_SECONDS):
            with pcols[idx]:
                is_curr_p = int(active.get("rest_target_s") or 90) == preset_s
                if st.button(
                    f"⏱️ {preset_s}s",
                    key=f"btn_rest_preset_{preset_s}",
                    type="primary" if is_curr_p else "secondary",
                    use_container_width=True,
                ):
                    active["rest_target_s"] = preset_s
                    st.rerun(scope="fragment")
        with pcols[4]:
            custom_rest = st.number_input(
                "Manual (s)",
                min_value=15,
                max_value=600,
                value=int(active.get("rest_target_s") or 90),
                step=15,
                label_visibility="collapsed",
                key="in_custom_rest_target",
            )
            if int(custom_rest) != int(active.get("rest_target_s") or 90):
                active["rest_target_s"] = int(custom_rest)

    # 2. SELECTOR DE EJERCICIO ACTIVO (Prioriza los de la rutina + acceso a todo el catálogo)
    if planned_items:
        routine_ex_ids = [str(it["exercise_id"]) for it in planned_items if str(it["exercise_id"]) in exercises_by_id]
        other_ex_ids = [str(e["id"]) for e in exercises if str(e["id"]) not in routine_ex_ids]
        ordered_ex_ids = routine_ex_ids + other_ex_ids
    else:
        ordered_ex_ids = [str(e["id"]) for e in exercises]

    if not ordered_ex_ids:
        st.warning("No hay ejercicios en el catálogo. Ejecuta sql/02_seed_catalog.sql.")
        return

    if curr_ex_id not in ordered_ex_ids:
        curr_ex_id = ordered_ex_ids[0]
        active["selected_exercise_id"] = curr_ex_id

    def _fmt_ex_option(eid: str) -> str:
        ex_obj = exercises_by_id.get(eid, {})
        done_cnt = sum(1 for s in logged_sets if str(s.get("exercise_id")) == eid and s.get("set_type") != "warmup")
        in_plan = planned_by_ex.get(eid)
        if in_plan:
            t_sets = int(in_plan.get("target_sets") or 3)
            return f"🎯 {ex_obj.get('name')} [{done_cnt}/{t_sets} series] · ({in_plan.get('target_rep_min')}–{in_plan.get('target_rep_max')} reps)"
        return f"➕ {ex_obj.get('name')} [{done_cnt} series]"

    selected_eid = st.selectbox(
        "Ejercicio en Ejecución",
        options=ordered_ex_ids,
        index=ordered_ex_ids.index(curr_ex_id),
        format_func=_fmt_ex_option,
        key="live_selected_exercise_box",
    )

    if selected_eid != curr_ex_id:
        active["selected_exercise_id"] = selected_eid
        plan_cfg = planned_by_ex.get(selected_eid)
        if plan_cfg and plan_cfg.get("default_rest_seconds"):
            active["rest_target_s"] = int(plan_cfg["default_rest_seconds"])
        active["prefill_weight"] = None
        active["prefill_reps"] = None
        active["prefill_rpe"] = None
        st.rerun(scope="fragment")

    # 3. BANNER DE RECOMENDACIÓN ALGORÍTMICA DE SOBRECARGA PROGRESIVA (04_UI_UX §3.2)
    plan_item = planned_by_ex.get(selected_eid, {})
    t_rep_min = int(plan_item.get("target_rep_min") or 8)
    t_rep_max = int(plan_item.get("target_rep_max") or 12)
    t_rpe = float(plan_item.get("target_rpe") or 8.0)
    t_step = float(plan_item.get("progression_step_kg") or 2.5)
    t_rest = int(plan_item.get("default_rest_seconds") or active.get("rest_target_s") or 90)

    rec = get_exercise_recommendation(
        user_id=user_id,
        exercise_id=selected_eid,
        all_user_sets=all_historical_sets,
        target_rep_min=t_rep_min,
        target_rep_max=t_rep_max,
        target_rpe=t_rpe,
        progression_step_kg=t_step,
        default_rest_seconds=t_rest,
    )

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="trifecta-prog-banner" style="
                background:{rec.badge_color}1A;
                border-left:4px solid {rec.badge_color};
                margin-bottom:8px;
            ">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px;">
                    <span style="
                        font-size:0.72rem; font-weight:800; color:{rec.badge_color};
                        background:{rec.badge_color}26; padding:2px 8px; border-radius:999px;
                    ">{rec.badge_label}</span>
                    <span style="font-size:0.74rem; color:#94A3B8; font-family:'JetBrains Mono', monospace;">
                        1RM Epley: <b>{rec.estimated_1rm_epley:g} kg</b> · Brzycki: <b>{rec.estimated_1rm_brzycki:g} kg</b>
                        ({rec.relative_intensity_pct:g}% 1RM)
                    </span>
                </div>
                <div style="font-weight:800; font-size:0.96rem; color:#F8FAFC; margin-top:5px;">
                    {rec.headline}
                </div>
                <div style="font-size:0.80rem; color:#94A3B8; margin-top:2px;">
                    {rec.explanation}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            f"⚡ Aplicar sugerencia ({rec.suggested_weight_kg:g} kg × {rec.suggested_reps} reps @ RPE {rec.suggested_rpe:g})",
            key=f"btn_apply_rec_{selected_eid}",
            use_container_width=True,
        ):
            active["prefill_weight"] = float(rec.suggested_weight_kg)
            active["prefill_reps"] = int(rec.suggested_reps)
            active["prefill_rpe"] = float(rec.suggested_rpe)
            active["rest_target_s"] = int(rec.suggested_rest_seconds)
            st.rerun(scope="fragment")

        # 4. AUTOCOMPLETADO INTELIGENTE Y CAPTURA DE SERIE EN VIVO
        sets_for_this_ex = [s for s in logged_sets if str(s.get("exercise_id")) == selected_eid]
        next_set_num = len(sets_for_this_ex) + 1

        if active.get("prefill_weight") is not None:
            default_w = float(active["prefill_weight"])
            default_r = int(active["prefill_reps"] or t_rep_min)
            default_rpe = float(active["prefill_rpe"] or t_rpe)
        elif sets_for_this_ex:
            last_logged = sets_for_this_ex[-1]
            default_w = float(last_logged.get("weight_kg") or rec.suggested_weight_kg)
            default_r = int(last_logged.get("reps") or rec.suggested_reps)
            default_rpe = float(last_logged.get("rpe") or rec.suggested_rpe)
        else:
            default_w = float(rec.suggested_weight_kg)
            default_r = int(rec.suggested_reps)
            default_rpe = float(rec.suggested_rpe)

        # Calcular descanso real transcurrido desde la última serie guardada
        last_epoch = active.get("last_set_saved_epoch")
        if last_epoch:
            elapsed_since_last = max(0, min(900, int(time.time() - float(last_epoch))))
        else:
            elapsed_since_last = int(active.get("rest_target_s") or 90)

        st.markdown(f"##### ✍️ Registrar Serie #{next_set_num}")
        col_st, col_w, col_r = st.columns([0.38, 0.32, 0.30])
        with col_st:
            set_type_in = st.selectbox(
                "Tipo de Serie",
                options=list(SET_TYPE_LABELS.keys()),
                index=1,  # 'working' por defecto
                format_func=lambda k: SET_TYPE_LABELS[k]["short"],
                key=f"in_stype_{selected_eid}_{next_set_num}",
            )
        with col_w:
            weight_in = st.number_input(
                "Peso (kg)",
                min_value=0.0,
                max_value=1000.0,
                value=float(default_w),
                step=2.5,
                key=f"in_w_{selected_eid}_{next_set_num}",
            )
        with col_r:
            reps_in = st.number_input(
                "Repeticiones",
                min_value=1,
                max_value=100,
                value=max(1, int(default_r)),
                step=1,
                key=f"in_r_{selected_eid}_{next_set_num}",
            )

        col_rpe, col_rest_act, col_notes = st.columns([0.36, 0.32, 0.32])
        with col_rpe:
            rpe_in = st.slider(
                "Esfuerzo RPE (RIR auto)",
                min_value=5.0,
                max_value=10.0,
                value=float(default_rpe),
                step=0.5,
                key=f"in_rpe_{selected_eid}_{next_set_num}",
            )
            rir_calc = round(max(0.0, 10.0 - float(rpe_in)), 1)
        with col_rest_act:
            rest_actual_in = st.number_input(
                "Descanso Real (s)",
                min_value=0,
                max_value=1200,
                value=int(elapsed_since_last),
                step=5,
                help="Se autocompleta con los segundos reales transcurridos desde tu serie anterior.",
                key=f"in_rest_act_{selected_eid}_{next_set_num}",
            )
        with col_notes:
            set_note_in = st.text_input(
                "Nota / Sensación",
                placeholder="Ej. Pausa 1s abajo",
                key=f"in_note_{selected_eid}_{next_set_num}",
            )

        # Vista previa instantánea de Tonelaje, 1RM Epley/Brzycki, Intensidad Relativa y RIR
        preview_epley = calculate_epley_1rm(float(weight_in), int(reps_in))
        preview_brzycki = calculate_brzycki_1rm(float(weight_in), int(reps_in))
        preview_tonnage = round(float(weight_in) * int(reps_in), 1)
        preview_rel_int = calculate_relative_intensity_pct(float(weight_in), preview_epley)

        st.caption(
            f"📊 **Tonelaje:** `{preview_tonnage:g} kg` · **RIR:** `{rir_calc:g}` · "
            f"**1RM Epley:** `{preview_epley:g} kg` · **1RM Brzycki:** `{preview_brzycki:g} kg` "
            f"(`{preview_rel_int:g}% 1RM`)"
        )

        if st.button(
            f"✔ Guardar Serie #{next_set_num} y Activar Descanso ({active.get('rest_target_s', 90)}s)",
            type="primary",
            use_container_width=True,
            key=f"btn_save_set_{selected_eid}_{next_set_num}",
        ):
            combined_prev = [
                s for s in (all_historical_sets + logged_sets)
                if str(s.get("exercise_id")) == selected_eid
            ]
            pr_achieved = is_set_personal_record(
                weight_kg=float(weight_in),
                reps=int(reps_in),
                set_type=str(set_type_in),
                historical_sets=combined_prev,
            )

            new_set_entry = {
                "exercise_id": selected_eid,
                "exercise_name": curr_ex_name,
                "set_number": next_set_num,
                "set_type": set_type_in,
                "weight_kg": float(weight_in),
                "reps": int(reps_in),
                "rpe": float(rpe_in),
                "rir": rir_calc,
                "rest_target_seconds": int(active.get("rest_target_s") or 90),
                "rest_actual_seconds": int(rest_actual_in),
                "tonnage_kg": preview_tonnage,
                "estimated_1rm": preview_epley,
                "is_pr": pr_achieved,
                "notes": set_note_in.strip(),
                "performed_at": datetime.now(timezone.utc).isoformat(),
            }
            active["sets"].append(new_set_entry)
            active["last_set_saved_epoch"] = time.time()
            active["rest_timer_start_ms"] = int(time.time() * 1000)
            active["rest_timer_running"] = True
            active["prefill_weight"] = None
            active["prefill_reps"] = None
            active["prefill_rpe"] = None

            if pr_achieved:
                st.toast(f"🏆 ¡Nuevo PR Personal en {curr_ex_name}! 1RM Est: {preview_epley:g} kg", icon="🏆")
            else:
                st.toast(f"Serie #{next_set_num} registrada. Cronómetro de descanso iniciado.", icon="⏱️")
            st.rerun(scope="fragment")

    # 5. HISTORIAL DE SERIES CAPTURADAS EN LA SESIÓN ACTUAL
    if logged_sets:
        with st.container(border=True):
            st.markdown(f"##### 📝 Series Capturadas Hoy ({len(logged_sets)})")
            for s_idx, s_row in enumerate(logged_sets):
                st_meta = SET_TYPE_LABELS.get(str(s_row.get("set_type", "working")), SET_TYPE_LABELS["working"])
                pr_tag = " 🏆 **PR**" if s_row.get("is_pr") else ""
                c_line, c_del = st.columns([0.86, 0.14], vertical_alignment="center")
                with c_line:
                    st.markdown(
                        f"<span style='color:{st_meta['color']}; font-weight:700;'>[{st_meta['code']}]</span> "
                        f"**{s_row.get('exercise_name')}** · Serie #{s_row.get('set_number')}: "
                        f"`{s_row.get('weight_kg'):g} kg × {s_row.get('reps')} reps` "
                        f"@ RPE {s_row.get('rpe'):g} (RIR {s_row.get('rir'):g}) · "
                        f"⏱️ {s_row.get('rest_actual_seconds')}s / {s_row.get('rest_target_seconds')}s{pr_tag}",
                        unsafe_allow_html=True,
                    )
                with c_del:
                    if st.button("🗑️", key=f"del_live_set_{s_idx}", help="Borrar serie"):
                        active["sets"].pop(s_idx)
                        st.rerun(scope="fragment")

    # 6. CIERRE Y GUARDADO TRANSACCIONAL EN SUPABASE
    with st.container(border=True):
        st.markdown("##### 🏁 Finalizar Sesión")
        col_fat, col_bw = st.columns(2)
        with col_fat:
            fatigue_in = st.slider("Fatiga Global Percibida (1–10)", min_value=1, max_value=10, value=7, key="live_fatigue_sl")
        with col_bw:
            bw_in = st.number_input("Peso Corporal Hoy (kg, opcional)", min_value=0.0, max_value=250.0, value=0.0, step=0.5, key="live_bw_in")
        sess_notes = st.text_input("Notas de la Sesión", placeholder="Ej. Excelente bombeo en pecho, buen nivel de energía", key="live_sess_notes")

        col_fin, col_cancel = st.columns([0.68, 0.32])
        with col_fin:
            if st.button("🏁 Finalizar y Guardar Entrenamiento", type="primary", use_container_width=True, key="btn_finish_workout"):
                ok, msg, summary = save_completed_workout_session(
                    user_id=user_id,
                    session_title=str(active.get("session_title", "Entrenamiento")),
                    started_at=active.get("started_at") or datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    sets_logged=logged_sets,
                    routine_id=active.get("routine_id"),
                    perceived_fatigue=int(fatigue_in),
                    bodyweight_kg=float(bw_in) if bw_in > 0 else None,
                    notes=sess_notes,
                )
                if ok:
                    st.session_state["last_workout_summary"] = summary
                    st.session_state["active_workout"] = None
                    st.toast(msg, icon="🏆")
                    st.rerun()
                else:
                    st.error(msg)
        with col_cancel:
            if st.button("❌ Descartar", use_container_width=True, key="btn_discard_workout"):
                st.session_state["active_workout"] = None
                st.rerun()


# ============================================================================
# 4. PESTAÑA 2: ANALÍTICA MULTITEMPORAL (8 HORIZONTES) Y DENSIDAD / DESCANSO
# ============================================================================

@st.fragment
def _render_workout_analytics_fragment(
    user_id: str,
    exercises: List[Dict[str, Any]],
    all_sets: List[Dict[str, Any]],
) -> None:
    """
    Fragmento reactivo (@st.fragment) con los 8 horizontes temporales (1D a 1Y + YTD),
    gráficas Plotly de volumen muscular ponderado (1.0 primario / 0.5 secundario)
    y panel de analítica de descanso inter-serie y correlación RPE/RIR.
    """
    exercises_by_id = {str(e["id"]): e for e in exercises}

    # Selector de los horizontes temporales
    tf_options = ["1D", "1W", "2W", "1M", "2M", "3M", "6M", "YTD", "1Y"]
    tf_labels_short = {
        "1D": "1D",
        "1W": "1W (7d)",
        "2W": "2W (14d)",
        "1M": "1M",
        "2M": "2M",
        "3M": "3M",
        "6M": "6M",
        "YTD": "YTD",
        "1Y": "1Y",
    }
    rev_tf = {v: k for k, v in tf_labels_short.items()}

    if hasattr(st, "segmented_control"):
        chosen_lbl = st.segmented_control(
            "Horizonte Temporal",
            options=[tf_labels_short[k] for k in tf_options],
            default=tf_labels_short["1W"],
            label_visibility="collapsed",
            key="analytics_tf_segmented",
        )
        selected_tf = rev_tf.get(chosen_lbl or "1W (7d)", "1W")
    else:
        selected_tf = st.selectbox("Horizonte Temporal", options=tf_options, index=1)

    col_mode, col_muscle = st.columns(2)
    with col_mode:
        metric_mode = st.selectbox(
            "Métrica de Volumen",
            options=["effective_sets", "tonnage_kg"],
            format_func=lambda m: "Series Efectivas (1.0x / 0.5x)" if m == "effective_sets" else "Tonelaje Ponderado (kg)",
            key="analytics_metric_mode",
        )
    with col_muscle:
        muscle_filter = st.selectbox(
            "Grupo Muscular",
            options=["all"] + list(MUSCLE_LABELS.keys()),
            format_func=lambda m: "Todos los músculos (14)" if m == "all" else MUSCLE_LABELS.get(m, m),
            key="analytics_muscle_filter",
        )

    vol_data = calculate_multitemporal_volume(
        sets_records=all_sets,
        exercises_by_id=exercises_by_id,
        timeframe_code=selected_tf,
        metric_mode=metric_mode,  # type: ignore[arg-type]
        muscle_filter=muscle_filter,
    )

    unit_sfx = "series ef." if metric_mode == "effective_sets" else "kg"
    delta_val = float(vol_data["delta_pct"])
    delta_sign = "+" if delta_val >= 0 else ""

    # Fila superior de KPIs de Volumen y Descanso
    rest_metrics = calculate_rest_and_density_metrics(all_sets)
    k1, k2 = st.columns(2)
    with k1:
        render_kpi_card(
            label=f"Volumen · {vol_data['timeframe_label']}",
            value=f"{vol_data['current_total']:,.1f} {unit_sfx}",
            delta_text=f"{delta_sign}{delta_val:.1f}% vs. previo",
            delta_positive=(delta_val >= 0),
            accent_color=PALETTE["accent_workout"],
        )
    with k2:
        render_kpi_card(
            label="Descanso Promedio / Ratio",
            value=f"{rest_metrics.avg_rest_actual_seconds:.0f}s ({rest_metrics.work_to_rest_ratio_label})",
            delta_text=f"Densidad: {rest_metrics.tonnage_per_min_kg:g} kg/min",
            delta_positive=(rest_metrics.rest_compliance_pct >= 75.0),
            accent_color="#10B981",
        )

    # Gráfica 1: Distribución por Grupo Muscular vs. Zona Óptima de Hipertrofia
    with st.container(border=True):
        st.markdown(
            f"##### 💪 Distribución por Grupo Muscular ({vol_data['timeframe_label']})"
        )
        st.caption(
            f"Zona óptima de hipertrofia escalada al periodo: **{vol_data['optimal_min_sets']:g} a "
            f"{vol_data['optimal_max_sets']:g} series efectivas** (`1.0` primario / `0.5` secundario)."
        )

        active_muscles = [m for m in vol_data["by_muscle"] if float(m["value"]) > 0]
        display_muscles = active_muscles if active_muscles else vol_data["by_muscle"][:8]
        display_muscles_rev = list(reversed(display_muscles))

        fig_bar = go.Figure()
        fig_bar.add_trace(
            go.Bar(
                y=[m["muscle_label"] for m in display_muscles_rev],
                x=[m["value"] for m in display_muscles_rev],
                orientation="h",
                marker=dict(
                    color=[m["zone_color"] if float(m["value"]) > 0 else "#263044" for m in display_muscles_rev],
                    line=dict(width=0),
                ),
                text=[f"{m['value']:g}" for m in display_muscles_rev],
                textposition="auto",
                name=unit_sfx,
            )
        )
        apply_mobile_dark_layout(fig_bar, height=max(240, len(display_muscles_rev) * 28 + 40))
        render_mobile_plotly(fig_bar, key=f"plotly_muscle_dist_{selected_tf}_{metric_mode}")

    # Gráfica 2: Evolución Temporal en el Horizonte Seleccionado
    with st.container(border=True):
        st.markdown(f"##### 📈 Evolución Temporal ({EXTENDED_TIMEFRAME_CONFIG[selected_tf]['label']})")
        timeline = vol_data.get("timeline") or []
        if not timeline:
            st.caption("Aún no hay series efectivas registradas en esta ventana temporal.")
        else:
            fig_time = go.Figure()
            fig_time.add_trace(
                go.Bar(
                    x=[t["bucket_label"] for t in timeline],
                    y=[t["value"] for t in timeline],
                    marker_color="#FF5500",
                    name=unit_sfx,
                )
            )
            apply_mobile_dark_layout(fig_time, height=230)
            render_mobile_plotly(fig_time, key=f"plotly_timeline_{selected_tf}_{metric_mode}")

    # Bloque 3: Analítica de Descanso Inter-Serie, Densidad y Correlación RPE/RIR
    with st.container(border=True):
        st.markdown("##### ⏱️ Analítica de Descanso, Densidad y Correlación RPE/RIR")
        corr_str = (
            f"r = {rest_metrics.rest_rpe_correlation:+.2f}"
            if rest_metrics.rest_rpe_correlation is not None
            else "Datos en acumulación"
        )
        st.markdown(
f"""
<div style="background:#1A2232; border:1px solid #263044; border-left:4px solid #06B6D4; border-radius:12px; padding:10px 12px; margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; font-size:0.78rem; color:#94A3B8;">
<span>Cumplimiento de Descanso: <b style="color:#F8FAFC;">{rest_metrics.rest_compliance_pct:.0f}%</b></span>
<span>Correlación Descanso vs. RPE: <b style="color:#06B6D4;">{corr_str}</b></span>
</div>
<div style="font-size:0.83rem; color:#F8FAFC; margin-top:5px;">
🧠 {rest_metrics.correlation_insight}
</div>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================================
# 5. PUNTO DE ENTRADA DEL PILAR 1 (workout_view.py)
# ============================================================================

def render_workout_view() -> None:
    """Renderiza el Módulo 1 completo: Entrenamiento Físico, Sobrecarga Progresiva y Analítica 1D-1Y."""
    user_id = get_current_user_id()
    if not user_id:
        st.warning("Inicia sesión para acceder al módulo de entrenamiento.")
        return

    access_token = st.session_state.get("access_token") or ""
    exercises = fetch_exercises_catalog(user_id, access_token)
    routines = fetch_workout_routines(user_id, access_token)
    routine_items = fetch_workout_routine_items(user_id, access_token)
    all_sets = fetch_workout_sets(user_id, access_token, days_back=370)
    sessions = fetch_workout_sessions(user_id, access_token, days_back=90)
    exercises_by_id = {str(e["id"]): e for e in exercises}

    render_pillar_header(
        title="Entrenamiento Físico",
        subtitle="Sobrecarga progresiva algorítmico, cronómetro inter-serie y volumen ponderado 1D–1Y",
        accent_hex=PALETTE["accent_workout"],
        badge_text="🏋️ Pilar 1 · Hypertrophy & Strength",
    )

    tab_live, tab_analytics, tab_catalog = st.tabs(
        ["⚡ Entrenar Ahora", "📊 Analítica (1D–1Y)", "📋 Rutinas y Catálogo"]
    )

    with tab_live:
        # Mostrar resumen si acaba de concluir un entrenamiento
        last_summary = st.session_state.get("last_workout_summary")
        if last_summary:
            with st.container(border=True):
                st.success(
                    f"🏆 **¡Sesión completada: {last_summary.get('session_title')}!**  \n"
                    f"Series efectivas: **{last_summary.get('working_sets')}** · "
                    f"Tonelaje total: **{last_summary.get('total_tonnage_kg'):,.1f} kg** · "
                    f"Récords (PRs): **{last_summary.get('prs_count')}** · "
                    f"Descanso medio: **{last_summary.get('avg_rest_seconds'):.0f}s** "
                    f"(Ratio `{last_summary.get('work_to_rest_ratio')}`)"
                )
                if st.button("Cerrar resumen", key="btn_close_workout_summary"):
                    st.session_state["last_workout_summary"] = None
                    st.rerun()

        if st.session_state.get("active_workout"):
            _render_live_workout_fragment(
                user_id=user_id,
                exercises=exercises,
                all_historical_sets=all_sets,
            )
        else:
            c_free, c_new_r = st.columns(2)
            with c_free:
                if st.button("⚡ Iniciar Sesión Libre", type="primary", use_container_width=True, key="btn_start_free_session"):
                    _start_active_workout(None, [], exercises_by_id)
                    st.rerun()
            with c_new_r:
                if st.button("➕ Crear Rutina", use_container_width=True, key="btn_live_new_routine"):
                    _open_create_routine_dialog(user_id, exercises)

            st.markdown("##### 🗂️ Tus Plantillas de Rutina")
            if not routines:
                with st.container(border=True):
                    st.info("Aún no tienes plantillas de rutina configuradas.")
                    if st.button(
                        "✨ Generar 3 Rutinas Base (Push / Pull / Legs)",
                        type="primary",
                        use_container_width=True,
                        key="btn_seed_ppl_routines",
                    ):
                        ok, msg = seed_starter_routines_for_user(user_id, exercises)
                        if ok:
                            st.toast(msg, icon="🔥")
                            st.rerun()
                        else:
                            st.error(msg)
            else:
                for r in routines:
                    rid = str(r["id"])
                    r_items = [it for it in routine_items if str(it.get("routine_id")) == rid]
                    ex_names = [
                        exercises_by_id.get(str(it.get("exercise_id")), {}).get("name", "Ejercicio")
                        for it in r_items
                    ]
                    ex_preview = " · ".join(ex_names[:4]) + (f" (+{len(ex_names)-4} más)" if len(ex_names) > 4 else "")
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-weight:800; font-size:1.02rem; color:#F8FAFC;">{r.get('name')}</span>
                                <span style="font-size:0.74rem; color:#FF5500; background:#FF55001F; padding:2px 8px; border-radius:999px;">
                                    {len(r_items)} ejercicios
                                </span>
                            </div>
                            <div style="font-size:0.80rem; color:#94A3B8; margin:4px 0 8px 0;">
                                {ex_preview or r.get('description') or 'Sin ejercicios asignados'}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            f"▶ Iniciar «{r.get('name')}»",
                            key=f"btn_start_routine_{rid}",
                            type="primary",
                            use_container_width=True,
                        ):
                            _start_active_workout(r, routine_items, exercises_by_id)
                            st.rerun()

            if sessions:
                with st.expander(f"🕒 Últimas Sesiones Registradas ({len(sessions[:5])})", expanded=False):
                    for sess in sessions[:5]:
                        dt_str = str(sess.get("started_at") or "")[:10]
                        dur = sess.get("duration_minutes") or "—"
                        st.markdown(
                            f"- **{sess.get('session_title')}** (`{dt_str}`) · Duración: `{dur} min` · "
                            f"Fatiga: `{sess.get('perceived_fatigue') or '—'}/10`"
                        )

    with tab_analytics:
        _render_workout_analytics_fragment(
            user_id=user_id,
            exercises=exercises,
            all_sets=all_sets,
        )

    with tab_catalog:
        c_nr, c_ne = st.columns(2)
        with c_nr:
            if st.button("➕ Nueva Rutina", type="primary", use_container_width=True, key="cat_btn_new_routine"):
                _open_create_routine_dialog(user_id, exercises)
        with c_ne:
            if st.button("➕ Nuevo Ejercicio", use_container_width=True, key="cat_btn_new_exercise"):
                _open_create_exercise_dialog(user_id)

        if routines:
            with st.container(border=True):
                st.markdown(f"#### 📋 Mis Rutinas ({len(routines)})")
                for r in routines:
                    rid = str(r["id"])
                    rc1, rc2 = st.columns([0.82, 0.18], vertical_alignment="center")
                    with rc1:
                        st.markdown(f"**{r.get('name')}** — _{r.get('description') or 'Plantilla activa'}_")
                    with rc2:
                        if st.button("🗑️", key=f"cat_del_routine_{rid}", use_container_width=True):
                            delete_workout_routine(user_id, rid)
                            st.rerun()

        with st.container(border=True):
            st.markdown(f"#### 🏋️ Catálogo de Ejercicios Ponderados ({len(exercises)})")
            m_filter = st.selectbox(
                "Filtrar por Músculo Primario",
                options=["all"] + list(MUSCLE_LABELS.keys()),
                format_func=lambda m: "Todos los grupos musculares" if m == "all" else MUSCLE_LABELS.get(m, m),
                key="catalog_tab_muscle_filter",
            )
            filtered_ex = [
                ex for ex in exercises if m_filter == "all" or ex.get("primary_muscle") == m_filter
            ]
            for ex in filtered_ex[:20]:
                prim_lbl = MUSCLE_LABELS.get(str(ex.get("primary_muscle", "")), str(ex.get("primary_muscle", "")))
                sec_list = ex.get("secondary_muscles") or []
                sec_lbls = ", ".join(MUSCLE_LABELS.get(s, s) for s in sec_list) or "Ninguno (Aislamiento)"
                custom_badge = " · 👤 Personalizado" if ex.get("user_id") else ""
                st.markdown(
                    f"""
                    <div style="
                        padding:10px 12px; border-radius:12px; background:#1A2232;
                        border:1px solid #263044; margin-bottom:8px;
                    ">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-weight:700; font-size:0.92rem; color:#F8FAFC;">
                                {ex.get('name')}{custom_badge}
                            </span>
                            <span style="font-size:0.73rem; color:#FF5500; background:#FF55001F; padding:2px 8px; border-radius:999px;">
                                {prim_lbl} (1.0x)
                            </span>
                        </div>
                        <div style="font-size:0.78rem; color:#94A3B8; margin-top:4px;">
                            Secundarios (0.5x): {sec_lbls} · Equipo: <code>{ex.get('equipment')}</code>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )