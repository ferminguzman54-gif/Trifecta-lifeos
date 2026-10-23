"""
Vista de Ajustes de Perfil, Preferencias de Visualización, Ponderación Fija del Trifecta Score,
Motor de Respaldo / Exportación (CSV + Life Snapshot JSON) y Limpieza Segura de Pruebas (Sprint 6).
Accesible desde el avatar del usuario en el encabezado móvil.
"""
from __future__ import annotations

from datetime import date
import streamlit as st

from src.auth.session_manager import get_current_user_id
from src.components.kpi_cards import render_kpi_card
from src.config.settings import APP_VERSION
from src.config.theme import PALETTE, render_pillar_header
from src.services.export_service import (
    fetch_all_user_export_bundle,
    purge_user_test_records,
    update_user_profile_settings,
)

SUPPORTED_CURRENCIES = ["MXN", "USD", "EUR", "COP", "ARS", "CLP", "PEN"]
SUPPORTED_DATE_FORMATS = ["DD/MM/YYYY", "YYYY-MM-DD", "MM/DD/YYYY"]


def render_settings_view() -> None:
    """Renderiza el Centro de Configuración, Respaldo y Limpieza de Pruebas del Sprint 6."""
    user_id = get_current_user_id() or ""
    access_token = st.session_state.get("access_token") or ""
    profile = st.session_state.get("user_profile") or {}

    if not user_id or not access_token:
        st.warning("Inicia sesión para gestionar las preferencias y respaldos de tu cuenta.")
        return

    render_pillar_header(
        title="Ajustes, Perfil & Respaldo",
        subtitle="Preferencias de Unidades · Ponderación Trifecta · Exportación CSV/JSON · Limpieza",
        accent_hex=PALETTE["accent_hub"],
        badge_text=f"⚙️ Configuración · v{APP_VERSION}",
    )

    if st.button("⬅️ Volver al Command Center (Hub)", use_container_width=True, key="set_back_to_hub"):
        st.session_state["active_pillar"] = "hub"
        st.rerun()

    tab_profile, tab_export, tab_danger = st.tabs(
        [
            "👤 Perfil & Ponderación",
            "📦 Exportar Datos (CSV / JSON)",
            "🧹 Limpieza de Pruebas",
        ]
    )

    # =================================================================
    # PESTAÑA 1: PERFIL, UNIDADES Y PONDERACIÓN FIJA DEL TRIFECTA SCORE
    # =================================================================
    with tab_profile:
        with st.container(border=True):
            st.markdown("#### 🪪 Identidad y Preferencias de Visualización")
            curr_name = str(profile.get("full_name") or "Usuario Trifecta")
            curr_alias = str(profile.get("alias") or "")
            curr_email = str(profile.get("email") or "")
            curr_currency = str(profile.get("preferred_currency") or "MXN").upper()
            if curr_currency not in SUPPORTED_CURRENCIES:
                curr_currency = "MXN"
            curr_weight_unit = str(profile.get("weight_unit") or "kg").lower()
            curr_date_fmt = str(profile.get("date_format") or "DD/MM/YYYY")
            if curr_date_fmt not in SUPPORTED_DATE_FORMATS:
                curr_date_fmt = "DD/MM/YYYY"

            col_id1, col_id2 = st.columns([1.3, 1])
            with col_id1:
                full_name_in = st.text_input(
                    "Nombre visible completo",
                    value=curr_name,
                    key="set_full_name",
                )
            with col_id2:
                alias_in = st.text_input(
                    "Alias corto (Encabezado móvil)",
                    value=curr_alias,
                    placeholder="Ej. Fermi, Alex...",
                    key="set_alias",
                )

            if curr_email:
                st.caption(f"📧 Cuenta autenticada en Supabase: `{curr_email}` · ID: `{user_id[:8]}...`")

            col_u1, col_u2, col_u3 = st.columns(3)
            with col_u1:
                weight_unit_in = st.selectbox(
                    "Unidad de peso (Gym)",
                    options=["kg", "lb"],
                    index=0 if curr_weight_unit == "kg" else 1,
                    format_func=lambda u: "Kilogramos (kg)" if u == "kg" else "Libras (lb)",
                    key="set_weight_unit",
                )
            with col_u2:
                currency_in = st.selectbox(
                    "Moneda predeterminada",
                    options=SUPPORTED_CURRENCIES,
                    index=SUPPORTED_CURRENCIES.index(curr_currency),
                    key="set_currency",
                )
            with col_u3:
                date_fmt_in = st.selectbox(
                    "Formato de fecha",
                    options=SUPPORTED_DATE_FORMATS,
                    index=SUPPORTED_DATE_FORMATS.index(curr_date_fmt),
                    key="set_date_format",
                )

        with st.container(border=True):
            st.markdown("#### ⚖️ Ponderación Fija Personalizada del Trifecta Score")
            st.caption(
                "Define el peso permanente de cada pilar en el cálculo de tu Trifecta Score diario. "
                "Si la suma difiere de 100%, el motor la normaliza proporcionalmente de forma automática."
            )

            w_session = st.session_state.get("trifecta_weights") or {}
            init_wh = int(round(float(profile.get("weight_habits") or w_session.get("habits") or 40.0)))
            init_ww = int(round(float(profile.get("weight_workouts") or w_session.get("workout") or 35.0)))
            init_wf = int(round(float(profile.get("weight_finances") or w_session.get("finance") or 25.0)))

            col_w1, col_w2, col_w3 = st.columns(3)
            with col_w1:
                w_hab_in = st.slider(
                    "🎯 Hábitos (%)",
                    min_value=5,
                    max_value=80,
                    value=max(5, min(80, init_wh)),
                    step=5,
                    key="set_w_habits",
                )
            with col_w2:
                w_wrk_in = st.slider(
                    "🏋️ Entrenamiento (%)",
                    min_value=5,
                    max_value=80,
                    value=max(5, min(80, init_ww)),
                    step=5,
                    key="set_w_workouts",
                )
            with col_w3:
                w_fin_in = st.slider(
                    "💳 Finanzas (%)",
                    min_value=5,
                    max_value=80,
                    value=max(5, min(80, init_wf)),
                    step=5,
                    key="set_w_finances",
                )

            raw_sum = max(1, w_hab_in + w_wrk_in + w_fin_in)
            eff_h = round((w_hab_in / raw_sum) * 100.0, 1)
            eff_w = round((w_wrk_in / raw_sum) * 100.0, 1)
            eff_f = round(100.0 - eff_h - eff_w, 1)

            st.markdown(
                f"""
                <div style="background:#1A2232; border:1px solid #263044; border-radius:12px; padding:10px 12px; margin:8px 0 12px 0;">
                    <div style="display:flex; justify-content:space-between; font-size:0.76rem; color:#CBD5E1; margin-bottom:6px;">
                        <span>🎯 Hábitos: <b style="color:#A78BFA;">{eff_h:.1f}%</b></span>
                        <span>🏋️ Entreno: <b style="color:#FB923C;">{eff_w:.1f}%</b></span>
                        <span>💳 Finanzas: <b style="color:#34D399;">{eff_f:.1f}%</b></span>
                    </div>
                    <div style="width:100%; height:10px; border-radius:999px; overflow:hidden; display:flex; background:#0A0D14;">
                        <div style="width:{eff_h}%; background:#8B5CF6;"></div>
                        <div style="width:{eff_w}%; background:#FF5500;"></div>
                        <div style="width:{eff_f}%; background:#10B981;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "💾 Guardar Perfil, Unidades y Ponderaciones",
                type="primary",
                use_container_width=True,
                key="set_save_profile_btn",
            ):
                ok, msg = update_user_profile_settings(
                    user_id=user_id,
                    full_name=full_name_in,
                    alias=alias_in,
                    preferred_currency=currency_in,
                    weight_unit=weight_unit_in,
                    date_format=date_fmt_in,
                    weight_habits=float(w_hab_in),
                    weight_workouts=float(w_wrk_in),
                    weight_finances=float(w_fin_in),
                )
                if ok:
                    st.toast(msg, icon="✅")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # =================================================================
    # PESTAÑA 2: MOTOR DE RESPALDO Y EXPORTACIÓN (CSV + LIFE SNAPSHOT JSON)
    # =================================================================
    with tab_export:
        export_bundle = fetch_all_user_export_bundle(user_id, access_token)
        counts = export_bundle["counts"]
        today_stamp = date.today().isoformat()

        st.markdown("#### 📊 Inventario Actual de tu Cuenta")
        kc1, kc2, kc3 = st.columns(3)
        with kc1:
            render_kpi_card(
                label="Hábitos / Registros",
                value=f"{counts['habit_logs_count']} logs",
                delta_text=f"{counts['habits_count']} hábitos · {counts['personal_goals_count']} metas",
                delta_positive=True,
                accent_color=PALETTE["accent_habits"],
            )
        with kc2:
            render_kpi_card(
                label="Entreno / Series",
                value=f"{counts['workout_sets_count']} series",
                delta_text=f"{counts['workout_sessions_count']} sesiones · {counts['workout_routines_count']} rutinas",
                delta_positive=True,
                accent_color=PALETTE["accent_workout"],
            )
        with kc3:
            render_kpi_card(
                label="Finanzas / Movimientos",
                value=f"{counts['finance_transactions_count']} movs",
                delta_text=f"{counts['finance_accounts_count']} cuentas/TDC",
                delta_positive=True,
                accent_color=PALETTE["accent_finance"],
            )

        with st.container(border=True):
            st.markdown("#### 📄 Exportación Tabular en CSV (Excel / Google Sheets)")
            st.caption(
                "Descarga archivos CSV independientes codificados en UTF-8 con BOM para análisis externo."
            )
            dl_c1, dl_c2, dl_c3 = st.columns(3)
            with dl_c1:
                st.download_button(
                    label="🎯 Hábitos (.CSV)",
                    data=export_bundle["habits_csv"].encode("utf-8"),
                    file_name=f"trifecta_habits_{today_stamp}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_csv_habits",
                )
            with dl_c2:
                st.download_button(
                    label="🏋️ Entrenamiento (.CSV)",
                    data=export_bundle["workouts_csv"].encode("utf-8"),
                    file_name=f"trifecta_workouts_{today_stamp}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_csv_workouts",
                )
            with dl_c3:
                st.download_button(
                    label="💳 Finanzas (.CSV)",
                    data=export_bundle["finances_csv"].encode("utf-8"),
                    file_name=f"trifecta_finances_{today_stamp}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_csv_finances",
                )

        with st.container(border=True):
            st.markdown("#### 📦 Respaldo Integral Consolidado (Life Snapshot .JSON)")
            st.caption(
                "Incluye tu perfil, preferencias, ponderaciones, rutinas, sesiones, series, cuentas, "
                "transacciones, suscripciones, hábitos, metas personales y snapshots diarios en un solo archivo JSON."
            )
            st.download_button(
                label=f"📦 Descargar Life Snapshot Completo ({today_stamp}.json)",
                data=export_bundle["snapshot_json"].encode("utf-8"),
                file_name=f"trifecta_life_snapshot_{today_stamp}.json",
                mime="application/json",
                type="primary",
                use_container_width=True,
                key="dl_json_snapshot",
            )
            with st.expander("🔍 Previsualizar estructura del archivo Life Snapshot JSON"):
                st.code(export_bundle["snapshot_json"][:2500] + "\n...", language="json")

    # =================================================================
    # PESTAÑA 3: GESTIÓN DE DATOS Y LIMPIEZA SEGURA DE PRUEBAS
    # =================================================================
    with tab_danger:
        with st.container(border=True):
            st.markdown(
                """
                <div style="background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.40);
                            border-radius:12px; padding:12px 14px; margin-bottom:12px;">
                    <div style="font-size:0.84rem; font-weight:800; color:#EF4444; text-transform:uppercase;">
                        🛡️ Limpieza Segura de Registros de Prueba (Reinicio Operativo)
                    </div>
                    <div style="font-size:0.80rem; color:#CBD5E1; margin-top:4px;">
                        Esta herramienta te permite depurar los registros de prueba creados durante la validación
                        de los Sprints 1 a 5 para comenzar a usar <b>Trifecta LifeOS</b> en producción con tu historial limpio:
                        <ul style="margin:6px 0 4px 18px; padding:0;">
                            <li><b>Se eliminan:</b> Registros diarios de hábitos (<code>habit_logs</code>), series y sesiones de entrenamiento (<code>workout_sets</code>, <code>workout_sessions</code>), transacciones financieras (<code>finance_transactions</code>) y snapshots diarios (<code>daily_life_snapshots</code>).</li>
                            <li><b>Se conservan intactos:</b> Tu perfil, unidades, rutinas configuradas (<code>workout_routines</code>), catálogo de ejercicios, cuentas/tarjetas (<code>finance_accounts</code>), categorías presupuestales, suscripciones, hábitos base (<code>habits</code>) y metas personales (<code>personal_goals</code>).</li>
                        </ul>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            reset_cc_chk = st.checkbox(
                "Reiniciar también la deuda utilizada de mis tarjetas de crédito a $0.00",
                value=True,
                key="purge_reset_cc_chk",
            )
            confirm_txt = st.text_input(
                "Para habilitar la limpieza, escribe exactamente BORRAR en mayúsculas:",
                placeholder="BORRAR",
                key="purge_confirm_input",
            )

            if st.button(
                "🗑️ Purgar Registros de Prueba Ahora",
                type="primary",
                disabled=(confirm_txt.strip() != "BORRAR"),
                use_container_width=True,
                key="purge_execute_btn",
            ):
                ok, msg = purge_user_test_records(
                    user_id=user_id,
                    confirmation_text=confirm_txt,
                    reset_credit_card_balances=bool(reset_cc_chk),
                )
                if ok:
                    st.toast(msg, icon="🧹")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
