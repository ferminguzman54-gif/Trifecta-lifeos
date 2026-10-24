"""
Command Center Central / Vista 'Hoy' (Sprint 5):
- Tarjeta Hero con el Trifecta Score diario (anillo SVG + sub-scores) y racha actual de consistencia.
- Barra táctil de Acción Rápida (1-Tap Quick Action Dock) con modales para registrar hábito,
  registrar gasto rápido o iniciar la rutina sugerida en un solo toque.
- Resumen dinámico del día:
  1. Hábitos pendientes y barra de avance global de la jornada.
  2. Próxima rutina sugerida según secuencia Push/Pull/Legs y sobrecarga progresiva recomendada.
  3. Resumen financiero inmediato: saldo consolidado, gasto del día y alerta de próximo vencimiento TDC.
- Analítica Cruzada y Gráfica Multitemporal de consistencia semanal y mensual (Línea de tendencia + Heatmap).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import plotly.graph_objects as go
import streamlit as st

from src.auth.session_manager import get_current_user_id
from src.components.chart_builders import apply_mobile_dark_layout, render_mobile_plotly
from src.components.kpi_cards import render_kpi_card
from src.config.theme import PALETTE
from src.models.hub_models import DailyLifeSnapshotModel, TrifectaWeights
from src.services.card_advisor_engine import (
    create_finance_transaction,
    fetch_finance_accounts,
    fetch_finance_categories,
    fetch_finance_transactions,
)
from src.services.habit_streak_engine import (
    calculate_habit_analytics,
    fetch_habit_logs,
    fetch_habits,
    upsert_habit_log,
)
from src.services.progression_engine import (
    fetch_exercises_catalog,
    fetch_workout_routine_items,
    fetch_workout_routines,
    fetch_workout_sessions,
    fetch_workout_sets,
)
from src.services.trifecta_score_engine import (
    evaluate_hub_daily_pulse,
    fetch_daily_snapshots,
    upsert_daily_snapshot,
)


# =====================================================================
# MODALES DE ACCIÓN RÁPIDA DE 1 TOQUE (@st.dialog)
# =====================================================================


@st.dialog("⚡ Registro Rápido de Hábito")
def _open_quick_habit_dialog(
    user_id: str,
    habits: List[Dict[str, Any]],
    habit_logs: List[Dict[str, Any]],
) -> None:
    """Modal táctil para registrar avance parcial o completar un hábito desde el Command Center."""
    if not habits:
        st.info("Aún no tienes hábitos activos. Ve al Pilar 3 (Hábitos) para crear o inicializar tu catálogo.")
        return

    habit_map = {
        str(h["id"]): f"{h.get('icon', '⚡')} {h.get('name')} (Meta: {float(h.get('daily_target_value') or 1):g} {h.get('unit_label', 'check')})"
        for h in habits
    }
    selected_hid = st.selectbox(
        "Selecciona el hábito a registrar hoy",
        options=list(habit_map.keys()),
        format_func=lambda k: habit_map[k],
        key="hub_dlg_habit_select",
    )
    chosen_h = next((h for h in habits if str(h["id"]) == selected_hid), habits[0])
    ana = calculate_habit_analytics(chosen_h, habit_logs)

    mtype = str(chosen_h.get("metric_type", "BOOLEAN")).upper()
    target_val = max(0.1, float(chosen_h.get("daily_target_value") or 1.0))
    unit_lbl = str(chosen_h.get("unit_label", "check"))

    if mtype == "BOOLEAN":
        new_val = target_val
        st.caption(f"Estado actual hoy: **{ana.today_status}**")
    else:
        default_v = float(ana.today_value) if ana.today_value > 0 else target_val
        new_val = st.number_input(
            f"Valor alcanzado hoy ({unit_lbl} · Meta: {target_val:g})",
            min_value=0.0,
            value=default_v,
            step=1.0 if target_val >= 10 else 0.5,
            key="hub_dlg_habit_val",
        )
        pct_preview = min(100.0, (float(new_val) / target_val) * 100.0)
        st.progress(pct_preview / 100.0, text=f"Cumplimiento proyectado: {pct_preview:.1f}%")

    notes = st.text_input("Nota breve (opcional)", key="hub_dlg_habit_note")

    if st.button("✅ Guardar Registro de Hoy", type="primary", use_container_width=True, key="hub_dlg_habit_save"):
        upsert_habit_log(
            user_id=user_id,
            habit=chosen_h,
            recorded_value=float(new_val),
            log_date=date.today(),
            notes=notes,
        )
        st.toast(f"Hábito «{chosen_h.get('name')}» actualizado.", icon="🎯")
        st.rerun()


@st.dialog("💸 Registro Rápido de Gasto / Ingreso")
def _open_quick_expense_dialog(
    user_id: str,
    currency: str,
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
) -> None:
    """Modal exprés de 1 toque para registrar un gasto o ingreso sin salir del Hub."""
    if not accounts:
        st.warning("Primero crea una cuenta o genera la Billetera Demo en el Pilar 2 (Finanzas).")
        if st.button("Ir a Finanzas", use_container_width=True):
            st.session_state["active_pillar"] = "finance"
            st.rerun()
        return

    tx_type = (
        st.segmented_control(
            "Tipo",
            options=["expense", "income"],
            default="expense",
            format_func=lambda t: "💸 Gasto Rápido" if t == "expense" else "💰 Ingreso Rápido",
            key="hub_dlg_tx_type",
        )
        or "expense"
    )

    acc_map = {
        str(a["id"]): f"{a['name']} (${float(a.get('current_balance') or 0):,.0f})"
        for a in accounts
    }
    account_id = st.selectbox(
        "Cuenta o Tarjeta",
        options=list(acc_map.keys()),
        format_func=lambda k: acc_map[k],
        key="hub_dlg_tx_acc",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        amount = st.number_input(
            f"Monto ({currency})",
            min_value=1.0,
            value=180.0,
            step=50.0,
            format="%.2f",
            key="hub_dlg_tx_amt",
        )
    with col_b:
        filtered_cats = [c for c in categories if str(c.get("kind", "expense")) == tx_type] or categories
        cat_map = {str(c["id"]): f"{c.get('icon', '💸')} {c.get('name')}" for c in filtered_cats}
        category_id = (
            st.selectbox(
                "Categoría",
                options=list(cat_map.keys()),
                format_func=lambda k: cat_map[k],
                key="hub_dlg_tx_cat",
            )
            if cat_map
            else None
        )

    concept = st.text_input(
        "Concepto o comercio",
        placeholder="Ej. Café, Supermercado, Uber, Comida...",
        key="hub_dlg_tx_concept",
    )

    if st.button("💾 Registrar Ahora", type="primary", use_container_width=True, key="hub_dlg_tx_save"):
        ok, msg = create_finance_transaction(
            user_id=user_id,
            account_id=account_id,
            tx_type=tx_type,
            amount=float(amount),
            merchant_or_concept=concept.strip() or ("Gasto rápido" if tx_type == "expense" else "Ingreso"),
            tx_date=date.today(),
            category_id=category_id,
        )
        if ok:
            st.toast(msg, icon="💳")
            st.rerun()
        else:
            st.error(msg)


# =====================================================================
# VISTA PRINCIPAL DEL COMMAND CENTER ("HOY" — SPRINT 5)
# =====================================================================


def render_hub_view() -> None:
    """Renderiza el Command Center Central con el Trifecta Score, Quick Actions, Resumen Dinámico y Analítica Cruzada."""
    profile = st.session_state.get("user_profile") or {}
    full_name = profile.get("full_name", "Usuario Trifecta")
    alias = (profile.get("alias") or "").strip()
    first_name = alias if alias else str(full_name).split(" ")[0]
    currency = profile.get("preferred_currency", "MXN")
    weight_unit = profile.get("weight_unit", "kg")
    user_id = get_current_user_id() or ""
    access_token = st.session_state.get("access_token") or ""

    if not user_id or not access_token:
        st.warning("Inicia sesión para cargar tu Command Center.")
        return

    # Inicializar pesos configurables en session_state desde el perfil del usuario (por defecto: 40/35/25)
    if "trifecta_weights" not in st.session_state:
        st.session_state["trifecta_weights"] = {
            "habits": int(round(float(profile.get("weight_habits") or 40.0))),
            "workout": int(round(float(profile.get("weight_workouts") or 35.0))),
            "finance": int(round(float(profile.get("weight_finances") or 25.0))),
        }
    w_state = st.session_state["trifecta_weights"]
    weights_model = TrifectaWeights(
        habits_weight=float(w_state["habits"]) / 100.0,
        workout_weight=float(w_state["workout"]) / 100.0,
        finance_weight=float(w_state["finance"]) / 100.0,
    ).normalized()

    # Cargar datos cacheados de los 3 pilares
    habits = fetch_habits(user_id, access_token, include_archived=False)
    habit_logs = fetch_habit_logs(user_id, access_token, days_back=45)

    routines = fetch_workout_routines(user_id, access_token)
    routine_items = fetch_workout_routine_items(user_id, access_token)
    workout_sessions = fetch_workout_sessions(user_id, access_token, days_back=45)
    workout_sets = fetch_workout_sets(user_id, access_token, days_back=45)
    exercises = fetch_exercises_catalog(user_id, access_token)

    accounts = fetch_finance_accounts(user_id, access_token)
    categories = fetch_finance_categories(user_id, access_token)
    transactions = fetch_finance_transactions(user_id, access_token, days_back=60)
    saved_snapshots = fetch_daily_snapshots(user_id, access_token, days_back=60)

    pulse, consistency_data = evaluate_hub_daily_pulse(
        user_id=user_id,
        habits=habits,
        habit_logs=habit_logs,
        routines=routines,
        routine_items=routine_items,
        workout_sessions=workout_sessions,
        workout_sets=workout_sets,
        exercises=exercises,
        accounts=accounts,
        categories=categories,
        transactions=transactions,
        saved_snapshots=saved_snapshots,
        weights=weights_model,
        target_date=date.today(),
    )

    # Auto-sincronizar el snapshot del día una vez por sesión (silencioso si la tabla aún no se migra)
    today_iso = date.today().isoformat()
    if st.session_state.get("_last_auto_snapshot_date") != today_iso:
        snap_obj = DailyLifeSnapshotModel(
            user_id=user_id,
            date=date.today(),
            habit_score=pulse.habit_score,
            workout_score=pulse.workout_score,
            finance_score=pulse.finance_score,
            workout_completed=pulse.workout_completed,
            budget_status=pulse.budget_status,
            trifecta_score=pulse.trifecta_score,
            metadata={
                "habits_completed": pulse.habits_completed_today,
                "habits_total": pulse.habits_total_active,
                "next_ppl_split": pulse.workout_suggestion.next_ppl_split,
                "today_expenses": pulse.today_expenses_amount,
            },
        )
        upsert_daily_snapshot(user_id, snap_obj)
        st.session_state["_last_auto_snapshot_date"] = today_iso

    # ── 1. TARJETA PRINCIPAL HERO: TRIFECTA SCORE DIARIO Y RACHA DE CONSISTENCIA ──
    score_val = pulse.trifecta_score
    ring_col = pulse.tier_color
    dash_array = 251.2  # 2 * pi * 40
    dash_offset = dash_array * (1.0 - min(100.0, max(0.0, score_val)) / 100.0)

    st.markdown(
        f"""
        <div class="trifecta-hero-card">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
                <div>
                    <span class="trifecta-pillar-pill" style="background:{ring_col}24; color:{ring_col}; border:1px solid {ring_col}66;">
                        {pulse.tier_label}
                    </span>
                    <div style="font-size:1.32rem; font-weight:800; color:#F8FAFC; margin-top:6px;">
                        Hola, {first_name} 👋
                    </div>
                    <div style="font-size:0.78rem; color:#94A3B8;">
                        Pulso integral · {date.today().strftime('%d %b %Y')}
                    </div>
                </div>
                <div style="text-align:right; background:rgba(10,13,20,0.65); border:1px solid #263044; border-radius:12px; padding:8px 12px;">
                    <div style="font-size:0.68rem; color:#94A3B8; text-transform:uppercase; letter-spacing:0.05em;">Racha Consistencia</div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size:1.15rem; font-weight:800; color:#F59E0B;">
                        🔥 {pulse.consistency_streak_days} día(s)
                    </div>
                    <div style="font-size:0.68rem; color:#64748B;">Récord: {pulse.best_consistency_streak_days}d</div>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: 112px 1fr; gap:14px; align-items:center;">
                <div style="position:relative; width:104px; height:104px; margin:0 auto;">
                    <svg width="104" height="104" viewBox="0 0 100 100">
                        <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="9"/>
                        <circle cx="50" cy="50" r="40" fill="none" stroke="{ring_col}" stroke-width="9"
                                stroke-linecap="round"
                                stroke-dasharray="{dash_array:.1f}"
                                stroke-dashoffset="{dash_offset:.1f}"
                                transform="rotate(-90 50 50)"/>
                    </svg>
                    <div style="position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                        <span style="font-family:'JetBrains Mono', monospace; font-size:1.38rem; font-weight:800; color:#F8FAFC; line-height:1;">
                            {score_val:.0f}
                        </span>
                        <span style="font-size:0.62rem; color:#94A3B8; text-transform:uppercase; margin-top:2px;">
                            Trifecta
                        </span>
                    </div>
                </div>
                <div style="display:flex; flex-direction:column; gap:7px;">
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:2px;">
                            <span style="color:#C4B5FD; font-weight:600;">🎯 Hábitos ({int(round(weights_model.habits_weight*100))}%)</span>
                            <span style="font-family:'JetBrains Mono', monospace; color:#F8FAFC; font-weight:700;">{pulse.habit_score:.0f}/100</span>
                        </div>
                        <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden;">
                            <div style="width:{min(100.0, pulse.habit_score):.1f}%; height:100%; background:#8B5CF6;"></div>
                        </div>
                    </div>
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:2px;">
                            <span style="color:#FDBA74; font-weight:600;">🏋️ Entrenamiento ({int(round(weights_model.workout_weight*100))}%)</span>
                            <span style="font-family:'JetBrains Mono', monospace; color:#F8FAFC; font-weight:700;">{pulse.workout_score:.0f}/100</span>
                        </div>
                        <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden;">
                            <div style="width:{min(100.0, pulse.workout_score):.1f}%; height:100%; background:#FF5500;"></div>
                        </div>
                    </div>
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:2px;">
                            <span style="color:#6EE7B7; font-weight:600;">💳 Finanzas ({int(round(weights_model.finance_weight*100))}%)</span>
                            <span style="font-family:'JetBrains Mono', monospace; color:#F8FAFC; font-weight:700;">{pulse.finance_score:.0f}/100</span>
                        </div>
                        <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden;">
                            <div style="width:{min(100.0, pulse.finance_score):.1f}%; height:100%; background:#10B981;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 2. WIDGET DE ACCIÓN RÁPIDA EN 1 TOQUE (QUICK ACTION DOCK) ──
    st.markdown(
        "<div style='font-size:0.74rem; font-weight:700; color:#94A3B8; text-transform:uppercase; "
        "letter-spacing:0.06em; margin:2px 0 6px 2px;'>⚡ Acción Rápida en 1 Toque</div>",
        unsafe_allow_html=True,
    )
    qa_col1, qa_col2, qa_col3 = st.columns(3)
    with qa_col1:
        if st.button("✅ + Hábito", type="primary", use_container_width=True, key="hub_qa_habit"):
            _open_quick_habit_dialog(user_id, habits, habit_logs)
    with qa_col2:
        if st.button("💸 + Gasto", use_container_width=True, key="hub_qa_expense"):
            _open_quick_expense_dialog(user_id, currency, accounts, categories)
    with qa_col3:
        if st.button("🏋️ Entrenar", use_container_width=True, key="hub_qa_workout"):
            if pulse.workout_suggestion.recommended_routine_id:
                st.session_state["selected_routine_id"] = pulse.workout_suggestion.recommended_routine_id
            st.session_state["active_pillar"] = "workout"
            st.rerun()

    # Configuración del balance de pesos y botón de persistencia manual de Snapshot
    with st.expander("⚖️ Personalizar ponderación del Trifecta Score & Guardar Snapshot"):
        wc1, wc2, wc3 = st.columns(3)
        with wc1:
            w_h = st.slider("🎯 Hábitos (%)", 10, 80, int(w_state["habits"]), step=5, key="hub_w_hab")
        with wc2:
            w_w = st.slider("🏋️ Entreno (%)", 10, 80, int(w_state["workout"]), step=5, key="hub_w_wrk")
        with wc3:
            w_f = st.slider("💳 Finanzas (%)", 10, 80, int(w_state["finance"]), step=5, key="hub_w_fin")

        act_c1, act_c2 = st.columns(2)
        with act_c1:
            if st.button("Aplicar Balance de Pesos", use_container_width=True, key="hub_apply_weights"):
                st.session_state["trifecta_weights"] = {"habits": w_h, "workout": w_w, "finance": w_f}
                st.rerun()
        with act_c2:
            if st.button("💾 Sincronizar Snapshot Hoy", type="primary", use_container_width=True, key="hub_sync_snap"):
                snap_manual = DailyLifeSnapshotModel(
                    user_id=user_id,
                    date=date.today(),
                    habit_score=pulse.habit_score,
                    workout_score=pulse.workout_score,
                    finance_score=pulse.finance_score,
                    workout_completed=pulse.workout_completed,
                    budget_status=pulse.budget_status,
                    trifecta_score=pulse.trifecta_score,
                    metadata={
                        "habits_completed": pulse.habits_completed_today,
                        "habits_total": pulse.habits_total_active,
                        "next_ppl_split": pulse.workout_suggestion.next_ppl_split,
                        "today_expenses": pulse.today_expenses_amount,
                    },
                )
                ok, msg = upsert_daily_snapshot(user_id, snap_manual)
                if ok:
                    st.toast(msg, icon="💾")
                else:
                    st.info(msg)

    # ── 3. RESUMEN DINÁMICO DEL DÍA (LOS 3 PILARES EN TIEMPO REAL) ──

    # 3.1 Bloque Hábitos Pendientes y Barra de Avance Global de la Jornada
    with st.container(border=True):
        analytics_map = {str(h["id"]): calculate_habit_analytics(h, habit_logs) for h in habits}
        st.markdown(
            f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
<span class="trifecta-pillar-pill" style="background:#8B5CF626; color:#A78BFA; border:1px solid #8B5CF655;">
🎯 Hábitos de la Jornada
</span>
<span class="trifecta-kpi-value" style="font-size:0.80rem; color:#F8FAFC;">
{pulse.habits_completed_today}/{pulse.habits_total_active} completados · {pulse.habits_partial_today} parciales ({pulse.habit_score:.0f}%)
</span>
</div>
<div style="width:100%; height:8px; background:rgba(255,255,255,0.08); border-radius:999px; margin-bottom:10px; overflow:hidden;">
<div style="width:{min(100.0, pulse.habit_score):.1f}%; height:100%; background:linear-gradient(90deg, #8B5CF6, #10B981); border-radius:999px;"></div>
</div>
""",
            unsafe_allow_html=True,
        )

        pending_habits = [
            h for h in habits if analytics_map[str(h["id"])].today_status != "COMPLETED"
        ]
        if pending_habits:
            st.caption("Pendientes o en progreso hoy (toca para completar al 100%):")
            for ph in pending_habits[:4]:
                ph_id = str(ph["id"])
                ph_ana = analytics_map[ph_id]
                target_v = float(ph.get("daily_target_value") or 1.0)
                unit_lbl = str(ph.get("unit_label", "check"))
                mtype = str(ph.get("metric_type", "BOOLEAN")).upper()
                if mtype == "BOOLEAN":
                    btn_txt = f"⬜ {ph.get('icon', '⚡')} {ph.get('name')}"
                elif ph_ana.today_status == "PARTIAL":
                    btn_txt = (
                        f"⏳ {ph.get('icon', '⚡')} {ph.get('name')} "
                        f"({ph_ana.today_value:g}/{target_v:g} {unit_lbl} · {ph_ana.today_progress_pct:.0f}%)"
                    )
                else:
                    btn_txt = f"⬜ {ph.get('icon', '⚡')} {ph.get('name')} (Meta: {target_v:g} {unit_lbl})"

                if st.button(btn_txt, key=f"hub_quick_check_{ph_id}", use_container_width=True):
                    upsert_habit_log(user_id, ph, target_v, log_date=date.today())
                    st.rerun()
        elif habits:
            st.success("🎉 ¡Todos los hábitos activos del día están al 100%!")
        else:
            st.caption("Aún no tienes hábitos configurados.")

        if st.button("🎯 Abrir Dashboard de Hábitos y Metas", use_container_width=True, key="hub_go_habits"):
            st.session_state["active_pillar"] = "habits"
            st.rerun()

    # 3.2 Bloque Próxima Rutina Sugerida (Secuencia Push/Pull/Legs + Sobrecarga Progresiva)
    with st.container(border=True):
        w_sugg = pulse.workout_suggestion
        status_badge = (
            "✅ ENTRENO COMPLETADO HOY"
            if pulse.workout_completed
            else f"🔄 SUGERENCIA HOY: {w_sugg.next_ppl_split}"
        )
        routine_subtitle = (
            f"Rutina vinculada: <b>{w_sugg.recommended_routine_name}</b>"
            if w_sugg.recommended_routine_name
            else w_sugg.split_subtitle
        )
        last_info = (
            f"Última sesión: {w_sugg.last_ppl_split} hace {w_sugg.days_since_last_workout}d · {w_sugg.workouts_last_7d} ses. en 7d"
            if w_sugg.last_session_date is not None
            else "Sin sesiones recientes registradas"
        )

        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:4px;">
                <span class="trifecta-pillar-pill" style="background:#FF550026; color:#FF5500; border:1px solid #FF550055;">
                    🏋️ Secuencia Push / Pull / Legs
                </span>
                <span style="font-size:0.74rem; color:#FDBA74; font-weight:700;">{status_badge}</span>
            </div>
            <div style="background:#1A2232; border-left:4px solid #FF5500; border-radius:10px; padding:10px 12px; margin-bottom:10px;">
                <div style="font-size:0.98rem; font-weight:800; color:#F8FAFC;">{w_sugg.split_title}</div>
                <div style="font-size:0.78rem; color:#CBD5E1; margin-top:2px;">{routine_subtitle}</div>
                <div style="font-size:0.72rem; color:#94A3B8; margin-top:4px;">⏱️ {last_info}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if w_sugg.overload_targets:
            st.caption(f"🎯 Prescripción de Sobrecarga Progresiva para hoy ({weight_unit}):")
            for target in w_sugg.overload_targets:
                b_col = str(target.get("badge_color") or "#10B981")
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; align-items:center;
                                background:#121722; border:1px solid #263044; border-radius:10px;
                                padding:8px 11px; margin-bottom:6px;">
                        <div>
                            <div style="font-size:0.84rem; font-weight:700; color:#F8FAFC;">
                                {target['exercise_name']}
                            </div>
                            <div style="font-size:0.71rem; color:{b_col}; font-weight:600;">
                                {target['badge_text']}
                            </div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-family:'JetBrains Mono', monospace; font-size:0.92rem; font-weight:800; color:#F8FAFC;">
                                {float(target['suggested_weight_kg']):g} {weight_unit} × {int(target['suggested_reps'])} reps
                            </div>
                            <div style="font-size:0.68rem; color:#64748B;">1RM est: {float(target['estimated_1rm_kg']):.1f} {weight_unit}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if st.button("⚡ Ir a Registro en Vivo de Entrenamiento", use_container_width=True, key="hub_go_workout"):
            if w_sugg.recommended_routine_id:
                st.session_state["selected_routine_id"] = w_sugg.recommended_routine_id
            st.session_state["active_pillar"] = "workout"
            st.rerun()

    # 3.3 Bloque Resumen Financiero Inmediato
    with st.container(border=True):
        b_status_map = {
            "OPTIMAL": ("✅ Presupuesto Saludable", "#10B981"),
            "WARNING": ("⚠️ Presupuesto en Alerta (>85%)", "#F59E0B"),
            "CRITICAL": ("🚨 Presupuesto Crítico (>100%)", "#EF4444"),
        }
        b_badge_txt, b_badge_col = b_status_map.get(pulse.budget_status, ("✅ Saludable", "#10B981"))

        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:4px;">
                <span class="trifecta-pillar-pill" style="background:#10B98126; color:#10B981; border:1px solid #10B98155;">
                    💳 Pulso Financiero Inmediato
                </span>
                <span style="font-size:0.74rem; color:{b_badge_col}; font-weight:700;">{b_badge_txt}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
render_kpi_card(
label="Saldo Consolidado",
value=f"${pulse.liquid_balance:,.0f}",
delta_text=f"Deuda TDC: ${pulse.cc_debt:,.0f}",
delta_positive=(pulse.liquid_balance >= pulse.cc_debt),
accent_color=PALETTE["accent_finance"],
            )
        with col_f2:
render_kpi_card(
label="Gasto de Hoy",
value=f"${pulse.today_expenses_amount:,.0f}",
delta_text=f"Moneda: {currency}",
delta_positive=(pulse.today_expenses_amount == 0),
accent_color="#38BDF8" if pulse.today_expenses_amount == 0 else "#F59E0B",
            )
        with col_f3:
render_kpi_card(
label="Presupuesto Libre",
value=f"${pulse.budget_remaining_total:,.0f}",
delta_text=f"{pulse.budget_used_pct:.1f}% usado este mes",
delta_positive=(pulse.budget_used_pct <= 85.0),
accent_color=b_badge_col,
            )

        st.markdown(
            f"""
            <div style="background:#121722; border-left:4px solid {pulse.next_card_alert_color};
                        border-top:1px solid #263044; border-right:1px solid #263044; border-bottom:1px solid #263044;
                        border-radius:10px; padding:8px 12px; margin:6px 0 10px 0;
                        display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.78rem; color:#CBD5E1;">🗓️ <b>Próximo evento TDC:</b> {pulse.next_card_alert_text}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("💳 Abrir Billetera Apple Wallet y Simulador TDC", use_container_width=True, key="hub_go_finance"):
            st.session_state["active_pillar"] = "finance"
            st.rerun()

    # ── 4. ANALÍTICA CRUZADA Y CONSISTENCIA MULTITEMPORAL (SEMANAL Y MENSUAL) ──
    with st.container(border=True):
        st.markdown("#### 📈 Analítica Cruzada y Evolución del Trifecta Score")
        col_tf, col_mode = st.columns(2)
        with col_tf:
            tf_days = (
                st.segmented_control(
                    "Horizonte",
                    options=[7, 14, 30],
                    default=14,
                    format_func=lambda d: f"{d}D ({'Semanal' if d == 7 else ('Quincenal' if d == 14 else 'Mensual')})",
                    key="hub_consistency_tf",
                )
                or 14
            )
        with col_mode:
            chart_mode = (
                st.segmented_control(
                    "Visualización",
                    options=["trend", "heatmap"],
                    default="trend",
                    format_func=lambda m: "📈 Tendencia" if m == "trend" else "🟦 Mapa de Calor",
                    key="hub_consistency_mode",
                )
                or "trend"
            )

        all_series = consistency_data.get("series") or []
        sliced_series = all_series[-int(tf_days) :] if all_series else []

        c_k1, c_k2 = st.columns(2)
        with c_k1:
render_kpi_card(
label="Promedio Semanal (7D)",
value=f"{consistency_data['avg_trifecta_7d']:.1f} pts",
delta_text=f"{consistency_data['avg_trifecta_7d'] - consistency_data['avg_trifecta_30d']:+.1f} vs 30D",
delta_positive=(consistency_data["avg_trifecta_7d"] >= consistency_data["avg_trifecta_30d"]),
accent_color="#3B82F6",
            )
        with c_k2:
render_kpi_card(
label="Promedio Mensual (30D)",
value=f"{consistency_data['avg_trifecta_30d']:.1f} pts",
delta_text=f"Racha activa: {pulse.consistency_streak_days}d",
delta_positive=(consistency_data["avg_trifecta_30d"] >= 70.0),
accent_color="#10B981",
            )

        if sliced_series:
            x_labels = [r["label"] for r in sliced_series]
            if chart_mode == "trend":
                fig_trend = go.Figure()
                fig_trend.add_trace(
                    go.Bar(
                        x=x_labels,
                        y=[float(r["habit_score"]) for r in sliced_series],
                        name="Hábitos",
                        marker_color="rgba(139, 92, 246, 0.40)",
                    )
                )
                fig_trend.add_trace(
                    go.Bar(
                        x=x_labels,
                        y=[float(r["workout_score"]) for r in sliced_series],
                        name="Entreno",
                        marker_color="rgba(255, 85, 0, 0.40)",
                    )
                )
                fig_trend.add_trace(
                    go.Scatter(
                        x=x_labels,
                        y=[float(r["trifecta_score"]) for r in sliced_series],
                        mode="lines+markers",
                        name="Trifecta Score",
                        line=dict(color="#38BDF8", width=3),
                        marker=dict(size=7, color="#38BDF8"),
                    )
                )
                fig_trend.update_layout(barmode="group")
                apply_mobile_dark_layout(fig_trend, height=250)
                render_mobile_plotly(fig_trend, key="hub_plotly_trend")
            else:
                # Mapa de calor matricial de los 3 pilares + Trifecta Score
                z_matrix = [
                    [float(r["finance_score"]) for r in sliced_series],
                    [float(r["workout_score"]) for r in sliced_series],
                    [float(r["habit_score"]) for r in sliced_series],
                    [float(r["trifecta_score"]) for r in sliced_series],
                ]
                y_Pillars = ["💳 Finanzas", "🏋️ Entreno", "🎯 Hábitos", "⚡ TRIFECTA"]
                fig_heat = go.Figure(
                    data=go.Heatmap(
                        z=z_matrix,
                        x=x_labels,
                        y=y_Pillars,
                        zmin=0,
                        zmax=100,
                        colorscale=[
                            [0.0, "#1E293B"],
                            [0.45, "#F59E0B"],
                            [0.75, "#3B82F6"],
                            [1.0, "#10B981"],
                        ],
                        showscale=False,
                        xgap=3,
                        ygap=3,
                    )
                )
                apply_mobile_dark_layout(fig_heat, height=220)
                render_mobile_plotly(fig_heat, key="hub_plotly_heatmap")
