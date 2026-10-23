"""
Módulo 3: Hábitos Generales Editables, Dashboard Reordenable, Heatmaps 90d,
Progreso Parcial Tripartito (Pendiente 0%, En progreso >0%-<100%, Completado >=100%),
Métricas Agregadas (Promedio Semanal 7d y Sumatoria Mensual) y Metas/Planes.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from src.auth.session_manager import get_current_user_id
from src.config.theme import PALETTE, render_pillar_header
from src.models.habit_models import (
    HABIT_COLOR_PRESETS,
    HABIT_ICON_PRESETS,
    LIFE_AREAS,
    HabitAnalytics,
)
from src.services.habit_streak_engine import (
    add_goal_milestone,
    calculate_goal_progress_pct,
    calculate_habit_analytics,
    create_habit,
    create_personal_goal_with_milestones,
    delete_goal_milestone,
    delete_habit,
    delete_personal_goal,
    fetch_goal_milestones,
    fetch_habit_logs,
    fetch_habits,
    fetch_personal_goals,
    move_habit_order,
    toggle_goal_milestone,
    toggle_habit_pin,
    update_habit,
    upsert_habit_log,
)


# ============================================================================
# 1. UTILIDADES VISUALES: ESTADOS TRIPARTITOS, FORMATOS Y HEATMAP 90 DÍAS
# ============================================================================

def _smart_step_for_target(metric_type: str, target_val: float) -> float:
    """Determina el incremento/decremento táctil ideal según la magnitud de la meta diaria."""
    if metric_type == "DURATION":
        if target_val <= 4.0:
            return 0.5
        if target_val <= 30.0:
            return 5.0
        return 15.0
    if target_val <= 5.0:
        return 0.5
    if target_val <= 25.0:
        return 1.0
    if target_val <= 200.0:
        return 10.0
    if target_val <= 2500.0:
        return 250.0
    return 1000.0


def _format_num(val: float) -> str:
    """Formatea números eliminando decimales .0 innecesarios y añadiendo separador de miles."""
    if abs(val - round(val)) < 1e-6:
        return f"{int(round(val)):,}"
    return f"{val:,.1f}"


def _format_status_pct(pct: float, status: str) -> str:
    """
    Formatea el porcentaje de cumplimiento evitando que un valor parcial como 9,999 / 10,000 (99.99%)
    se redondee visualmente a 100% antes de completar la meta.
    """
    if status == "PENDING" or pct <= 0.0:
        return "0%"
    if status == "PARTIAL":
        capped = min(99.9, pct)
        if abs(capped - round(capped)) < 0.05 and capped < 99.0:
            return f"{int(round(capped))}%"
        return f"{capped:.1f}%"
    return f"{pct:.0f}%"


def _get_status_visual_tokens(status: str) -> Tuple[str, str, str]:
    """
    Retorna (color_hex, icono_estado, etiqueta_corta) para los 3 estados definidos:
    - PENDING (0%): Pendiente
    - PARTIAL (>0% y <100%): En progreso / Parcial
    - COMPLETED (>=100%): Completado
    """
    if status == "COMPLETED":
        return "#22C55E", "✔", "Completado"
    if status == "PARTIAL":
        return "#F59E0B", "⏳", "En progreso / Parcial"
    return "#94A3B8", "⬜", "Pendiente"


def _render_quantitative_summary_strip(
    analytics: HabitAnalytics,
    unit_label: str,
    accent_color: str,
    reference_date: date,
) -> None:
    """
    Renderiza el bloque compacto con las 2 métricas agregadas requeridas para hábitos cuantitativos:
    1. Promedio diario semanal (últimos 7 días)
    2. Sumatoria acumulada mensual (mes corriente)
    """
    month_names = [
        "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"
    ]
    month_lbl = month_names[reference_date.month - 1]

    st.markdown(
        f"""
        <div style="
            display:grid; grid-template-columns: 1fr 1fr; gap:8px;
            margin-top:8px; margin-bottom:4px;
        ">
            <div style="
                background:#1A2232; border:1px solid #263044; border-left:3px solid {accent_color};
                border-radius:10px; padding:8px 10px;
            ">
                <div style="font-size:0.70rem; color:#94A3B8; font-weight:600; text-transform:uppercase; letter-spacing:0.03em;">
                    📊 Promedio Diario (7d)
                </div>
                <div class="trifecta-kpi-value" style="font-size:1.02rem; color:#F8FAFC; margin-top:2px;">
                    {_format_num(analytics.weekly_daily_avg_7d)} <span style="font-size:0.75rem; font-weight:500; color:#94A3B8;">{unit_label}/día</span>
                </div>
                <div style="font-size:0.68rem; color:#94A3B8;">
                    {analytics.weekly_active_days_7d} de 7 días con registro
                </div>
            </div>
            <div style="
                background:#1A2232; border:1px solid #263044; border-left:3px solid #10B981;
                border-radius:10px; padding:8px 10px;
            ">
                <div style="font-size:0.70rem; color:#94A3B8; font-weight:600; text-transform:uppercase; letter-spacing:0.03em;">
                    ∑ Acumulado ({month_lbl})
                </div>
                <div class="trifecta-kpi-value" style="font-size:1.02rem; color:#10B981; margin-top:2px;">
                    {_format_num(analytics.monthly_accumulated_sum)} <span style="font-size:0.75rem; font-weight:500; color:#94A3B8;">{unit_label}</span>
                </div>
                <div style="font-size:0.68rem; color:#94A3B8;">
                    {analytics.monthly_active_days} días activos este mes
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_habit_heatmap_90d(analytics: HabitAnalytics, color_hex: str, unit_label: str) -> None:
    """
    Renderiza el mapa de calor de los últimos 90 días estilo GitHub / HabitKit
    distinguiendo visualmente los 3 estados: Pendiente (0%), Parcial (>0% y <100%), Completado (>=100%).
    """
    cells_html: List[str] = []
    for cell in analytics.heatmap_90d:
        if cell.daily_status == "COMPLETED":
            bg = color_hex
            border = f"1px solid {color_hex}"
            box_shadow = f"0 0 6px {color_hex}55"
        elif cell.daily_status == "PARTIAL":
            bg = f"{color_hex}59"
            border = "1px solid #F59E0B99"
            box_shadow = "none"
        else:
            bg = "#1A2232"
            border = "1px solid #263044"
            box_shadow = "none"

        pct_txt = _format_status_pct(cell.completion_pct, cell.daily_status)
        if cell.daily_status == "COMPLETED":
            status_txt = f"Completado · {pct_txt}"
        elif cell.daily_status == "PARTIAL":
            status_txt = f"En progreso / Parcial · {pct_txt}"
        else:
            status_txt = "Pendiente · 0%"

        val_txt = f"{_format_num(cell.recorded_value)} {unit_label}" if cell.recorded_value > 0 else "0"
        tooltip = f"{cell.date_label}: {val_txt} ({status_txt})"
        cells_html.append(
            f'<div title="{tooltip}" style="'
            f'width:100%; aspect-ratio:1/1; border-radius:3px; '
            f'background:{bg}; border:{border}; box-shadow:{box_shadow};'
            f'"></div>'
        )

    grid_str = "".join(cells_html)
    start_lbl = analytics.heatmap_90d[0].date_label if analytics.heatmap_90d else "Hace 90d"
    end_lbl = analytics.heatmap_90d[-1].date_label if analytics.heatmap_90d else "Hoy"

    st.markdown(
        f"""
        <div style="margin-top:8px; padding-top:8px; border-top:1px solid rgba(38,48,68,0.65);">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.71rem; color:#94A3B8; margin-bottom:5px;">
                <span>Consistencia 90d ({start_lbl} → {end_lbl})</span>
                <span>🔥 <b>{analytics.current_streak}d</b> · 🏆 Mejor: <b>{analytics.best_streak}d</b> · 30d: <b>{analytics.adherence_30d_pct:.0f}%</b></span>
            </div>
            <div style="
                display:grid;
                grid-template-columns: repeat(30, minmax(0, 1fr));
                gap: 3px;
                width: 100%;
            ">
                {grid_str}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# 2. MODALES NATIVOS (@st.dialog) PARA CREAR/EDITAR HÁBITOS Y METAS ANUALES
# ============================================================================

@st.dialog("✨ Nuevo Hábito Personalizado")
def _open_create_habit_dialog(user_id: str, goals: List[Dict[str, Any]]) -> None:
    """Modal móvil para crear un tracker de cualquier tipo (BOOLEAN, NUMERIC, DURATION, RATING)."""
    st.caption("Configura tu métrica diaria y vincúlala opcionalmente a una Meta Personal.")

    metric_options = {
        "BOOLEAN": "✅ Booleano (1 toque: Cumplido / Pendiente)",
        "NUMERIC": "🔢 Numérico (Cantidad con unidad libre: Litros, págs, pasos)",
        "DURATION": "⏱️ Duración (Tiempo dedicado: minutos u horas)",
        "RATING": "⭐ Escala / Valoración (Slider diario 1–5 o 1–10)",
    }
    selected_mtype = st.selectbox(
        "Tipo de Registro (`metric_type`)",
        options=list(metric_options.keys()),
        format_func=lambda k: metric_options[k],
        key="dlg_new_habit_mtype",
    )

    if selected_mtype == "BOOLEAN":
        default_unit = "check"
        default_target = 1.0
        placeholder_name = "Ej. Tomar creatina 5g / Leer antes de dormir"
    elif selected_mtype == "NUMERIC":
        default_unit = "Litros"
        default_target = 3.0
        placeholder_name = "Ej. Hidratación diaria / Pasos (10,000)"
    elif selected_mtype == "DURATION":
        default_unit = "min"
        default_target = 30.0
        placeholder_name = "Ej. Estudio de inglés / Meditación"
    else:
        default_unit = "pts"
        default_target = 10.0
        placeholder_name = "Ej. Nivel de energía diaria / Enfoque mental"

    with st.form("form_create_habit_modal", clear_on_submit=False):
        name_in = st.text_input("Nombre del Hábito", placeholder=placeholder_name)

        col_icon, col_color = st.columns(2)
        with col_icon:
            icon_in = st.selectbox("Icono", options=HABIT_ICON_PRESETS, index=0)
        with col_color:
            color_choice = st.selectbox(
                "Color de Acento",
                options=[c["hex"] for c in HABIT_COLOR_PRESETS],
                format_func=lambda hx: next((c["label"] for c in HABIT_COLOR_PRESETS if c["hex"] == hx), hx),
                index=0,
            )

        if selected_mtype == "BOOLEAN":
            unit_in = "check"
            target_in = 1.0
            st.caption("ℹ️ Los hábitos booleanos se completan al 100% con un solo toque.")
        elif selected_mtype == "RATING":
            unit_in = "pts"
            scale_choice = st.radio(
                "Escala de Valoración",
                options=[5.0, 10.0],
                format_func=lambda x: f"Escala 1 a {int(x)}",
                horizontal=True,
                index=1,
            )
            target_in = float(scale_choice)
        else:
            col_t, col_u = st.columns(2)
            with col_t:
                target_in = st.number_input(
                    "Meta Diaria Objetivo",
                    min_value=0.1,
                    max_value=1000000.0,
                    value=float(default_target),
                    step=0.5 if default_target < 10 else 100.0,
                )
            with col_u:
                unit_in = st.text_input("Unidad de Medida", value=default_unit, placeholder="Litros, pasos, min...")

        freq_in = st.slider(
            "Frecuencia Objetivo (días por semana)",
            min_value=1,
            max_value=7,
            value=7,
        )

        goal_map = {"": "— Sin vincular a meta específica —"}
        for g in goals:
            if g.get("status") != "archived":
                goal_map[str(g["id"])] = f"🎯 {g.get('title')} ({g.get('life_area')})"

        linked_goal_in = st.selectbox(
            "Vincular a Meta Personal (`linked_goal_id`)",
            options=list(goal_map.keys()),
            format_func=lambda k: goal_map.get(k, k),
        )

        pinned_in = st.checkbox("📌 Fijar en la parte superior del Dashboard (`is_pinned`)", value=False)

        submitted = st.form_submit_button("💾 Crear Hábito", type="primary", use_container_width=True)
        if submitted:
            if not name_in.strip():
                st.error("Por favor ingresa un nombre para el hábito.")
            else:
                ok, msg = create_habit(
                    user_id=user_id,
                    name=name_in,
                    icon=icon_in,
                    color_hex=color_choice,
                    metric_type=selected_mtype,  # type: ignore[arg-type]
                    unit_label=unit_in,
                    daily_target_value=float(target_in),
                    frequency_days_per_week=int(freq_in),
                    linked_goal_id=linked_goal_in if linked_goal_in else None,
                    is_pinned=pinned_in,
                )
                if ok:
                    st.toast(msg, icon="✅")
                    st.rerun()
                else:
                    st.error(msg)


@st.dialog("✏️ Editar Hábito")
def _open_edit_habit_dialog(
    user_id: str,
    habit: Dict[str, Any],
    goals: List[Dict[str, Any]],
) -> None:
    """Modal móvil para editar los parámetros de un hábito existente."""
    habit_id = str(habit["id"])
    curr_mtype = str(habit.get("metric_type", "BOOLEAN")).upper()
    mtypes = ["BOOLEAN", "NUMERIC", "DURATION", "RATING"]
    mtype_idx = mtypes.index(curr_mtype) if curr_mtype in mtypes else 0

    with st.form(f"form_edit_habit_{habit_id}"):
        name_in = st.text_input("Nombre del Hábito", value=str(habit.get("name", "")))
        col_i, col_c = st.columns(2)
        with col_i:
            curr_icon = str(habit.get("icon", "⚡"))
            icons_list = HABIT_ICON_PRESETS if curr_icon in HABIT_ICON_PRESETS else [curr_icon] + HABIT_ICON_PRESETS
            icon_in = st.selectbox("Icono", options=icons_list, index=0)
        with col_c:
            curr_hex = str(habit.get("color_hex", "#8B5CF6"))
            hex_list = [c["hex"] for c in HABIT_COLOR_PRESETS]
            if curr_hex not in hex_list:
                hex_list.insert(0, curr_hex)
            color_in = st.selectbox(
                "Color",
                options=hex_list,
                index=hex_list.index(curr_hex),
                format_func=lambda hx: next((c["label"] for c in HABIT_COLOR_PRESETS if c["hex"] == hx), hx),
            )

        new_mtype = st.selectbox("Tipo de Métrica", options=mtypes, index=mtype_idx)
        col_t, col_u = st.columns(2)
        with col_t:
            target_in = st.number_input(
                "Meta Diaria",
                min_value=0.1,
                max_value=1000000.0,
                value=float(habit.get("daily_target_value") or 1.0),
            )
        with col_u:
            unit_in = st.text_input("Unidad", value=str(habit.get("unit_label", "check")))

        freq_in = st.slider(
            "Frecuencia Semanal (días/semana)",
            min_value=1,
            max_value=7,
            value=int(habit.get("frequency_days_per_week") or 7),
        )

        goal_map = {"": "— Sin vincular a meta —"}
        for g in goals:
            goal_map[str(g["id"])] = f"🎯 {g.get('title')}"
        curr_goal_id = str(habit.get("linked_goal_id") or "")
        goal_keys = list(goal_map.keys())
        goal_idx = goal_keys.index(curr_goal_id) if curr_goal_id in goal_keys else 0

        linked_goal_in = st.selectbox(
            "Meta Personal Vinculada",
            options=goal_keys,
            index=goal_idx,
            format_func=lambda k: goal_map.get(k, k),
        )

        col_p, col_a = st.columns(2)
        with col_p:
            pinned_in = st.checkbox("📌 Fijar arriba", value=bool(habit.get("is_pinned", False)))
        with col_a:
            archived_in = st.checkbox("📦 Archivar hábito", value=bool(habit.get("is_archived", False)))

        saved = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
        if saved:
            ok, msg = update_habit(
                user_id=user_id,
                habit_id=habit_id,
                name=name_in,
                icon=icon_in,
                color_hex=color_in,
                metric_type=new_mtype,  # type: ignore[arg-type]
                unit_label=unit_in,
                daily_target_value=float(target_in),
                frequency_days_per_week=int(freq_in),
                linked_goal_id=linked_goal_in if linked_goal_in else None,
                is_pinned=pinned_in,
                is_archived=archived_in,
            )
            if ok:
                st.toast(msg, icon="✅")
                st.rerun()
            else:
                st.error(msg)


@st.dialog("🎯 Nueva Meta Personal y Plan de Desarrollo")
def _open_create_goal_dialog(user_id: str, habits: List[Dict[str, Any]]) -> None:
    """Modal para crear una Meta Anual/Personal desglosada en Hitos y vinculada a Hábitos."""
    st.caption("Conecta tus propósitos de largo plazo con un plan de hitos secuenciales y hábitos diarios.")
    with st.form("form_create_personal_goal", clear_on_submit=False):
        title_in = st.text_input(
            "Título de la Meta / Propósito",
            placeholder="Ej. Dominar Inglés Conversacional B2 / Bajar a 12% grasa",
        )
        col_area, col_date = st.columns(2)
        with col_area:
            area_in = st.selectbox("Área de Vida", options=LIFE_AREAS, index=0)
        with col_date:
            target_date_in = st.date_input(
                "Fecha Objetivo",
                value=date(date.today().year, 12, 31) if date.today().month < 11 else (date.today() + timedelta(days=180)),
                min_value=date.today() + timedelta(days=1),
            )

        desc_in = st.text_area(
            "Motivación / Resultado Esperado (Opcional)",
            placeholder="¿Cómo sabrás que lograste esta meta?",
            height=68,
        )

        st.markdown("##### 🗺️ Hitos del Plan de Desarrollo (`goal_milestones`)")
        st.caption("Define al menos 3 pasos concretos y verificables:")
        m1 = st.text_input("Hito 1 (Corto plazo)", placeholder="Ej. Completar módulo intermedio / primeros 30 días")
        m2 = st.text_input("Hito 2 (Mediano plazo)", placeholder="Ej. Aprobar primer simulacro / llegar a la mitad de la meta")
        m3 = st.text_input("Hito 3 (Consolidación)", placeholder="Ej. Certificación o logro final verificado")

        habit_options = {str(h["id"]): f"{h.get('icon', '⚡')} {h.get('name')}" for h in habits}
        linked_habits_selected = st.multiselect(
            "🔗 Vincular Hábitos Diarios que impulsan esta meta",
            options=list(habit_options.keys()),
            format_func=lambda k: habit_options.get(k, k),
        )

        submitted = st.form_submit_button("🚀 Crear Meta y Plan de Desarrollo", type="primary", use_container_width=True)
        if submitted:
            if not title_in.strip():
                st.error("Por favor ingresa un título para la meta.")
            else:
                milestones_list = [m for m in [m1, m2, m3] if m and m.strip()]
                ok, msg = create_personal_goal_with_milestones(
                    user_id=user_id,
                    title=title_in,
                    life_area=area_in,
                    target_date=target_date_in,
                    description=desc_in,
                    milestone_titles=milestones_list,
                    linked_habit_ids=linked_habits_selected,
                )
                if ok:
                    st.toast(msg, icon="🎯")
                    st.rerun()
                else:
                    st.error(msg)


# ============================================================================
# 3. PESTAÑA 1: DASHBOARD DIARIO REORDENABLE Y HEATMAPS (@st.fragment)
# ============================================================================

@st.fragment
def _render_daily_habits_fragment(
    user_id: str,
    selected_date: date,
    reorder_mode: bool,
) -> None:
    """
    Fragmento reactivo (@st.fragment) que permite marcar o ajustar cualquier hábito,
    visualizar su estado tripartito (Pendiente 0%, En progreso >0%-<100%, Completado >=100%),
    consultar su promedio semanal (7d) y acumulado mensual, y reordenar tarjetas.
    """
    access_token = st.session_state.get("access_token") or ""
    habits = fetch_habits(user_id, access_token, include_archived=False)
    logs = fetch_habit_logs(user_id, access_token, days_back=120)
    goals = fetch_personal_goals(user_id, access_token)
    goals_by_id = {str(g["id"]): g for g in goals}

    if not habits:
        with st.container(border=True):
            st.markdown(
                """
                <div style="text-align:center; padding:18px 8px;">
                    <div style="font-size:2rem; margin-bottom:6px;">⚡</div>
                    <div style="font-weight:700; font-size:1.02rem; color:#F8FAFC;">
                        Tu Dashboard de Hábitos está listo
                    </div>
                    <div style="font-size:0.84rem; color:#94A3B8; margin-top:4px;">
                        Pulsa <b>«➕ Nuevo Hábito»</b> arriba para crear tu primer registro booleano,
                        numérico (ej. litros de agua o pasos), de duración o de valoración diaria.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    # Calcular analítica de cada hábito para la fecha seleccionada
    analytics_map: Dict[str, HabitAnalytics] = {
        str(h["id"]): calculate_habit_analytics(h, logs, reference_date=selected_date)
        for h in habits
    }

    total_habits = len(habits)
    completed_today = sum(1 for a in analytics_map.values() if a.today_status == "COMPLETED")
    partial_today = sum(1 for a in analytics_map.values() if a.today_status == "PARTIAL")
    pending_today = total_habits - completed_today - partial_today

    # Avance ponderado global del día (incluyendo progreso parcial de hábitos cuantitativos)
    weighted_daily_pct = (
        round(sum(a.today_bar_pct for a in analytics_map.values()) / total_habits, 1)
        if total_habits > 0
        else 0.0
    )

    if completed_today == total_habits and total_habits > 0:
        bar_color = "#22C55E"
    elif partial_today > 0 or completed_today > 0:
        bar_color = PALETTE["accent_habits"]
    else:
        bar_color = "#94A3B8"

    st.markdown(
        f"""
        <div style="
            background:#121722; border:1px solid #263044; border-radius:14px;
            padding:12px 14px; margin-bottom:12px;
        ">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:0.84rem; font-weight:600; color:#F8FAFC;">
                    Avance Global del Día ({selected_date.strftime('%d/%m/%Y')})
                </span>
                <span class="trifecta-kpi-value" style="font-size:0.94rem; color:{bar_color};">
                    {weighted_daily_pct:g}%
                </span>
            </div>
            <div style="width:100%; height:8px; background:rgba(255,255,255,0.10); border-radius:999px; overflow:hidden; margin-bottom:8px;">
                <div style="width:{min(100.0, weighted_daily_pct):.1f}%; height:100%; background:{bar_color}; border-radius:999px; transition:width 0.25s ease;"></div>
            </div>
            <div style="display:flex; gap:10px; font-size:0.75rem; color:#94A3B8; flex-wrap:wrap;">
                <span><b style="color:#22C55E;">✔ {completed_today}</b> Completados</span>
                <span>·</span>
                <span><b style="color:#F59E0B;">⏳ {partial_today}</b> En progreso</span>
                <span>·</span>
                <span><b style="color:#94A3B8;">⬜ {pending_today}</b> Pendientes</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Renderizar cada tarjeta de hábito respetando display_order e is_pinned
    for idx, habit in enumerate(habits):
        h_id = str(habit["id"])
        h_name = str(habit.get("name", "Hábito"))
        h_icon = str(habit.get("icon", "⚡"))
        h_color = str(habit.get("color_hex", "#8B5CF6"))
        h_mtype = str(habit.get("metric_type", "BOOLEAN")).upper()
        h_unit = str(habit.get("unit_label", "check"))
        h_target = float(habit.get("daily_target_value") or 1.0)
        is_pinned = bool(habit.get("is_pinned", False))
        linked_goal_id = str(habit.get("linked_goal_id") or "")
        linked_goal = goals_by_id.get(linked_goal_id)

        analytics = analytics_map[h_id]
        pin_badge = (
            '<span style="font-size:0.70rem; background:rgba(245,158,11,0.18); color:#F59E0B; '
            'padding:2px 7px; border-radius:999px; margin-left:6px;">📌 Fijado</span>'
            if is_pinned
            else ""
        )
        goal_badge = (
            f'<div style="font-size:0.73rem; color:#94A3B8; margin-top:2px;">'
            f'🎯 Vinculado a: <b style="color:#F8FAFC;">{linked_goal.get("title")}</b></div>'
            if linked_goal
            else ""
        )

        # Insignia visual para los 3 estados: Pendiente (0%), En progreso (>0% y <100%), Completado (>=100%)
        st_color, st_icon, st_label = _get_status_visual_tokens(analytics.today_status)
        pct_badge_txt = _format_status_pct(analytics.today_progress_pct, analytics.today_status)
        status_pill_display = f"{st_icon} {st_label} ({pct_badge_txt})"

        with st.container(border=True):
            st.markdown(
                f"""
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px; gap:8px;">
                    <div>
                        <div style="display:flex; align-items:center; flex-wrap:wrap;">
                            <span style="
                                display:inline-flex; align-items:center; justify-content:center;
                                width:28px; height:28px; border-radius:8px;
                                background:{h_color}26; border:1px solid {h_color}66;
                                margin-right:8px; font-size:0.95rem;
                            ">{h_icon}</span>
                            <span style="font-weight:700; font-size:1.02rem; color:#F8FAFC;">{h_name}</span>
                            {pin_badge}
                        </div>
                        {goal_badge}
                    </div>
                    <span style="
                        font-size:0.72rem; font-weight:700; color:{st_color};
                        background:{st_color}1F; border:1px solid {st_color}4D;
                        padding:3px 9px; border-radius:999px; white-space:nowrap;
                    ">{status_pill_display}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Controles interactivos según tipo de métrica (BOOLEAN, NUMERIC, DURATION, RATING)
            if h_mtype == "BOOLEAN":
                btn_label = (
                    "✅ Completado hoy · 100% (Toque para desmarcar)"
                    if analytics.today_status == "COMPLETED"
                    else "⬜ Marcar como completado (1 toque)"
                )
                btn_type = "primary" if analytics.today_status != "COMPLETED" else "secondary"
                if st.button(
                    btn_label,
                    key=f"bool_toggle_{h_id}_{selected_date.isoformat()}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    new_val = 0.0 if analytics.today_status == "COMPLETED" else 1.0
                    upsert_habit_log(user_id, habit, new_val, log_date=selected_date)
                    st.rerun(scope="fragment")

            elif h_mtype in ("NUMERIC", "DURATION"):
                step = _smart_step_for_target(h_mtype, h_target)
                remaining = max(0.0, h_target - analytics.today_value)
                if analytics.today_status == "COMPLETED":
                    prog_bar_fill_color = "#22C55E"
                    sub_status_msg = f"🎉 Meta diaria cumplida ({_format_num(analytics.today_value)} / {_format_num(h_target)} {h_unit})"
                elif analytics.today_status == "PARTIAL":
                    prog_bar_fill_color = "#F59E0B"
                    sub_status_msg = f"⏳ En progreso: faltan {_format_num(remaining)} {h_unit} para el 100%"
                else:
                    prog_bar_fill_color = h_color
                    sub_status_msg = f"Meta objetivo: {_format_num(h_target)} {h_unit}"

                # Elemento visual de avance con barra de progreso e indicador porcentual exacto
                st.markdown(
                    f"""
                    <div style="
                        background:rgba(26, 34, 50, 0.65); border:1px solid #263044;
                        border-radius:12px; padding:9px 11px; margin-bottom:8px;
                    ">
                        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:5px;">
                            <span style="font-size:0.78rem; color:#94A3B8;">{sub_status_msg}</span>
                            <span class="trifecta-kpi-value" style="font-size:0.92rem; color:{prog_bar_fill_color};">
                                {_format_num(analytics.today_value)} / {_format_num(h_target)} {h_unit} · {pct_badge_txt}
                            </span>
                        </div>
                        <div style="width:100%; height:8px; background:rgba(255,255,255,0.10); border-radius:999px; overflow:hidden;">
                            <div style="
                                width:{analytics.today_bar_pct:.2f}%;
                                height:100%;
                                background:{prog_bar_fill_color};
                                border-radius:999px;
                                transition:width 0.25s ease;
                            "></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c_minus, c_plus, c_target, c_exact = st.columns(4)
                with c_minus:
                    if st.button(
                        f"➖ {_format_num(step)}",
                        key=f"num_dec_{h_id}_{selected_date.isoformat()}",
                        use_container_width=True,
                    ):
                        new_v = max(0.0, analytics.today_value - step)
                        upsert_habit_log(user_id, habit, new_v, log_date=selected_date)
                        st.rerun(scope="fragment")
                with c_plus:
                    if st.button(
                        f"➕ {_format_num(step)}",
                        key=f"num_inc_{h_id}_{selected_date.isoformat()}",
                        type="primary",
                        use_container_width=True,
                    ):
                        new_v = analytics.today_value + step
                        upsert_habit_log(user_id, habit, new_v, log_date=selected_date)
                        st.rerun(scope="fragment")
                with c_target:
                    if st.button(
                        "✔ 100%",
                        key=f"num_full_{h_id}_{selected_date.isoformat()}",
                        use_container_width=True,
                    ):
                        upsert_habit_log(user_id, habit, h_target, log_date=selected_date)
                        st.rerun(scope="fragment")
                with c_exact:
                    with st.popover("✏️ Valor", use_container_width=True):
                        exact_val = st.number_input(
                            f"Cantidad ({h_unit})",
                            min_value=0.0,
                            max_value=1000000.0,
                            value=float(analytics.today_value),
                            step=float(step),
                            key=f"num_exact_in_{h_id}_{selected_date.isoformat()}",
                        )
                        if st.button(
                            "Guardar",
                            key=f"num_exact_save_{h_id}_{selected_date.isoformat()}",
                            type="primary",
                            use_container_width=True,
                        ):
                            upsert_habit_log(user_id, habit, float(exact_val), log_date=selected_date)
                            st.rerun(scope="fragment")

                # Mostrar Promedio Diario Semanal (7d) y Sumatoria Acumulada Mensual
                _render_quantitative_summary_strip(
                    analytics=analytics,
                    unit_label=h_unit,
                    accent_color=h_color,
                    reference_date=selected_date,
                )

            elif h_mtype == "RATING":
                max_scale = int(h_target) if h_target >= 2 else 10
                current_rating = int(round(analytics.today_value)) if analytics.today_value >= 1 else max(1, max_scale // 2)
                col_sl, col_btn = st.columns([0.68, 0.32], vertical_alignment="bottom")
                with col_sl:
                    rating_val = st.slider(
                        f"Valoración del día (1 a {max_scale} {h_unit})",
                        min_value=1,
                        max_value=max_scale,
                        value=min(max_scale, max(1, current_rating)),
                        key=f"rating_sl_{h_id}_{selected_date.isoformat()}",
                    )
                with col_btn:
                    if st.button(
                        "💾 Registrar",
                        key=f"rating_save_{h_id}_{selected_date.isoformat()}",
                        type="primary",
                        use_container_width=True,
                    ):
                        upsert_habit_log(user_id, habit, float(rating_val), log_date=selected_date)
                        st.rerun(scope="fragment")

            # Controles de Reordenamiento del Dashboard (Modo Personalizar Vista)
            if reorder_mode:
                st.markdown(
                    f'<div style="font-size:0.74rem; color:#F59E0B; margin-top:6px; margin-bottom:4px;">'
                    f'🔀 Posición actual: <b>#{idx + 1}</b> (Orden DB: <code>{habit.get("display_order")}</code>)</div>',
                    unsafe_allow_html=True,
                )
                rc1, rc2, rc3 = st.columns(3)
                with rc1:
                    if st.button(
                        "⬆ Subir",
                        key=f"reord_up_{h_id}",
                        disabled=(idx == 0),
                        use_container_width=True,
                    ):
                        move_habit_order(user_id, h_id, "up")
                        st.rerun(scope="fragment")
                with rc2:
                    if st.button(
                        "⬇ Bajar",
                        key=f"reord_down_{h_id}",
                        disabled=(idx == len(habits) - 1),
                        use_container_width=True,
                    ):
                        move_habit_order(user_id, h_id, "down")
                        st.rerun(scope="fragment")
                with rc3:
                    pin_lbl = "📍 Desfijar" if is_pinned else "📌 Fijar arriba"
                    if st.button(pin_lbl, key=f"reord_pin_{h_id}", use_container_width=True):
                        toggle_habit_pin(user_id, h_id, is_pinned)
                        st.rerun(scope="fragment")

            # Heatmap de 90 días estilo GitHub / HabitKit
            _render_habit_heatmap_90d(analytics, h_color, h_unit)


# ============================================================================
# 4. PESTAÑA 2: METAS PERSONALES Y PLANES DE DESARROLLO (goal_milestones)
# ============================================================================

def _render_goals_and_plans_tab(user_id: str) -> None:
    """Renderiza la jerarquía de 3 niveles: Meta Personal -> Plan de Hitos -> Hábitos Vinculados."""
    access_token = st.session_state.get("access_token") or ""
    goals = fetch_personal_goals(user_id, access_token)
    milestones = fetch_goal_milestones(user_id, access_token)
    habits = fetch_habits(user_id, access_token, include_archived=False)
    logs = fetch_habit_logs(user_id, access_token, days_back=45)

    col_btn, col_info = st.columns([0.55, 0.45], vertical_alignment="center")
    with col_btn:
        if st.button("➕ Nueva Meta / Propósito", type="primary", use_container_width=True, key="btn_open_new_goal"):
            _open_create_goal_dialog(user_id, habits)
    with col_info:
        st.caption(f"🎯 **{len(goals)}** metas registradas")

    if not goals:
        with st.container(border=True):
            st.markdown(
                """
                <div style="text-align:center; padding:18px 8px;">
                    <div style="font-size:2rem; margin-bottom:6px;">🎯</div>
                    <div style="font-weight:700; font-size:1.02rem; color:#F8FAFC;">
                        Define tus Metas Anuales y Planes de Desarrollo
                    </div>
                    <div style="font-size:0.84rem; color:#94A3B8; margin-top:4px;">
                        Desglosa cada propósito en hitos verificables y vincula los hábitos diarios que lo respaldan.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    ms_by_goal: Dict[str, List[Dict[str, Any]]] = {}
    for m in milestones:
        gid = str(m.get("goal_id", ""))
        ms_by_goal.setdefault(gid, []).append(m)

    habits_by_goal: Dict[str, List[Dict[str, Any]]] = {}
    for h in habits:
        gid = str(h.get("linked_goal_id") or "")
        if gid:
            habits_by_goal.setdefault(gid, []).append(h)

    for goal in goals:
        gid = str(goal["id"])
        g_title = str(goal.get("title", "Meta Personal"))
        g_area = str(goal.get("life_area", "Desarrollo Personal"))
        g_desc = str(goal.get("description") or "")
        g_target_str = str(goal.get("target_date") or "")[:10]
        try:
            days_left = (date.fromisoformat(g_target_str) - date.today()).days
            days_badge = f"⏳ {days_left} días restantes ({g_target_str})" if days_left >= 0 else f"📅 Venció hace {abs(days_left)}d"
        except Exception:
            days_badge = f"📅 Meta: {g_target_str}"

        g_milestones = ms_by_goal.get(gid, [])
        g_habits = habits_by_goal.get(gid, [])

        habit_adherences: List[Tuple[Dict[str, Any], HabitAnalytics]] = []
        for h in g_habits:
            ha = calculate_habit_analytics(h, logs)
            habit_adherences.append((h, ha))

        live_pct = calculate_goal_progress_pct(
            g_milestones,
            [ha.adherence_30d_pct for _, ha in habit_adherences],
        )
        next_milestone = next((m for m in g_milestones if not m.get("is_completed")), None)

        with st.container(border=True):
            bar_color = "#22C55E" if live_pct >= 100.0 else PALETTE["accent_habits"]
            st.markdown(
                f"""
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <span class="trifecta-pillar-pill" style="background:#8B5CF626; color:#8B5CF6; border:1px solid #8B5CF655;">
                        {g_area}
                    </span>
                    <span style="font-size:0.75rem; color:#94A3B8;">{days_badge}</span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:4px;">
                    <div style="font-size:1.10rem; font-weight:800; color:#F8FAFC;">{g_title}</div>
                    <div class="trifecta-kpi-value" style="font-size:1.15rem; color:{bar_color};">{live_pct:.0f}%</div>
                </div>
                <div style="width:100%; height:8px; background:rgba(255,255,255,0.10); border-radius:999px; margin:8px 0; overflow:hidden;">
                    <div style="width:{min(100.0, live_pct):.1f}%; height:100%; background:{bar_color}; border-radius:999px;"></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if g_desc:
                st.caption(g_desc)

            if next_milestone:
                st.markdown(
                    f"""
                    <div style="
                        background:rgba(139,92,246,0.12); border-left:3px solid #8B5CF6;
                        padding:7px 10px; border-radius:8px; font-size:0.80rem; color:#F8FAFC; margin-bottom:8px;
                    ">
                        👉 <b>Siguiente paso en tu hoja de ruta:</b> {next_milestone.get('title')}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("###### 🗺️ Plan de Desarrollo (Hitos Verificables)")
            if not g_milestones:
                st.caption("Aún no has agregado hitos a esta meta.")
            else:
                for m in g_milestones:
                    m_id = str(m["id"])
                    m_done = bool(m.get("is_completed", False))
                    m_step = int(m.get("step_order") or 1)
                    m_title = str(m.get("title", ""))
                    c_chk, c_del = st.columns([0.85, 0.15], vertical_alignment="center")
                    with c_chk:
                        lbl = f"~~Paso {m_step}: {m_title}~~ ✅" if m_done else f"Paso {m_step}: {m_title}"
                        toggled = st.checkbox(
                            lbl,
                            value=m_done,
                            key=f"ms_chk_{m_id}",
                        )
                        if toggled != m_done:
                            toggle_goal_milestone(user_id, m_id, gid, toggled)
                            st.rerun()
                    with c_del:
                        if st.button("🗑️", key=f"ms_del_{m_id}", help="Eliminar hito"):
                            delete_goal_milestone(user_id, m_id, gid)
                            st.rerun()

            st.markdown("###### 🔗 Hábitos Diarios que Impulsan esta Meta")
            if not habit_adherences:
                st.caption("Sin hábitos vinculados. Puedes enlazar cualquier hábito desde «Editar Hábito».")
            else:
                for h_obj, h_ana in habit_adherences:
                    st.markdown(
                        f"""
                        <div style="
                            display:flex; justify-content:space-between; align-items:center;
                            background:#1A2232; border:1px solid #263044; border-radius:10px;
                            padding:7px 11px; margin-bottom:6px; font-size:0.82rem;
                        ">
                            <span>{h_obj.get('icon', '⚡')} <b>{h_obj.get('name')}</b></span>
                            <span style="color:#10B981; font-family:'JetBrains Mono', monospace; font-weight:700;">
                                🔥 {h_ana.current_streak}d · {h_ana.adherence_30d_pct:.0f}% adherencia (30d)
                            </span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            with st.expander("➕ Agregar Hito o Administrar Meta"):
                col_new_m, col_add_m = st.columns([0.72, 0.28], vertical_alignment="bottom")
                with col_new_m:
                    new_ms_title = st.text_input(
                        "Nuevo Hito del Plan",
                        placeholder="Ej. Aprobar examen simulacro",
                        key=f"in_add_ms_{gid}",
                    )
                with col_add_m:
                    if st.button("Añadir", key=f"btn_add_ms_{gid}", type="primary", use_container_width=True):
                        ok, msg = add_goal_milestone(user_id, gid, new_ms_title)
                        if ok:
                            st.toast(msg, icon="🗺️")
                            st.rerun()
                        else:
                            st.warning(msg)

                st.divider()
                if st.button("🗑️ Eliminar Meta Personal", key=f"btn_del_goal_{gid}", use_container_width=True):
                    delete_personal_goal(user_id, gid)
                    st.rerun()


# ============================================================================
# 5. PESTAÑA 3: GESTOR DE TRACKERS PERSONALIZADOS (EDICIÓN Y ARCHIVO)
# ============================================================================

def _render_trackers_manager_tab(user_id: str) -> None:
    """Permite inspeccionar, editar, archivar/restaurar o eliminar todos los trackers del usuario."""
    access_token = st.session_state.get("access_token") or ""
    all_habits = fetch_habits(user_id, access_token, include_archived=True)
    logs = fetch_habit_logs(user_id, access_token, days_back=120)
    goals = fetch_personal_goals(user_id, access_token)

    col_new, col_count = st.columns([0.55, 0.45], vertical_alignment="center")
    with col_new:
        if st.button("➕ Crear Nuevo Tracker", type="primary", use_container_width=True, key="mgr_btn_new_habit"):
            _open_create_habit_dialog(user_id, goals)
    with col_count:
        st.caption(f"⚙️ **{len(all_habits)}** trackers configurados")

    if not all_habits:
        st.info("Aún no tienes trackers registrados. Crea el primero con el botón superior.")
        return

    for h in all_habits:
        hid = str(h["id"])
        is_arch = bool(h.get("is_archived", False))
        arch_tag = " · 📦 Archivado" if is_arch else ""
        mtype = str(h.get("metric_type", "BOOLEAN")).upper()
        unit_lbl = str(h.get("unit_label", "check"))
        ana = calculate_habit_analytics(h, logs)

        with st.container(border=True):
            c_info, c_edit, c_del = st.columns([0.62, 0.22, 0.16], vertical_alignment="center")
            with c_info:
                st.markdown(
                    f"**{h.get('icon', '⚡')} {h.get('name')}**{arch_tag}  \n"
                    f"<span style='font-size:0.78rem; color:#94A3B8;'>"
                    f"Tipo: <code>{mtype}</code> · Meta: "
                    f"<b>{_format_num(float(h.get('daily_target_value') or 1))} {unit_lbl}</b> · "
                    f"Orden: <code>#{h.get('display_order')}</code></span>",
                    unsafe_allow_html=True,
                )
            with c_edit:
                if st.button("✏️ Editar", key=f"mgr_edit_{hid}", use_container_width=True):
                    _open_edit_habit_dialog(user_id, h, goals)
            with c_del:
                if st.button("🗑️", key=f"mgr_del_{hid}", help="Eliminar definitivamente", use_container_width=True):
                    delete_habit(user_id, hid)
                    st.rerun()

            if mtype in ("NUMERIC", "DURATION"):
                _render_quantitative_summary_strip(
                    analytics=ana,
                    unit_label=unit_lbl,
                    accent_color=str(h.get("color_hex", "#8B5CF6")),
                    reference_date=date.today(),
                )


# ============================================================================
# 6. PUNTO DE ENTRADA DEL MÓDULO 3 (habits_view.py)
# ============================================================================

def render_habits_view() -> None:
    """Renderiza el Módulo 3 completo: Hábitos Editables, Dashboard Reordenable, Heatmaps y Metas."""
    user_id = get_current_user_id()
    if not user_id:
        st.warning("Inicia sesión para gestionar tus hábitos y metas.")
        return

    render_pillar_header(
        title="Hábitos y Metas",
        subtitle="Trackers personalizables, progreso parcial, promedios temporales y planes de desarrollo",
        accent_hex=PALETTE["accent_habits"],
        badge_text="🎯 Pilar 3 · Habits & OKRs",
    )

    tab_today, tab_goals, tab_manager = st.tabs(
        ["⚡ Hoy (Dashboard)", "🎯 Metas y Planes", "⚙️ Gestor de Trackers"]
    )

    with tab_today:
        access_token = st.session_state.get("access_token") or ""
        goals = fetch_personal_goals(user_id, access_token)

        col_add, col_reord = st.columns([0.52, 0.48], vertical_alignment="center")
        with col_add:
            if st.button("➕ Nuevo Hábito", type="primary", use_container_width=True, key="today_btn_new_habit"):
                _open_create_habit_dialog(user_id, goals)
        with col_reord:
            reorder_mode = st.toggle("🔀 Reordenar Vista", value=False, key="today_toggle_reorder_mode")

        with st.expander("📅 Cambiar fecha de captura (Por defecto: Hoy)", expanded=False):
            selected_date = st.date_input(
                "Fecha de registro",
                value=date.today(),
                max_value=date.today(),
                key="habits_selected_log_date",
            )

        _render_daily_habits_fragment(
            user_id=user_id,
            selected_date=selected_date,
            reorder_mode=reorder_mode,
        )

    with tab_goals:
        _render_goals_and_plans_tab(user_id=user_id)

    with tab_manager:
        _render_trackers_manager_tab(user_id=user_id)
