"""
Módulo 1: Entrenamiento Físico, Motor Algorítmico de Sobrecarga Progresiva,
Cronómetro de Descanso Inteligente (Client-Side HTML5/JS), Planificador Semanal,
Duplicación/Reordenamiento Flexible de Rutinas, Catálogo Editable y Analítica (1D a 1Y).
Implementado según 01_PRD (§2), 02_TRD (§5.1), 03_Appflow (§4), 04_UI_UX (§3.2-3.3).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
    SPANISH_WEEKDAYS,
    WEEKLY_PLAN_STATUS_LABELS,
    WORKOUT_FOCUS_PRESETS,
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
    delete_weekly_workout_plan_day,
    delete_workout_routine,
    duplicate_workout_routine,
    fetch_exercises_catalog,
    fetch_weekly_workout_plan,
    fetch_workout_routine_items,
    fetch_workout_routines,
    fetch_workout_sessions,
    fetch_workout_sets,
    get_exercise_recommendation,
    get_monday_of_week,
    is_set_personal_record,
    move_routine_item_order,
    save_completed_workout_session,
    seed_starter_routines_for_user,
    update_exercise_in_catalog,
    update_workout_routine_with_items,
    upsert_weekly_workout_plan_day,
)


# ============================================================================
# 1. COMPONENTES Y ESTADO DE SESIÓN EN VIVO (st.session_state["active_workout"])
# ============================================================================

def render_kpi_card(
    label: str,
    value: str,
    delta_text: str = "",
    delta_positive: bool = True,
    accent_color: str = "#3B82F6",
) -> None:
    """Tarjeta KPI con HTML pegado al margen izquierdo (columna 0)."""
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
        planned_items.sort(key=lambda x: int(x.get("order_index") or 1))
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
# 2. MODALES NATIVOS (@st.dialog) PARA EJERCICIOS Y PLANTILLAS DE RUTINAS
# ============================================================================

@st.dialog("➕ Nuevo Ejercicio Personalizado")
def _open_create_exercise_dialog(user_id: str) -> None:
    """Modal móvil para agregar un ejercicio personalizado con músculos primario (1.0x), secundarios (0.5x) y notas."""
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
        notes_in = st.text_area(
            "Notas técnicas de ejecución (opcional)",
            placeholder="Ej. Retracción escapular, codos a 45°, pausa de 1s en estiramiento...",
            height=68,
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
                    notes=notes_in,
                )
                if ok:
                    st.toast(msg, icon="🏋️")
                    st.rerun()
                else:
                    st.error(msg)


@st.dialog("✏️ Editar Ejercicio del Catálogo")
def _open_edit_exercise_dialog(user_id: str, exercise: Dict[str, Any]) -> None:
    """
    Modal móvil para editar un ejercicio existente en el catálogo (nombre, músculo primario/secundario,
    equipo y notas técnicas) conservando su ID en Supabase sin romper el historial de sets pasados.
    """
    ex_id = str(exercise.get("id") or "")
    curr_name = str(exercise.get("name") or "")
    curr_eq = str(exercise.get("equipment") or "barbell")
    curr_pat = str(exercise.get("movement_pattern") or "compound")
    curr_prim = str(exercise.get("primary_muscle") or "chest")
    curr_secs = [s for s in (exercise.get("secondary_muscles") or []) if s in MUSCLE_LABELS]
    curr_notes = str(exercise.get("notes") or "")

    st.caption("Los cambios actualizarán el catálogo conservando intacto tu historial de series y PRs.")
    with st.form(f"form_edit_exercise_{ex_id}", clear_on_submit=False):
        name_in = st.text_input("Nombre del Ejercicio", value=curr_name)

        eq_keys = list(EQUIPMENT_LABELS.keys())
        eq_idx = eq_keys.index(curr_eq) if curr_eq in eq_keys else 0
        pat_keys = ["compound", "isolation"]
        pat_idx = pat_keys.index(curr_pat) if curr_pat in pat_keys else 0

        col_eq, col_pat = st.columns(2)
        with col_eq:
            eq_in = st.selectbox(
                "Equipo Requerido",
                options=eq_keys,
                index=eq_idx,
                format_func=lambda k: EQUIPMENT_LABELS.get(k, k),
            )
        with col_pat:
            pat_in = st.selectbox(
                "Patrón Biomecánico",
                options=pat_keys,
                index=pat_idx,
                format_func=lambda p: "Compuesto (Multiarticular)" if p == "compound" else "Aislamiento (Monoarticular)",
            )

        muscle_keys = list(MUSCLE_LABELS.keys())
        prim_idx = muscle_keys.index(curr_prim) if curr_prim in muscle_keys else 0
        prim_in = st.selectbox(
            "Grupo Muscular Principal (Factor 1.0x)",
            options=muscle_keys,
            index=prim_idx,
            format_func=lambda m: MUSCLE_LABELS.get(m, m),
        )
        sec_options = [m for m in muscle_keys if m != prim_in]
        sec_defaults = [m for m in curr_secs if m in sec_options]
        sec_in = st.multiselect(
            "Grupos Musculares Secundarios (Factor 0.5x)",
            options=sec_options,
            default=sec_defaults,
            format_func=lambda m: MUSCLE_LABELS.get(m, m),
        )
        notes_in = st.text_area(
            "Notas Técnicas / Claves Biomecánicas",
            value=curr_notes,
            placeholder="Ej. Mantener escápulas deprimidas, controlar excéntrica 3s...",
            height=75,
        )

        submitted = st.form_submit_button("💾 Actualizar Ejercicio", type="primary", use_container_width=True)
        if submitted:
            if not name_in.strip():
                st.error("El nombre del ejercicio no puede estar vacío.")
            else:
                ok, msg = update_exercise_in_catalog(
                    user_id=user_id,
                    exercise_id=ex_id,
                    name=name_in,
                    equipment=eq_in,
                    primary_muscle=prim_in,
                    secondary_muscles=sec_in,
                    movement_pattern=pat_in,
                    notes=notes_in,
                )
                if ok:
                    st.toast(msg, icon="✅")
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


@st.dialog("🛠️ Editar y Reordenar Plantilla de Rutina")
def _open_edit_routine_dialog(
    user_id: str,
    routine: Dict[str, Any],
    routine_items: List[Dict[str, Any]],
    exercises: List[Dict[str, Any]],
) -> None:
    """
    Modal interactivo para editar una rutina existente:
    - Reordenar ejercicios con botones ↑ / ↓
    - Agregar ejercicios nuevos intercalados o al final
    - Modificar series objetivo, rango de repeticiones y descanso
    - Retirar ejercicios sin afectar otras rutinas
    """
    rid = str(routine.get("id") or "")
    draft_key = f"routine_edit_draft_{rid}"
    exercises_by_id = {str(e["id"]): e for e in exercises}
    ex_map = {
        str(e["id"]): f"{e.get('name')} ({MUSCLE_LABELS.get(str(e.get('primary_muscle')), '')})"
        for e in exercises
    }

    if draft_key not in st.session_state:
        initial_items = [it for it in routine_items if str(it.get("routine_id")) == rid]
        initial_items.sort(key=lambda x: int(x.get("order_index") or 1))
        st.session_state[draft_key] = [
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
            for it in initial_items
        ]

    draft_items: List[Dict[str, Any]] = st.session_state[draft_key]

    r_name = st.text_input(
        "Nombre de la Rutina",
        value=str(routine.get("name") or ""),
        key=f"dlg_ed_rname_{rid}",
    )
    r_desc = st.text_input(
        "Descripción / Enfoque",
        value=str(routine.get("description") or ""),
        key=f"dlg_ed_rdesc_{rid}",
    )

    st.markdown(f"##### 🔢 Orden y Parámetros de Ejercicios ({len(draft_items)})")
    if not draft_items:
        st.info("No hay ejercicios en la plantilla. Agrega al menos uno abajo.")
    else:
        for idx, item in enumerate(list(draft_items)):
            ex_obj = exercises_by_id.get(str(item["exercise_id"]), {})
            ex_title = ex_obj.get("name", "Ejercicio")
            with st.container(border=True):
                h_col, up_col, dn_col, del_col = st.columns([3.2, 0.65, 0.65, 0.65], vertical_alignment="center")
                with h_col:
                    st.markdown(f"**#{idx + 1} · {ex_title}**")
                with up_col:
                    if st.button(
                        "⬆️",
                        key=f"dlg_up_{rid}_{idx}",
                        disabled=(idx == 0),
                        help="Subir posición",
                        use_container_width=True,
                    ):
                        draft_items[idx - 1], draft_items[idx] = draft_items[idx], draft_items[idx - 1]
                        st.rerun(scope="fragment" if hasattr(st, "fragment") else "app")
                with dn_col:
                    if st.button(
                        "⬇️",
                        key=f"dlg_dn_{rid}_{idx}",
                        disabled=(idx == len(draft_items) - 1),
                        help="Bajar posición",
                        use_container_width=True,
                    ):
                        draft_items[idx + 1], draft_items[idx] = draft_items[idx], draft_items[idx + 1]
                        st.rerun(scope="fragment" if hasattr(st, "fragment") else "app")
                with del_col:
                    if st.button(
                        "🗑️",
                        key=f"dlg_rm_{rid}_{idx}",
                        help="Retirar ejercicio de la rutina",
                        use_container_width=True,
                    ):
                        draft_items.pop(idx)
                        st.rerun(scope="fragment" if hasattr(st, "fragment") else "app")

                p1, p2, p3, p4 = st.columns(4)
                with p1:
                    new_sets = st.number_input(
                        "Series",
                        min_value=1,
                        max_value=15,
                        value=int(item.get("target_sets") or 3),
                        key=f"dlg_sets_{rid}_{idx}_{item['exercise_id']}",
                    )
                    item["target_sets"] = int(new_sets)
                with p2:
                    new_min = st.number_input(
                        "Reps Mín",
                        min_value=1,
                        max_value=35,
                        value=int(item.get("target_rep_min") or 8),
                        key=f"dlg_rmin_{rid}_{idx}_{item['exercise_id']}",
                    )
                    item["target_rep_min"] = int(new_min)
                with p3:
                    new_max = st.number_input(
                        "Reps Máx",
                        min_value=1,
                        max_value=45,
                        value=max(int(new_min), int(item.get("target_rep_max") or 12)),
                        key=f"dlg_rmax_{rid}_{idx}_{item['exercise_id']}",
                    )
                    item["target_rep_max"] = max(int(new_min), int(new_max))
                with p4:
                    new_rest = st.number_input(
                        "Descanso(s)",
                        min_value=15,
                        max_value=600,
                        value=int(item.get("default_rest_seconds") or 90),
                        step=15,
                        key=f"dlg_rest_{rid}_{idx}_{item['exercise_id']}",
                    )
                    item["default_rest_seconds"] = int(new_rest)

    with st.expander("➕ Agregar / Intercalar Nuevo Ejercicio en la Plantilla", expanded=False):
        if ex_map:
            add_ex_id = st.selectbox(
                "Ejercicio a insertar",
                options=list(ex_map.keys()),
                format_func=lambda k: ex_map[k],
                key=f"dlg_add_ex_sel_{rid}",
            )
            pos_options = list(range(1, len(draft_items) + 2))
            add_pos = st.selectbox(
                "Posición donde insertar",
                options=pos_options,
                index=len(pos_options) - 1,
                format_func=lambda p: f"Al final (Posición #{p})" if p == len(draft_items) + 1 else f"Intercalar en Posición #{p}",
                key=f"dlg_add_ex_pos_{rid}",
            )
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                add_sets = st.number_input("Series obj.", min_value=1, max_value=12, value=3, key=f"dlg_add_s_{rid}")
            with ac2:
                add_rmin = st.number_input("Reps mín.", min_value=1, max_value=30, value=8, key=f"dlg_add_min_{rid}")
            with ac3:
                add_rmax = st.number_input("Reps máx.", min_value=1, max_value=40, value=12, key=f"dlg_add_max_{rid}")

            if st.button("➕ Insertar Ejercicio en la Rutina", use_container_width=True, key=f"dlg_btn_insert_ex_{rid}"):
                new_entry = {
                    "exercise_id": add_ex_id,
                    "target_sets": int(add_sets),
                    "target_rep_min": int(add_rmin),
                    "target_rep_max": max(int(add_rmin), int(add_rmax)),
                    "target_rpe": 8.0,
                    "progression_step_kg": 2.5,
                    "default_rest_seconds": 90,
                    "notes": "",
                }
                insert_idx = max(0, min(len(draft_items), int(add_pos) - 1))
                draft_items.insert(insert_idx, new_entry)
                st.rerun(scope="fragment" if hasattr(st, "fragment") else "app")

    col_sv, col_rst = st.columns([2, 1])
    with col_sv:
        if st.button("💾 Guardar Plantilla Actualizada", type="primary", use_container_width=True, key=f"dlg_save_routine_{rid}"):
            if not r_name.strip():
                st.warning("El nombre de la rutina no puede estar vacío.")
                return
            if not draft_items:
                st.warning("La rutina debe tener al menos 1 ejercicio.")
                return
            ok, msg = update_workout_routine_with_items(
                user_id=user_id,
                routine_id=rid,
                name=r_name.strip(),
                description=r_desc.strip(),
                accent_color=str(routine.get("accent_color") or "#FF5500"),
                items=draft_items,
            )
            if ok:
                st.session_state.pop(draft_key, None)
                st.toast(msg, icon="✅")
                st.rerun()
            else:
                st.error(msg)
    with col_rst:
        if st.button("🔄 Revertir", use_container_width=True, key=f"dlg_reset_draft_{rid}"):
            st.session_state.pop(draft_key, None)
            st.rerun()


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

    logged_sets: List[Dict[str, Any]] = active.get("sets") or []
    working_logged = [s for s in logged_sets if s.get("set_type") != "warmup"]
    live_tonnage = sum(float(s.get("weight_kg") or 0) * int(s.get("reps") or 0) for s in working_logged)
    live_prs = sum(1 for s in working_logged if s.get("is_pr"))

    st.markdown(
        f"""
<div style="background:linear-gradient(135deg, rgba(255,85,0,0.16) 0%, rgba(18,23,34,0.96) 100%); border:1px solid rgba(255,85,0,0.45); border-radius:16px; padding:12px 14px; margin-bottom:10px;">
<div style="display:flex; justify-content:space-between; align-items:center;">
<div>
<span class="trifecta-pillar-pill" style="background:#FF550033; color:#FF5500;">🔴 SESIÓN EN VIVO</span>
<div style="font-size:1.08rem; font-weight:800; color:#F8FAFC; margin-top:4px;">{active.get('session_title')}</div>
</div>
<div style="text-align:right; font-family:'JetBrains Mono', monospace;">
<div style="font-size:1.05rem; font-weight:800; color:#FF5500;">{live_tonnage:,.0f} kg</div>
<div style="font-size:0.74rem; color:#94A3B8;">{len(working_logged)} series ef. · 🏆 {live_prs} PRs</div>
</div>
</div>
</div>
""",
        unsafe_allow_html=True,
    )

    curr_ex_id = str(active.get("selected_exercise_id") or "")
    curr_ex = exercises_by_id.get(curr_ex_id, {})
    curr_ex_name = str(curr_ex.get("name", "Ejercicio Activo"))

    render_client_rest_timer(
        target_seconds=int(active.get("rest_target_s") or 90),
        start_epoch_ms=int(active.get("rest_timer_start_ms") or 0),
        auto_running=bool(active.get("rest_timer_running", False)),
        exercise_label=f"Descanso · {curr_ex_name[:26]}",
    )

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
<div class="trifecta-prog-banner" style="background:{rec.badge_color}1A; border-left:4px solid {rec.badge_color}; margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px;">
<span style="font-size:0.72rem; font-weight:800; color:{rec.badge_color}; background:{rec.badge_color}26; padding:2px 8px; border-radius:999px;">{rec.badge_label}</span>
<span style="font-size:0.74rem; color:#94A3B8; font-family:'JetBrains Mono', monospace;">1RM Epley: <b>{rec.estimated_1rm_epley:g} kg</b> · Brzycki: <b>{rec.estimated_1rm_brzycki:g} kg</b> ({rec.relative_intensity_pct:g}% 1RM)</span>
</div>
<div style="font-weight:800; font-size:0.96rem; color:#F8FAFC; margin-top:5px;">{rec.headline}</div>
<div style="font-size:0.80rem; color:#94A3B8; margin-top:2px;">{rec.explanation}</div>
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
                index=1,
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
                    # Si el día de hoy estaba planificado en el Planificador Semanal, marcarlo como completado
                    upsert_weekly_workout_plan_day(
                        user_id=user_id,
                        plan_date=date.today(),
                        focus_title=str(active.get("session_title", "Entrenamiento")),
                        routine_id=active.get("routine_id"),
                        status="completed",
                        notes=sess_notes,
                    )
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
# 4. PESTAÑA 2: PLANIFICADOR SEMANAL DE ENTRENAMIENTOS (REQUERIMIENTO 7)
# ============================================================================

@st.fragment
def _render_weekly_planner_fragment(
    user_id: str,
    access_token: str,
    routines: List[Dict[str, Any]],
    routine_items: List[Dict[str, Any]],
    exercises_by_id: Dict[str, Dict[str, Any]],
) -> None:
    """
    Vista interactiva «Planificador Semanal» estilo Agenda / Google Calendar:
    - Selección de día (Lunes a Domingo / fecha específica)
    - Grupo muscular o enfoque (Empuje, Tirón, Pierna Hipertrofia, etc.)
    - Rutina o plantilla asignada
    - Estado (Planificado, Completado, Descanso)
    """
    today = date.today()
    if "planner_week_monday" not in st.session_state:
        st.session_state["planner_week_monday"] = get_monday_of_week(today)

    week_monday: date = st.session_state["planner_week_monday"]
    week_sunday: date = week_monday + timedelta(days=6)

    nav_c1, nav_c2, nav_c3 = st.columns([1, 1.4, 1])
    with nav_c1:
        if st.button("◀ Semana Ant.", use_container_width=True, key="plan_prev_wk"):
            st.session_state["planner_week_monday"] = week_monday - timedelta(days=7)
            st.rerun(scope="fragment")
    with nav_c2:
        if st.button("📍 Semana Actual", use_container_width=True, key="plan_curr_wk"):
            st.session_state["planner_week_monday"] = get_monday_of_week(today)
            st.rerun(scope="fragment")
    with nav_c3:
        if st.button("Semana Sig. ▶", use_container_width=True, key="plan_next_wk"):
            st.session_state["planner_week_monday"] = week_monday + timedelta(days=7)
            st.rerun(scope="fragment")

    db_entries = fetch_weekly_workout_plan(user_id, access_token, week_monday.isoformat())
    local_store: Dict[str, Dict[str, Any]] = st.session_state.get("local_weekly_workout_plan") or {}

    plan_by_date: Dict[str, Dict[str, Any]] = {}
    for iso_k, row_v in local_store.items():
        plan_by_date[iso_k[:10]] = row_v
    for row_db in db_entries:
        d_key = str(row_db.get("plan_date") or "")[:10]
        if d_key:
            plan_by_date[d_key] = row_db

    routines_by_id = {str(r["id"]): r for r in routines}

    week_dates = [week_monday + timedelta(days=i) for i in range(7)]
    planned_cnt = sum(
        1 for d in week_dates if plan_by_date.get(d.isoformat(), {}).get("status") == "planned"
    )
    completed_cnt = sum(
        1 for d in week_dates if plan_by_date.get(d.isoformat(), {}).get("status") == "completed"
    )
    rest_cnt = sum(
        1 for d in week_dates if plan_by_date.get(d.isoformat(), {}).get("status") == "rest"
    )

    pk1, pk2, pk3 = st.columns(3)
    with pk1:
        render_kpi_card(
            label="Entrenos Planificados",
            value=f"{planned_cnt + completed_cnt} días",
            delta_text=f"Semana {week_monday.strftime('%d/%m')}–{week_sunday.strftime('%d/%m')}",
            delta_positive=True,
            accent_color="#3B82F6",
        )
    with pk2:
        render_kpi_card(
            label="Completados",
            value=f"{completed_cnt}",
            delta_text=f"{planned_cnt} pendientes esta semana",
            delta_positive=(completed_cnt > 0 or planned_cnt == 0),
            accent_color="#10B981",
        )
    with pk3:
        render_kpi_card(
            label="Días de Descanso",
            value=f"{rest_cnt}",
            delta_text="Recuperación programada",
            delta_positive=True,
            accent_color="#94A3B8",
        )

    # Formulario ergonómico para programar o actualizar un día de la semana
    with st.expander("➕ Programar / Editar Día de la Semana", expanded=True):
        day_options = {
            d.isoformat(): f"{SPANISH_WEEKDAYS[d.weekday()]} ({d.strftime('%d/%m/%Y')})"
            + (" · HOY" if d == today else "")
            for d in week_dates
        }
        default_day_iso = today.isoformat() if today.isoformat() in day_options else week_monday.isoformat()
        day_keys = list(day_options.keys())

        col_d, col_st = st.columns([1.4, 1])
        with col_d:
            sel_date_iso = st.selectbox(
                "Día de la semana / Fecha",
                options=day_keys,
                index=day_keys.index(default_day_iso),
                format_func=lambda k: day_options[k],
                key="planner_sel_day_iso",
            )
        existing_day = plan_by_date.get(sel_date_iso, {})
        with col_st:
            status_keys = ["planned", "completed", "rest"]
            curr_st = str(existing_day.get("status") or "planned")
            st_idx = status_keys.index(curr_st) if curr_st in status_keys else 0
            sel_status = st.selectbox(
                "Estado del día",
                options=status_keys,
                index=st_idx,
                format_func=lambda s: WEEKLY_PLAN_STATUS_LABELS[s]["label"],
                key="planner_sel_status",
            )

        col_foc, col_rt = st.columns([1.3, 1.1])
        with col_foc:
            curr_focus = str(existing_day.get("focus_title") or WORKOUT_FOCUS_PRESETS[0])
            preset_list = list(dict.fromkeys([curr_focus] + WORKOUT_FOCUS_PRESETS))
            sel_focus_preset = st.selectbox(
                "Grupo muscular o enfoque",
                options=preset_list,
                index=0,
                key="planner_sel_focus_preset",
            )
        with col_rt:
            r_opts = {"": "— Sin rutina fija / Libre —"}
            for r in routines:
                r_opts[str(r["id"])] = f"📋 {r.get('name')}"
            curr_rid = str(existing_day.get("routine_id") or "")
            r_keys = list(r_opts.keys())
            r_idx = r_keys.index(curr_rid) if curr_rid in r_keys else 0
            sel_routine_id = st.selectbox(
                "Rutina o plantilla asignada",
                options=r_keys,
                index=r_idx,
                format_func=lambda k: r_opts[k],
                key="planner_sel_routine_id",
            )

        col_custom_foc, col_notes = st.columns(2)
        with col_custom_foc:
            custom_focus = st.text_input(
                "Personalizar título de enfoque (opcional)",
                value="",
                placeholder="Ej. Pecho pesado + Hombro lateral",
                key="planner_custom_focus",
            )
        with col_notes:
            day_notes = st.text_input(
                "Notas / Horario",
                value=str(existing_day.get("notes") or ""),
                placeholder="Ej. 7:00 AM · Priorizar press inclinado",
                key="planner_day_notes",
            )

        if st.button("📅 Guardar en Planificador Semanal", type="primary", use_container_width=True, key="btn_save_planner_day"):
            final_focus = (
                "Descanso y Recuperación"
                if sel_status == "rest" and not custom_focus.strip()
                else (custom_focus.strip() or sel_focus_preset)
            )
            ok, msg = upsert_weekly_workout_plan_day(
                user_id=user_id,
                plan_date=date.fromisoformat(sel_date_iso),
                focus_title=final_focus,
                routine_id=sel_routine_id if sel_routine_id else None,
                status=sel_status,
                notes=day_notes,
            )
            if ok:
                st.toast(msg, icon="🗓️")
                st.rerun(scope="fragment")
            else:
                st.error(msg)

    st.markdown(
        f"##### 🗓️ Agenda de la Semana ({week_monday.strftime('%d/%b')} al {week_sunday.strftime('%d/%b/%Y')})"
    )

    for d_obj in week_dates:
        d_iso = d_obj.isoformat()
        w_name = SPANISH_WEEKDAYS[d_obj.weekday()]
        is_today = d_obj == today
        day_plan = plan_by_date.get(d_iso)

        if day_plan:
            st_code = str(day_plan.get("status") or "planned")
            st_meta = WEEKLY_PLAN_STATUS_LABELS.get(st_code, WEEKLY_PLAN_STATUS_LABELS["planned"])
            focus_txt = str(day_plan.get("focus_title") or "Entrenamiento")
            rid_assigned = str(day_plan.get("routine_id") or "")
            assigned_routine = routines_by_id.get(rid_assigned)
            r_badge_txt = f"📋 {assigned_routine.get('name')}" if assigned_routine else "⚡ Sesión Libre"
            notes_txt = str(day_plan.get("notes") or "")
            border_color = "#FF5500" if is_today else st_meta["color"]
        else:
            st_code = "unplanned"
            st_meta = {"label": "⚪ Sin programar", "color": "#64748B", "bg": "#1E293B"}
            focus_txt = "Sin entrenamiento asignado"
            assigned_routine = None
            r_badge_txt = "Usa el panel superior para asignar rutina o descanso"
            notes_txt = ""
            border_color = "#FF5500" if is_today else "#263044"

        today_pill = (
            "<span style='background:#FF550033; color:#FF5500; border:1px solid #FF550066; padding:1px 7px; border-radius:999px; font-size:0.68rem; font-weight:800; margin-left:6px;'>HOY</span>"
            if is_today
            else ""
        )
        notes_html = (
            f"<div style='font-size:0.74rem; color:#CBD5E1; margin-top:3px;'>📝 {notes_txt}</div>"
            if notes_txt
            else ""
        )

        st.markdown(
            f"""
<div style="background:#121722; border:1px solid #263044; border-left:4px solid {border_color}; border-radius:12px; padding:10px 14px; margin-bottom:6px;">
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
<div>
<span style="font-size:0.88rem; font-weight:800; color:#F8FAFC;">{w_name} {d_obj.strftime('%d/%m')}</span>{today_pill}
</div>
<span style="font-size:0.72rem; font-weight:700; color:{st_meta['color']}; background:{st_meta['bg']}; border:1px solid {st_meta['color']}55; padding:2px 9px; border-radius:999px;">
{st_meta['label']}
</span>
</div>
<div style="font-size:0.94rem; font-weight:700; color:#F8FAFC; margin-top:4px;">{focus_txt}</div>
<div style="font-size:0.76rem; color:#94A3B8; margin-top:2px;">{r_badge_txt}</div>
{notes_html}
</div>
""",
            unsafe_allow_html=True,
        )

        if day_plan:
            ac1, ac2, ac3, ac4 = st.columns([1.4, 1.1, 1.1, 0.7])
            with ac1:
                if st_code != "rest" and st.button(
                    "▶ Entrenar",
                    key=f"plan_start_{d_iso}",
                    type="primary",
                    use_container_width=True,
                ):
                    _start_active_workout(assigned_routine, routine_items, exercises_by_id)
                    st.rerun()
            with ac2:
                if st_code != "completed" and st.button(
                    "✅ Completado",
                    key=f"plan_done_{d_iso}",
                    use_container_width=True,
                ):
                    upsert_weekly_workout_plan_day(
                        user_id=user_id,
                        plan_date=d_obj,
                        focus_title=focus_txt,
                        routine_id=str(day_plan.get("routine_id")) if day_plan.get("routine_id") else None,
                        status="completed",
                        notes=notes_txt,
                    )
                    st.rerun(scope="fragment")
            with ac3:
                if st_code != "rest" and st.button(
                    "🧘 Descanso",
                    key=f"plan_rest_{d_iso}",
                    use_container_width=True,
                ):
                    upsert_weekly_workout_plan_day(
                        user_id=user_id,
                        plan_date=d_obj,
                        focus_title="Descanso / Recuperación",
                        routine_id=None,
                        status="rest",
                        notes=notes_txt,
                    )
                    st.rerun(scope="fragment")
            with ac4:
                if st.button("🗑️", key=f"plan_del_{d_iso}", help="Limpiar día", use_container_width=True):
                    delete_weekly_workout_plan_day(user_id, d_obj)
                    st.rerun(scope="fragment")


# ============================================================================
# 5. PESTAÑA 3: ANALÍTICA MULTITEMPORAL (8 HORIZONTES) Y DENSIDAD / DESCANSO
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
# 6. PUNTO DE ENTRADA DEL PILAR 1 (workout_view.py)
# ============================================================================

def render_workout_view() -> None:
    """Renderiza el Módulo 1 completo: Entrenar Ahora, Planificador Semanal, Analítica y Catálogo."""
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
        subtitle="Sobrecarga progresiva, planificador semanal, cronómetro inter-serie y volumen 1D–1Y",
        accent_hex=PALETTE["accent_workout"],
        badge_text="🏋️ Pilar 1 · Hypertrophy & Strength",
    )

    tab_live, tab_planner, tab_analytics, tab_catalog = st.tabs(
        [
            "⚡ Entrenar Ahora",
            "🗓️ Planificador Semanal",
            "📊 Analítica (1D–1Y)",
            "📋 Rutinas y Catálogo",
        ]
    )

    with tab_live:
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
                    r_items.sort(key=lambda x: int(x.get("order_index") or 1))
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
                        b_col1, b_col2, b_col3 = st.columns([2.2, 1.1, 1.1])
                        with b_col1:
                            if st.button(
                                f"▶ Iniciar «{r.get('name')}»",
                                key=f"btn_start_routine_{rid}",
                                type="primary",
                                use_container_width=True,
                            ):
                                _start_active_workout(r, routine_items, exercises_by_id)
                                st.rerun()
                        with b_col2:
                            if st.button(
                                "📄 Duplicar",
                                key=f"btn_dup_live_{rid}",
                                help="Clona esta rutina como «(Copia)» en 1 clic.",
                                use_container_width=True,
                            ):
                                ok, msg = duplicate_workout_routine(user_id, rid)
                                st.toast(msg, icon="📄" if ok else "⚠️")
                                st.rerun()
                        with b_col3:
                            if st.button(
                                "🛠️ Editar",
                                key=f"btn_edit_live_{rid}",
                                help="Reordenar ejercicios o editar series/descanso.",
                                use_container_width=True,
                            ):
                                st.session_state.pop(f"routine_edit_draft_{rid}", None)
                                _open_edit_routine_dialog(user_id, r, routine_items, exercises)

            if sessions:
                with st.expander(f"🕒 Últimas Sesiones Registradas ({len(sessions[:5])})", expanded=False):
                    for sess in sessions[:5]:
                        dt_str = str(sess.get("started_at") or "")[:10]
                        dur = sess.get("duration_minutes") or "—"
                        st.markdown(
                            f"- **{sess.get('session_title')}** (`{dt_str}`) · Duración: `{dur} min` · "
                            f"Fatiga: `{sess.get('perceived_fatigue') or '—'}/10`"
                        )

    with tab_planner:
        _render_weekly_planner_fragment(
            user_id=user_id,
            access_token=access_token,
            routines=routines,
            routine_items=routine_items,
            exercises_by_id=exercises_by_id,
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
                st.markdown(f"#### 📋 Gestión de Rutinas ({len(routines)}) · Duplicar y Reordenar")
                st.caption("Clona cualquier rutina en 1 clic, edita su plantilla o reordena sus ejercicios (↑ / ↓).")
                for r in routines:
                    rid = str(r["id"])
                    r_items = [it for it in routine_items if str(it.get("routine_id")) == rid]
                    r_items.sort(key=lambda x: int(x.get("order_index") or 1))

                    rc1, rc_dup, rc_ed, rc_del = st.columns([2.5, 1.05, 1.15, 0.65], vertical_alignment="center")
                    with rc1:
                        st.markdown(
                            f"**{r.get('name')}** ({len(r_items)} ej.) — _{r.get('description') or 'Plantilla activa'}_"
                        )
                    with rc_dup:
                        if st.button("📄 Duplicar", key=f"cat_dup_routine_{rid}", use_container_width=True):
                            ok, msg = duplicate_workout_routine(user_id, rid)
                            st.toast(msg, icon="📄" if ok else "⚠️")
                            st.rerun()
                    with rc_ed:
                        if st.button("🛠️ Editar / Orden", key=f"cat_ed_routine_{rid}", use_container_width=True):
                            st.session_state.pop(f"routine_edit_draft_{rid}", None)
                            _open_edit_routine_dialog(user_id, r, routine_items, exercises)
                    with rc_del:
                        if st.button("🗑️", key=f"cat_del_routine_{rid}", use_container_width=True):
                            delete_workout_routine(user_id, rid)
                            st.rerun()

                    if r_items:
                        with st.expander(f"🔢 Ver orden de ejercicios en «{r.get('name')}» (↑ / ↓)", expanded=False):
                            for idx_it, it_row in enumerate(r_items):
                                ex_obj = exercises_by_id.get(str(it_row.get("exercise_id")), {})
                                ex_nm = ex_obj.get("name", "Ejercicio")
                                ic_txt, ic_up, ic_dn = st.columns([3.8, 0.7, 0.7], vertical_alignment="center")
                                with ic_txt:
                                    st.markdown(
                                        f"`#{idx_it + 1}` **{ex_nm}** · "
                                        f"{it_row.get('target_sets', 3)}×{it_row.get('target_rep_min', 8)}–{it_row.get('target_rep_max', 12)} reps "
                                        f"@ RPE {it_row.get('target_rpe', 8.0)} · ⏱️ {it_row.get('default_rest_seconds', 90)}s"
                                    )
                                with ic_up:
                                    if st.button(
                                        "↑",
                                        key=f"quick_up_{rid}_{idx_it}",
                                        disabled=(idx_it == 0),
                                        use_container_width=True,
                                    ):
                                        move_routine_item_order(user_id, rid, idx_it, "up")
                                        st.rerun()
                                with ic_dn:
                                    if st.button(
                                        "↓",
                                        key=f"quick_dn_{rid}_{idx_it}",
                                        disabled=(idx_it == len(r_items) - 1),
                                        use_container_width=True,
                                    ):
                                        move_routine_item_order(user_id, rid, idx_it, "down")
                                        st.rerun()

        with st.container(border=True):
            st.markdown(f"#### 🏋️ Catálogo de Ejercicios Ponderados ({len(exercises)}) · Editable")
            m_filter = st.selectbox(
                "Filtrar por Músculo Primario",
                options=["all"] + list(MUSCLE_LABELS.keys()),
                format_func=lambda m: "Todos los grupos musculares" if m == "all" else MUSCLE_LABELS.get(m, m),
                key="catalog_tab_muscle_filter",
            )
            filtered_ex = [
                ex for ex in exercises if m_filter == "all" or ex.get("primary_muscle") == m_filter
            ]
            for ex in filtered_ex[:30]:
                ex_id = str(ex.get("id") or "")
                prim_lbl = MUSCLE_LABELS.get(str(ex.get("primary_muscle", "")), str(ex.get("primary_muscle", "")))
                sec_list = ex.get("secondary_muscles") or []
                sec_lbls = ", ".join(MUSCLE_LABELS.get(s, s) for s in sec_list) or "Ninguno (Aislamiento)"
                eq_lbl = EQUIPMENT_LABELS.get(str(ex.get("equipment", "")), str(ex.get("equipment", "")))
                custom_badge = " · 👤 Personalizado" if ex.get("user_id") else ""
                ex_notes = str(ex.get("notes") or "").strip()
                notes_line = (
                    f"<div style='font-size:0.75rem; color:#CBD5E1; margin-top:4px;'>📝 <i>{ex_notes}</i></div>"
                    if ex_notes
                    else ""
                )

                col_ex_card, col_ex_edit = st.columns([4.8, 1.0], vertical_alignment="center")
                with col_ex_card:
                    st.markdown(
                        f"""
<div style="padding:10px 12px; border-radius:12px; background:#1A2232; border:1px solid #263044; margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; align-items:center;">
<span style="font-weight:700; font-size:0.92rem; color:#F8FAFC;">{ex.get('name')}{custom_badge}</span>
<span style="font-size:0.73rem; color:#FF5500; background:#FF55001F; padding:2px 8px; border-radius:999px;">{prim_lbl} (1.0x)</span>
</div>
<div style="font-size:0.78rem; color:#94A3B8; margin-top:4px;">
Secundarios (0.5x): {sec_lbls} · Equipo: <code>{eq_lbl}</code>
</div>
{notes_line}
</div>
""",
                        unsafe_allow_html=True,
                    )
                with col_ex_edit:
                    if st.button("✏️ Editar", key=f"btn_edit_ex_{ex_id}", use_container_width=True):
                        _open_edit_exercise_dialog(user_id, ex)
