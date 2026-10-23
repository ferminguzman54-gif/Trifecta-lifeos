"""
Command Center — Resumen Diario Unificado de los 3 Pilares
según 03_Appflow_Flujo_Usuario.md (§3).
"""
from __future__ import annotations

from datetime import date
from typing import Dict
import streamlit as st

from src.auth.session_manager import get_current_user_id
from src.auth.supabase_client import get_supabase_client
from src.components.kpi_cards import render_kpi_card
from src.config.theme import PALETTE, render_pillar_header
from src.services.habit_streak_engine import (
    calculate_habit_analytics,
    fetch_habit_logs,
    fetch_habits,
    upsert_habit_log,
)
from src.services.progression_engine import (
    calculate_multitemporal_volume,
    fetch_exercises_catalog,
    fetch_workout_sets,
)


@st.cache_data(ttl=300)
def _fetch_hub_summary_counts(user_id: str, access_token: str) -> Dict[str, int]:
    """Consulta conteos básicos aislados por user_id para el Command Center."""
    counts = {
        "exercises_catalog": 0,
        "workout_sessions": 0,
        "finance_accounts": 0,
        "finance_categories": 0,
        "habits_active": 0,
        "personal_goals": 0,
    }
    try:
        client = get_supabase_client(access_token=access_token)
        ex_res = client.table("exercises").select("id", count="exact").execute()
        counts["exercises_catalog"] = ex_res.count or len(ex_res.data or [])

        ws_res = client.table("workout_sessions").select("id", count="exact").eq("user_id", user_id).execute()
        counts["workout_sessions"] = ws_res.count or len(ws_res.data or [])

        fa_res = client.table("finance_accounts").select("id", count="exact").eq("user_id", user_id).execute()
        counts["finance_accounts"] = fa_res.count or len(fa_res.data or [])

        fc_res = client.table("finance_categories").select("id", count="exact").eq("user_id", user_id).execute()
        counts["finance_categories"] = fc_res.count or len(fc_res.data or [])

        hb_res = (
            client.table("habits")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_archived", False)
            .execute()
        )
        counts["habits_active"] = hb_res.count or len(hb_res.data or [])

        pg_res = client.table("personal_goals").select("id", count="exact").eq("user_id", user_id).execute()
        counts["personal_goals"] = pg_res.count or len(pg_res.data or [])
    except Exception:
        pass
    return counts


def render_home_hub_view() -> None:
    """Renderiza el Command Center con los 3 bloques ejecutivos diarios."""
    profile = st.session_state.get("user_profile") or {}
    full_name = profile.get("full_name", "Usuario Trifecta")
    currency = profile.get("preferred_currency", "MXN")
    weight_unit = profile.get("weight_unit", "kg")
    user_id = get_current_user_id() or ""
    access_token = st.session_state.get("access_token") or ""

    render_pillar_header(
        title=f"Hola, {full_name}",
        subtitle="Resumen ejecutivo de tus 3 pilares de vida hoy",
        accent_hex=PALETTE["accent_hub"],
        badge_text="⚡ Command Center",
    )

    counts = _fetch_hub_summary_counts(user_id, access_token) if user_id and access_token else {
        "exercises_catalog": 0,
        "workout_sessions": 0,
        "finance_accounts": 0,
        "finance_categories": 0,
        "habits_active": 0,
        "personal_goals": 0,
    }

    # Bloque 1 — Estado de Entrenamiento del Día (Volumen 7d en tiempo real)
    with st.container(border=True):
        w_exercises = fetch_exercises_catalog(user_id, access_token) if user_id and access_token else []
        w_sets = fetch_workout_sets(user_id, access_token, days_back=15) if user_id and access_token else []
        ex_by_id = {str(e["id"]): e for e in w_exercises}
        vol_7d = calculate_multitemporal_volume(w_sets, ex_by_id, timeframe_code="1W", metric_mode="effective_sets")

        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span class="trifecta-pillar-pill" style="background:#FF550026; color:#FF5500; border:1px solid #FF550055;">
                    🏋️ Pilar 1 · Entrenamiento Físico
                </span>
                <span style="font-size:0.76rem; color:#94A3B8;">Unidad: <b>{weight_unit}</b></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            render_kpi_card(
                label="Volumen Últimos 7 Días",
                value=f"{vol_7d['current_total']:g} series ef.",
                delta_text=f"{vol_7d['delta_pct']:+.0f}% vs 7d prev",
                delta_positive=(float(vol_7d["delta_pct"]) >= 0),
                accent_color=PALETTE["accent_workout"],
            )
        with col_w2:
            render_kpi_card(
                label="Sesiones / Catálogo",
                value=f"{counts['workout_sessions']} ses.",
                delta_text=f"{counts['exercises_catalog']} ejercicios",
                delta_positive=True,
                accent_color=PALETTE["accent_workout"],
            )
        if st.button("⚡ Iniciar Entrenamiento", use_container_width=True, key="hub_go_workout"):
            st.session_state["active_pillar"] = "workout"
            st.rerun()

    # Bloque 2 — Pulso Financiero y Próximo Vencimiento
    with st.container(border=True):
        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span class="trifecta-pillar-pill" style="background:#10B98126; color:#10B981; border:1px solid #10B98155;">
                    💳 Pilar 2 · Pulso Financiero
                </span>
                <span style="font-size:0.76rem; color:#94A3B8;">Moneda: <b>{currency}</b></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            render_kpi_card(
                label="Cuentas / TDC Activas",
                value=str(counts["finance_accounts"]),
                delta_text="Billetera lista",
                delta_positive=True,
                accent_color=PALETTE["accent_finance"],
            )
        with col_f2:
            render_kpi_card(
                label="Categorías Presupuesto",
                value=str(counts["finance_categories"]),
                delta_text="Aisladas por RLS",
                delta_positive=True,
                accent_color=PALETTE["accent_finance"],
            )
        if st.button("➕ Registrar Movimiento / Simulador TDC", use_container_width=True, key="hub_go_finance"):
            st.session_state["active_pillar"] = "finance"
            st.rerun()

    # Bloque 3 — Progreso de Hábitos de Hoy (Interactivo en tiempo real con progreso parcial)
    with st.container(border=True):
        habits = fetch_habits(user_id, access_token, include_archived=False) if user_id and access_token else []
        logs = fetch_habit_logs(user_id, access_token, days_back=35) if user_id and access_token else []
        analytics_map = {str(h["id"]): calculate_habit_analytics(h, logs) for h in habits}

        total_h = len(habits)
        done_h = sum(1 for a in analytics_map.values() if a.today_status == "COMPLETED")
        partial_h = sum(1 for a in analytics_map.values() if a.today_status == "PARTIAL")
        pct_h = round(sum(a.today_bar_pct for a in analytics_map.values()) / total_h, 1) if total_h > 0 else 0.0

        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span class="trifecta-pillar-pill" style="background:#8B5CF626; color:#8B5CF6; border:1px solid #8B5CF655;">
                    🎯 Pilar 3 · Progreso de Hábitos de Hoy
                </span>
                <span class="trifecta-kpi-value" style="font-size:0.80rem; color:#F8FAFC;">
                    {done_h} completados · {partial_h} en progreso ({pct_h:g}%)
                </span>
            </div>
            <div style="width:100%; height:7px; background:rgba(255,255,255,0.10); border-radius:999px; margin-bottom:10px; overflow:hidden;">
                <div style="width:{min(100.0, pct_h):.1f}%; height:100%; background:#8B5CF6; border-radius:999px;"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Mostrar pendientes o en progreso del día para completar en 1 toque desde el Command Center
        pending_habits = [h for h in habits if analytics_map[str(h["id"])].today_status != "COMPLETED"]
        if pending_habits:
            st.caption("Pendientes o en progreso hoy (completar al 100% en 1 toque):")
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
                        f"({ph_ana.today_value:g}/{target_v:g} {unit_lbl} · {ph_ana.today_progress_pct:.1f}%)"
                    )
                else:
                    btn_txt = f"⬜ {ph.get('icon', '⚡')} {ph.get('name')} (Meta: {target_v:g} {unit_lbl})"

                if st.button(btn_txt, key=f"hub_quick_check_{ph_id}", use_container_width=True):
                    upsert_habit_log(user_id, ph, target_v, log_date=date.today())
                    st.rerun()

        if st.button("🎯 Abrir Dashboard de Hábitos y Metas", use_container_width=True, key="hub_go_habits"):
            st.session_state["active_pillar"] = "habits"
            st.rerun()
