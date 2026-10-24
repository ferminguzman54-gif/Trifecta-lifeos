"""
Vista de Finanzas Personales, Billetera Digital tipo Apple Wallet, Calendario Financiero
y Simulador Inteligente de Tarjetas de Crédito (Sprint 4 — Pilar 2).
Sigue estrictamente 01_PRD (§3), 02_TRD (§5.2), 03_Appflow (§5) y 04_UI_UX_Design_Brief.
"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List

import plotly.graph_objects as go
import streamlit as st

from src.auth.session_manager import get_current_user_id
from src.components.chart_builders import apply_mobile_dark_layout, render_mobile_plotly
from src.components.credit_card_widget import render_credit_card_widget
from src.components.kpi_cards import render_kpi_card
from src.config.theme import CARD_GRADIENTS, PALETTE, render_pillar_header
from src.models.finance_models import (
    ACCOUNT_TYPE_LABELS,
    BILLING_CYCLE_LABELS,
    TX_TYPE_LABELS,
)
from src.services.card_advisor_engine import (
    build_financial_calendar_events,
    calculate_card_cycle_dates,
    calculate_cashflow_and_budget_summary,
    create_finance_account,
    create_finance_subscription,
    create_finance_transaction,
    delete_finance_account,
    delete_finance_subscription,
    delete_finance_transaction,
    evaluate_best_payment_cards,
    fetch_finance_accounts,
    fetch_finance_categories,
    fetch_finance_subscriptions,
    fetch_finance_transactions,
    seed_sample_wallet_for_user,
    simulate_credit_card_amortization,
    update_category_budget_limit,
    update_finance_account_balance,
)


SPANISH_MONTHS: List[str] = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


# =====================================================================
# MODALES ERGONÓMICOS MOBILE-FIRST (@st.dialog)
# =====================================================================


@st.dialog("➕ Registrar Movimiento Financiero")
def _open_new_transaction_dialog(
    user_id: str,
    currency: str,
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    budget_summary: Dict[str, Any],
) -> None:
    """Modal móvil para registrar gastos, ingresos, pagos de TDC o transferencias."""
    if not accounts:
        st.warning("Primero crea una cuenta o genera la Billetera Demo para registrar movimientos.")
        return

    tx_type_ui = (
        st.segmented_control(
            "Tipo de movimiento",
            options=["expense", "income", "cc_payment", "transfer"],
            default="expense",
            format_func=lambda t: TX_TYPE_LABELS.get(t, t),
            key="dlg_tx_type_seg",
        )
        or "expense"
    )

    acc_options = {
        str(a["id"]): (
            f"{a['name']} ({a.get('institution_name', 'Banco')} · "
            f"${float(a.get('current_balance') or 0):,.2f})"
        )
        for a in accounts
    }

    if tx_type_ui in ("cc_payment", "transfer"):
        liquid_accs = [a for a in accounts if str(a.get("account_type")) != "credit_card"] or accounts
        src_map = {
            str(a["id"]): f"{a['name']} (${float(a.get('current_balance') or 0):,.2f})"
            for a in liquid_accs
        }
        source_account_id = st.selectbox(
            "Cuenta origen (de donde sale el dinero)",
            options=list(src_map.keys()),
            format_func=lambda k: src_map[k],
            key="dlg_tx_src_acc",
        )
        if tx_type_ui == "cc_payment":
            dest_candidates = [a for a in accounts if str(a.get("account_type")) == "credit_card"] or accounts
            dest_label = "Tarjeta de crédito a liquidar / abonar"
        else:
            dest_candidates = [a for a in accounts if str(a["id"]) != source_account_id] or accounts
            dest_label = "Cuenta destino"
        dest_map = {
            str(a["id"]): f"{a['name']} (Saldo: ${float(a.get('current_balance') or 0):,.2f})"
            for a in dest_candidates
        }
        destination_account_id = st.selectbox(
            dest_label,
            options=list(dest_map.keys()),
            format_func=lambda k: dest_map[k],
            key="dlg_tx_dest_acc",
        )
    else:
        source_account_id = st.selectbox(
            "Cuenta o tarjeta",
            options=list(acc_options.keys()),
            format_func=lambda k: acc_options[k],
            key="dlg_tx_single_acc",
        )
        destination_account_id = None

    col_amt, col_dt = st.columns([1.2, 1])
    with col_amt:
        amount = st.number_input(
            f"Monto ({currency})",
            min_value=0.01,
            value=250.0,
            step=50.0,
            format="%.2f",
            key="dlg_tx_amount",
        )
    with col_dt:
        tx_date = st.date_input(
            "Fecha",
            value=date.today(),
            key="dlg_tx_date",
        )

    selected_category_id = None
    if tx_type_ui in ("expense", "income"):
        filtered_cats = [
            c for c in categories if str(c.get("kind", "expense")) == tx_type_ui
        ] or categories
        if filtered_cats:
            cat_map = {
                str(c["id"]): f"{c.get('icon', '💸')} {c.get('name', 'Categoría')}"
                for c in filtered_cats
            }
            selected_category_id = st.selectbox(
                "Categoría",
                options=list(cat_map.keys()),
                format_func=lambda k: cat_map[k],
                key="dlg_tx_cat",
            )
            if tx_type_ui == "expense" and selected_category_id:
                cat_rows = budget_summary.get("categories_breakdown") or []
                match_cat = next(
                    (r for r in cat_rows if str(r.get("id")) == str(selected_category_id)),
                    None,
                )
                if match_cat and float(match_cat.get("budget_limit") or 0) > 0:
                    cur_spent = float(match_cat["spent"])
                    b_limit = float(match_cat["budget_limit"])
                    projected_spent = cur_spent + float(amount)
                    proj_pct = (projected_spent / b_limit) * 100.0
                    bar_color = (
                        "#10B981"
                        if proj_pct <= 85
                        else ("#F59E0B" if proj_pct <= 100 else "#EF4444")
                    )
                    st.markdown(
                        f"""
                        <div style="background:#1A202F; border:1px solid #263044; border-radius:8px; padding:8px 10px; margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94A3B8; margin-bottom:4px;">
                                <span>Presupuesto {match_cat['name']} tras compra:</span>
                                <span style="color:{bar_color}; font-weight:700;">${projected_spent:,.0f} / ${b_limit:,.0f} ({proj_pct:.1f}%)</span>
                            </div>
                            <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden;">
                                <div style="width:{min(100.0, proj_pct):.1f}%; height:100%; background:{bar_color};"></div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    merchant_or_concept = st.text_input(
        "Comercio o concepto",
        placeholder="Ej. Supermercado HEB, Gasolina, Uber, Nómina...",
        key="dlg_tx_concept",
    )

    col_msi, col_tags = st.columns([1, 1.3])
    with col_msi:
        msi_months = st.selectbox(
            "Plazo / MSI",
            options=[1, 3, 6, 9, 12, 18, 24],
            format_func=lambda m: "Contado (1 exhibición)" if m == 1 else f"{m} MSI",
            key="dlg_tx_msi",
        )
    with col_tags:
        tags_raw = st.text_input(
            "Etiquetas (separadas por coma)",
            placeholder="fijo, viaje, deducible",
            key="dlg_tx_tags",
        )

    notes = st.text_input(
        "Notas adicionales (opcional)",
        placeholder="Ej. Compra compartida, factura pendiente...",
        key="dlg_tx_notes",
    )

    if st.button("💾 Guardar Movimiento", type="primary", use_container_width=True, key="dlg_tx_submit"):
        concept_clean = merchant_or_concept.strip() or TX_TYPE_LABELS.get(tx_type_ui, "Movimiento")
        tags_list = [t.strip().lstrip("#") for t in tags_raw.split(",") if t.strip()]
        ok, msg = create_finance_transaction(
            user_id=user_id,
            account_id=source_account_id,
            tx_type=tx_type_ui,
            amount=float(amount),
            merchant_or_concept=concept_clean,
            tx_date=tx_date,
            category_id=selected_category_id,
            destination_account_id=destination_account_id,
            tags=tags_list,
            is_msi=(int(msi_months) > 1),
            msi_months=int(msi_months),
            notes=notes,
        )
        if ok:
            st.toast(msg, icon="✅")
            st.rerun()
        else:
            st.error(msg)


@st.dialog("💳 Nueva Cuenta o Tarjeta")
def _open_new_account_dialog(user_id: str, currency: str) -> None:
    """Modal para dar de alta cuentas de débito, efectivo, inversión o tarjetas de crédito."""
    col_n1, col_n2 = st.columns([1.2, 1])
    with col_n1:
        name = st.text_input(
            "Alias de la cuenta o tarjeta",
            placeholder="Ej. TDC Nu Morada, BBVA Azul, Nómina...",
            key="dlg_acc_name",
        )
    with col_n2:
        institution_name = st.text_input(
            "Institución bancaria",
            placeholder="Ej. Nu, BBVA, Amex, Banorte...",
            value="BBVA",
            key="dlg_acc_inst",
        )

    account_type = st.selectbox(
        "Tipo de cuenta",
        options=list(ACCOUNT_TYPE_LABELS.keys()),
        format_func=lambda k: ACCOUNT_TYPE_LABELS[k],
        key="dlg_acc_type",
    )

    col_net, col_l4 = st.columns(2)
    with col_net:
        card_network = st.selectbox(
            "Red de pago",
            options=["visa", "mastercard", "amex", "other"],
            format_func=lambda r: r.upper(),
            key="dlg_acc_net",
        )
    with col_l4:
        last_four_digits = st.text_input(
            "Últimos 4 dígitos",
            value="4821",
            max_chars=4,
            key="dlg_acc_last4",
        )

    is_cc = account_type == "credit_card"
    balance_label = (
        f"Deuda utilizada actual ({currency})"
        if is_cc
        else f"Saldo disponible actual ({currency})"
    )
    current_balance = st.number_input(
        balance_label,
        min_value=0.0,
        value=0.0 if is_cc else 15000.0,
        step=500.0,
        format="%.2f",
        key="dlg_acc_balance",
    )

    credit_limit = 0.0
    cutoff_day = 15
    payment_due_day = 5
    cashback_pct = 0.0
    interest_rate_cat = 45.0
    minimum_payment_pct = 5.0

    if is_cc:
        credit_limit = st.number_input(
            f"Límite de crédito total ({currency})",
            min_value=500.0,
            value=45000.0,
            step=1000.0,
            format="%.2f",
            key="dlg_acc_limit",
        )
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            cutoff_day = st.number_input(
                "Día de corte del mes (1–31)",
                min_value=1,
                max_value=31,
                value=8,
                step=1,
                key="dlg_acc_cutoff",
            )
        with col_c2:
            payment_due_day = st.number_input(
                "Día límite de pago (1–31)",
                min_value=1,
                max_value=31,
                value=28,
                step=1,
                key="dlg_acc_due",
            )

        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            cashback_pct = st.number_input(
                "Cashback (%)",
                min_value=0.0,
                max_value=20.0,
                value=1.5,
                step=0.25,
                format="%.2f",
                key="dlg_acc_cb",
            )
        with col_r2:
            interest_rate_cat = st.number_input(
                "Tasa Anual / CAT (%)",
                min_value=0.0,
                max_value=200.0,
                value=54.0,
                step=1.0,
                format="%.1f",
                key="dlg_acc_cat",
            )
        with col_r3:
            minimum_payment_pct = st.number_input(
                "Pago mínimo (%)",
                min_value=1.0,
                max_value=25.0,
                value=5.0,
                step=0.5,
                format="%.1f",
                key="dlg_acc_minpct",
            )

    card_gradient_theme = st.selectbox(
        "Estilo visual Apple Wallet",
        options=list(CARD_GRADIENTS.keys()),
        format_func=lambda k: CARD_GRADIENTS[k]["label"],
        key="dlg_acc_theme",
    )

    if st.button("✨ Crear Cuenta / Tarjeta", type="primary", use_container_width=True, key="dlg_acc_submit"):
        if not name.strip():
            st.warning("Ingresa un alias para la cuenta o tarjeta.")
            return
        ok, msg = create_finance_account(
            user_id=user_id,
            name=name.strip(),
            institution_name=institution_name.strip() or "Banco",
            account_type=account_type,
            card_network=card_network,
            last_four_digits=last_four_digits,
            card_gradient_theme=card_gradient_theme,
            current_balance=float(current_balance),
            credit_limit=float(credit_limit),
            cutoff_day=int(cutoff_day) if is_cc else None,
            payment_due_day=int(payment_due_day) if is_cc else None,
            cashback_pct=float(cashback_pct),
            interest_rate_cat=float(interest_rate_cat),
            minimum_payment_pct=float(minimum_payment_pct),
        )
        if ok:
            st.toast(msg, icon="💳")
            st.rerun()
        else:
            st.error(msg)


@st.dialog("🔄 Nueva Suscripción o Pago Recurrente")
def _open_new_subscription_dialog(
    user_id: str,
    currency: str,
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
) -> None:
    """Modal para programar pagos fijos o suscripciones en el Calendario Financiero."""
    if not accounts:
        st.warning("Primero crea una cuenta o tarjeta para vincular la suscripción.")
        return

    service_name = st.text_input(
        "Nombre del servicio o cargo recurrente",
        placeholder="Ej. Spotify, Gimnasio, Internet Fibra, Seguro Auto...",
        key="dlg_sub_name",
    )
    col_a, col_b, col_c = st.columns([1.1, 1, 1])
    with col_a:
        amount = st.number_input(
            f"Monto ({currency})",
            min_value=1.0,
            value=199.0,
            step=20.0,
            format="%.2f",
            key="dlg_sub_amount",
        )
    with col_b:
        billing_cycle = st.selectbox(
            "Frecuencia",
            options=list(BILLING_CYCLE_LABELS.keys()),
            index=2,  # monthly
            format_func=lambda c: BILLING_CYCLE_LABELS.get(c, c),
            key="dlg_sub_cycle",
        )
    with col_c:
        billing_day = st.number_input(
            "Día de cobro (1–31)",
            min_value=1,
            max_value=31,
            value=min(28, date.today().day + 3),
            step=1,
            key="dlg_sub_day",
        )

    acc_map = {str(a["id"]): a["name"] for a in accounts}
    account_id = st.selectbox(
        "Tarjeta o cuenta de cargo",
        options=list(acc_map.keys()),
        format_func=lambda k: acc_map[k],
        key="dlg_sub_acc",
    )

    expense_cats = [c for c in categories if str(c.get("kind", "expense")) == "expense"] or categories
    cat_map = {str(c["id"]): f"{c.get('icon', '🔄')} {c.get('name')}" for c in expense_cats}
    category_id = (
        st.selectbox(
            "Categoría de presupuesto",
            options=list(cat_map.keys()),
            format_func=lambda k: cat_map[k],
            key="dlg_sub_cat",
        )
        if cat_map
        else None
    )

    if st.button("📅 Programar en Calendario", type="primary", use_container_width=True, key="dlg_sub_submit"):
        if not service_name.strip():
            st.warning("Escribe el nombre del servicio.")
            return
        ok, msg = create_finance_subscription(
            user_id=user_id,
            service_name=service_name.strip(),
            amount=float(amount),
            billing_cycle=billing_cycle,
            billing_day_of_month=int(billing_day),
            account_id=account_id,
            category_id=category_id,
        )
        if ok:
            st.toast(msg, icon="📅")
            st.rerun()
        else:
            st.error(msg)


# =====================================================================
# FRAGMENTOS INTERACTIVOS DEL SIMULADOR INTELIGENTE DE TDC
# =====================================================================


@st.fragment
def _render_card_advisor_simulator_fragment(
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    budget_summary: Dict[str, Any],
    currency: str,
) -> None:
    """
    Simulador Inteligente 1: «¿Con qué tarjeta pago hoy?»
    Evalúa las 4 variables ponderadas (45% Float, 25% Cashback, 20% Utilización, 10% Presupuesto)
    y alerta si conviene esperar 1–5 días a que pase la fecha de corte.
    """
    st.markdown(
        """
        <div style="background:rgba(16,185,129,0.10); border:1px solid rgba(16,185,129,0.35);
                    border-radius:12px; padding:12px 14px; margin-bottom:12px;">
            <div style="font-size:0.78rem; font-weight:700; color:#10B981; text-transform:uppercase; letter-spacing:0.05em;">
                🧠 Motor Algorítmico · ¿Con qué tarjeta pago hoy?
            </div>
            <div style="font-size:0.82rem; color:#94A3B8; margin-top:2px;">
                Compara tus tarjetas activas ponderando: <b>45% Días de financiamiento post-corte</b> ·
                <b>25% Cashback</b> · <b>20% Salud de utilización (&le;30%)</b> · <b>10% Presupuesto de categoría</b>.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    expense_cats = [c for c in categories if str(c.get("kind", "expense")) == "expense"] or categories
    cat_options = {
        str(c["id"]): f"{c.get('icon', '💸')} {c.get('name', 'Categoría')}"
        for c in expense_cats
    }

    col_s1, col_s2, col_s3 = st.columns([1.1, 1.2, 1])
    with col_s1:
        sim_amount = st.number_input(
            f"Monto a pagar ({currency})",
            min_value=10.0,
            value=2500.0,
            step=250.0,
            format="%.2f",
            key="sim_advisor_amount",
        )
    with col_s2:
        sim_cat_id = (
            st.selectbox(
                "Categoría del gasto",
                options=list(cat_options.keys()),
                format_func=lambda k: cat_options[k],
                key="sim_advisor_cat",
            )
            if cat_options
            else None
        )
    with col_s3:
        sim_purchase_date = st.date_input(
            "Fecha de compra",
            value=date.today(),
            key="sim_advisor_date",
        )

    # Obtener presupuesto remanente de la categoría seleccionada
    cat_rem_budget = None
    if sim_cat_id:
        cat_rows = budget_summary.get("categories_breakdown") or []
        matched = next((r for r in cat_rows if str(r.get("id")) == str(sim_cat_id)), None)
        if matched and float(matched.get("budget_limit") or 0) > 0:
            cat_rem_budget = float(matched["remaining"])

    recommendations = evaluate_best_payment_cards(
        credit_cards=accounts,
        amount=float(sim_amount),
        purchase_date=sim_purchase_date,
        category_remaining_budget=cat_rem_budget,
    )

    if not recommendations:
        st.info("Agrega al menos una Tarjeta de Crédito (TDC) en tu billetera para usar el recomendador.")
        return

    winner = recommendations[0]
    win_border = "#10B981" if winner.is_eligible else "#EF4444"
    win_badge_bg = "rgba(16,185,129,0.20)" if winner.is_eligible else "rgba(239,68,68,0.20)"
    win_badge_txt = (
        f"🏆 MEJOR OPCIÓN · SCORE {winner.total_score:.1f}/100"
        if winner.is_eligible
        else "⚠️ LÍNEA INSUFICIENTE EN TODAS LAS TDC"
    )
    summary_txt = (
        f"{winner.optimal_window_badge} · Comprando el {sim_purchase_date.strftime('%d/%b')} obtienes "
        f"<b>{winner.float_days} días sin intereses</b> (corta el {winner.statement_cutoff_date.strftime('%d/%b')} "
        f"y se paga hasta el {winner.payment_due_date.strftime('%d/%b')})."
        if winner.is_eligible
        else (winner.rejection_reason or "Excede la línea de crédito disponible.")
    )

    st.markdown(
        f"""
        <div style="background:linear-gradient(145deg, #121722 0%, #192234 100%);
                    border:2px solid {win_border}; border-radius:14px; padding:16px; margin:8px 0 12px 0;
                    box-shadow:0 10px 26px rgba(0,0,0,0.45);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                <span style="font-size:0.73rem; font-weight:700; padding:4px 10px; border-radius:999px;
                             background:{win_badge_bg}; color:{win_border}; border:1px solid {win_border}66;">
                    {win_badge_txt}
                </span>
                <span style="font-size:0.78rem; color:#94A3B8; font-family:'JetBrains Mono', monospace;">
                    Liquidar el: <b style="color:#F8FAFC;">{winner.payment_due_date.strftime('%d/%b/%Y')}</b>
                </span>
            </div>
            <div style="font-size:1.25rem; font-weight:800; color:#F8FAFC; margin:10px 0 4px 0;">
                💳 {winner.card_name} <span style="font-size:0.82rem; color:#94A3B8; font-weight:500;">({winner.institution_name} •••• {winner.last_four_digits})</span>
            </div>
            <div style="font-size:0.84rem; color:#CBD5E1; margin-bottom:12px;">
                {summary_txt}
            </div>
            <div style="display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:8px;">
                <div style="background:rgba(10,13,20,0.65); border:1px solid #263044; border-radius:10px; padding:8px 10px;">
                    <div style="font-size:0.68rem; color:#94A3B8; text-transform:uppercase;">Plazo sin intereses (45%)</div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size:1.05rem; font-weight:700; color:#10B981;">
                        {winner.float_days} días libres
                    </div>
                    <div style="font-size:0.70rem; color:#64748B;">Score Float: {winner.score_float:.1f}/45 pts</div>
                </div>
                <div style="background:rgba(10,13,20,0.65); border:1px solid #263044; border-radius:10px; padding:8px 10px;">
                    <div style="font-size:0.68rem; color:#94A3B8; text-transform:uppercase;">Recompensa Cashback (25%)</div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size:1.05rem; font-weight:700; color:#38BDF8;">
                        +${winner.cashback_earned:,.2f} {currency}
                    </div>
                    <div style="font-size:0.70rem; color:#64748B;">Tasa {winner.cashback_pct:.2f}% · {winner.score_cashback:.1f}/25 pts</div>
                </div>
                <div style="background:rgba(10,13,20,0.65); border:1px solid #263044; border-radius:10px; padding:8px 10px;">
                    <div style="font-size:0.68rem; color:#94A3B8; text-transform:uppercase;">Salud Utilización (20%)</div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size:0.95rem; font-weight:700; color:#F8FAFC;">
                        {winner.utilization_before_pct:.1f}% → {winner.utilization_after_pct:.1f}%
                    </div>
                    <div style="font-size:0.70rem; color:#64748B;">Disp. post-compra: ${winner.available_credit_after:,.0f}</div>
                </div>
                <div style="background:rgba(10,13,20,0.65); border:1px solid #263044; border-radius:10px; padding:8px 10px;">
                    <div style="font-size:0.68rem; color:#94A3B8; text-transform:uppercase;">Ajuste Presupuesto (10%)</div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size:0.95rem; font-weight:700; color:#F8FAFC;">
                        {winner.score_budget:.1f} / 10 pts
                    </div>
                    <div style="font-size:0.70rem; color:#64748B;">Remanente cat.: ${winner.budget_remaining_after:,.0f}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mostrar alertas sobre días óptimos de compra (esperar al día después de la fecha de corte)
    cutoff_tips = [r for r in recommendations if r.wait_for_cutoff_tip]
    for tip_card in cutoff_tips:
        st.markdown(
            f"""
            <div style="background:rgba(245,158,11,0.14); border:1px solid rgba(245,158,11,0.45);
                        border-radius:10px; padding:10px 12px; margin-bottom:10px;">
                <div style="font-size:0.76rem; font-weight:700; color:#F59E0B;">
                    ⚡ ALERTA DE DÍA ÓPTIMO DE COMPRA · {tip_card.card_name}
                </div>
                <div style="font-size:0.80rem; color:#FDE68A; margin-top:2px;">
                    {tip_card.wait_for_cutoff_tip}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if len(recommendations) > 1:
        with st.expander("📊 Ver ranking comparativo de todas tus tarjetas", expanded=True):
            for idx, rec in enumerate(recommendations, start=1):
                status_icon = "🥇" if idx == 1 else ("🥈" if idx == 2 else "💳")
                score_txt = f"{rec.total_score:.1f} pts" if rec.is_eligible else "Excede línea"
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; align-items:center;
                                background:#121722; border:1px solid #263044; border-radius:10px;
                                padding:10px 12px; margin-bottom:6px;">
                        <div>
                            <div style="font-size:0.88rem; font-weight:700; color:#F8FAFC;">
                                {status_icon} #{idx} {rec.card_name} <span style="font-size:0.75rem; color:#94A3B8;">({rec.optimal_window_badge})</span>
                            </div>
                            <div style="font-size:0.74rem; color:#94A3B8;">
                                {rec.float_days}d libres (paga {rec.payment_due_date.strftime('%d/%b')}) ·
                                Cashback +${rec.cashback_earned:,.2f} · Utilización {rec.utilization_after_pct:.1f}%
                            </div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-family:'JetBrains Mono', monospace; font-size:0.95rem; font-weight:700; color:#10B981;">
                                {score_txt}
                            </div>
                            <div style="font-size:0.68rem; color:#64748B;">/ 100</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


@st.fragment
def _render_amortization_and_minimum_payment_simulator_fragment(
    credit_cards: List[Dict[str, Any]],
    currency: str,
) -> None:
    """
    Simulador Inteligente 2:
    - Estimación del pago para no generar intereses
    - Costo financiero de pagar solo el mínimo
    - Proyección de amortización mes a mes con gráfica de capital vs intereses
    """
    st.markdown(
        """
        <div style="background:rgba(59,130,246,0.10); border:1px solid rgba(59,130,246,0.35);
                    border-radius:12px; padding:12px 14px; margin:16px 0 12px 0;">
            <div style="font-size:0.78rem; font-weight:700; color:#38BDF8; text-transform:uppercase; letter-spacing:0.05em;">
                📉 Simulador de Pago para No Generar Intereses, Pago Mínimo y Amortización
            </div>
            <div style="font-size:0.82rem; color:#94A3B8; margin-top:2px;">
                Conoce el costo real del interés compuesto en tu TDC y proyecta tu tabla de liquidación.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    default_name = "Tarjeta Simulada"
    default_debt = 18500.0
    default_cat = 54.0
    default_min_pct = 5.0

    if credit_cards:
        cc_map = {
            str(c["id"]): (
                f"💳 {c['name']} (Deuda: ${float(c.get('current_balance') or 0):,.2f} · "
                f"CAT: {float(c.get('interest_rate_cat') or 50.0):.1f}%)"
            )
            for c in credit_cards
        }
        selected_cc_id = st.selectbox(
            "Seleccionar tarjeta de tu billetera para precargar datos",
            options=list(cc_map.keys()),
            format_func=lambda k: cc_map[k],
            key="sim_amort_cc_select",
        )
        chosen_cc = next((c for c in credit_cards if str(c["id"]) == selected_cc_id), credit_cards[0])
        default_name = str(chosen_cc.get("name", "TDC"))
        cc_debt = float(chosen_cc.get("current_balance") or 0.0)
        default_debt = cc_debt if cc_debt > 0 else 15000.0
        default_cat = float(chosen_cc.get("interest_rate_cat") or 54.0)
        default_min_pct = float(chosen_cc.get("minimum_payment_pct") or 5.0)

    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        balance_input = st.number_input(
            f"Saldo / Deuda a simular ({currency})",
            min_value=100.0,
            value=float(default_debt),
            step=500.0,
            format="%.2f",
            key="sim_amort_balance",
        )
    with col_p2:
        cat_input = st.number_input(
            "Tasa Anual / CAT (%)",
            min_value=0.0,
            max_value=200.0,
            value=float(default_cat),
            step=1.0,
            format="%.1f",
            key="sim_amort_cat",
        )
    with col_p3:
        months_input = st.slider(
            "Plazo meta de liquidación (meses)",
            min_value=1,
            max_value=36,
            value=6,
            step=1,
            key="sim_amort_months",
        )

    sim = simulate_credit_card_amortization(
        card_name=default_name,
        current_balance=float(balance_input),
        annual_cat_pct=float(cat_input),
        minimum_payment_pct=float(default_min_pct),
        plan_months=int(months_input),
    )

    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        render_kpi_card(
            label="Pago para No Generar Intereses",
            value=f"${sim.no_interest_payment:,.2f}",
            delta_text="$0.00 de interés (100% al corte)",
            delta_positive=True,
            accent_color="#10B981",
        )
    with col_res2:
        render_kpi_card(
            label=f"Si solo pagas el Mínimo (${sim.minimum_payment:,.0f})",
            value=f"+${sim.first_month_interest_if_minimum:,.2f}/mes",
            delta_text=(
                f"Tardarías {sim.months_if_minimum_only} meses · "
                f"Interés total: ${sim.total_interest_if_minimum_only:,.0f}"
            ),
            delta_positive=False,
            accent_color="#EF4444",
        )
    with col_res3:
        render_kpi_card(
            label=f"Plan en {sim.plan_months} Meses (Cuota Fija)",
            value=f"${sim.plan_monthly_payment:,.2f}/mes",
            delta_text=f"Interés total: ${sim.plan_total_interest:,.2f} (Total: ${sim.plan_total_paid:,.0f})",
            delta_positive=(sim.plan_total_interest < sim.total_interest_if_minimum_only),
            accent_color="#38BDF8",
        )

    if sim.schedule:
        months_x = [f"Mes {row['month']}" for row in sim.schedule]
        remaining_y = [float(row["end_balance"]) for row in sim.schedule]
        interest_y = [float(row["interest"]) for row in sim.schedule]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=months_x,
                y=remaining_y,
                name="Saldo Insoluto Restante",
                marker_color="#38BDF8",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=months_x,
                y=interest_y,
                mode="lines+markers",
                name="Interés Mensual Pagado",
                line=dict(color="#EF4444", width=2.5),
            )
        )
        apply_mobile_dark_layout(fig, height=230)
        render_mobile_plotly(fig, key="plotly_amortization_curve")

        with st.expander("📋 Ver tabla de amortización mes a mes"):
            st.dataframe(
                [
                    {
                        "Mes": r["month"],
                        "Saldo Inicial": f"${r['start_balance']:,.2f}",
                        "Pago Mensual": f"${r['payment']:,.2f}",
                        "Interés": f"${r['interest']:,.2f}",
                        "Abono a Capital": f"${r['principal']:,.2f}",
                        "Saldo Final": f"${r['end_balance']:,.2f}",
                    }
                    for r in sim.schedule
                ],
                use_container_width=True,
                hide_index=True,
            )


# =====================================================================
# VISTA PRINCIPAL DE FINANZAS PERSONALES (SPRINT 4)
# =====================================================================


def render_finance_view() -> None:
    """Renderiza el Pilar 2 completo: Billetera Apple Wallet, Simulador TDC, Flujo y Calendario."""
    user_id = get_current_user_id()
    access_token = st.session_state.get("access_token") or ""
    profile = st.session_state.get("user_profile") or {}
    currency = profile.get("preferred_currency", "MXN")

    if not user_id or not access_token:
        st.warning("Inicia sesión para acceder a tu Billetera y Simulador Financiero.")
        return

    render_pillar_header(
        title="Finanzas & Billetera Inteligente",
        subtitle="Apple Wallet Digital · Simulador de Tarjetas · Calendario de Liquidez",
        accent_hex=PALETTE["accent_finance"],
        badge_text=f"💳 Pilar 2 · {currency}",
    )

    accounts = fetch_finance_accounts(user_id, access_token)
    categories = fetch_finance_categories(user_id, access_token)
    transactions = fetch_finance_transactions(user_id, access_token, days_back=120)
    subscriptions = fetch_finance_subscriptions(user_id, access_token)

    today = date.today()
    budget_summary = calculate_cashflow_and_budget_summary(
        accounts=accounts,
        categories=categories,
        transactions=transactions,
        reference_date=today,
    )

    credit_cards = [a for a in accounts if str(a.get("account_type")) == "credit_card"]
    liquid_accounts = [a for a in accounts if str(a.get("account_type")) != "credit_card"]

    # ── Barra Superior de Acciones Rápidas (Ergonomía One-Handed) ──
    btn_c1, btn_c2, btn_c3 = st.columns([1.25, 1.15, 1.0])
    with btn_c1:
        if st.button("➕ Movimiento", type="primary", use_container_width=True, key="fin_top_new_tx"):
            _open_new_transaction_dialog(user_id, currency, accounts, categories, budget_summary)
    with btn_c2:
        if st.button("💳 + Cuenta / TDC", use_container_width=True, key="fin_top_new_acc"):
            _open_new_account_dialog(user_id, currency)
    with btn_c3:
        if st.button("🔄 + Suscripción", use_container_width=True, key="fin_top_new_sub"):
            _open_new_subscription_dialog(user_id, currency, accounts, categories)

    # Banner de generación rápida de Billetera Demo si aún no hay cuentas
    if not accounts:
        with st.container(border=True):
            st.markdown(
                """
                <div style="font-size:0.95rem; font-weight:700; color:#F8FAFC; margin-bottom:4px;">
                    👋 Tu Billetera Digital está vacía
                </div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-bottom:10px;">
                    Puedes agregar tus cuentas manualmente con el botón <b>💳 + Cuenta / TDC</b> o inicializar
                    en 1 toque una billetera de prueba con 1 Cuenta de Débito y 2 Tarjetas de Crédito con distintas
                    fechas de corte para probar de inmediato el Simulador Inteligente.
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "✨ Generar Billetera Demo (1 Débito + 2 TDC con distinto corte)",
                type="primary",
                use_container_width=True,
                key="fin_seed_demo_wallet",
            ):
                ok, msg = seed_sample_wallet_for_user(user_id)
                st.toast(msg, icon="💳")
                st.rerun()

    # ── Top 3 KPIs Globales del Pilar 2 ──
    total_liquid = float(budget_summary["liquid_balance"]) + float(budget_summary["investment_balance"])
    total_budget = float(budget_summary["total_monthly_budget"])
    month_exp = float(budget_summary["month_expenses"])
    budget_used_pct = round((month_exp / total_budget) * 100.0, 1) if total_budget > 0 else 0.0
    cc_debt = float(budget_summary["cc_debt"])
    cc_limit = float(budget_summary["cc_total_limit"])
    util_pct = round((cc_debt / cc_limit) * 100.0, 1) if cc_limit > 0 else 0.0

    kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
    with kpi_c1:
        render_kpi_card(
            label="Liquidez + Inversión",
            value=f"${total_liquid:,.2f}",
            delta_text=f"Patrimonio Neto: ${budget_summary['net_worth']:,.0f}",
            delta_positive=(float(budget_summary["net_worth"]) >= 0),
            accent_color=PALETTE["accent_finance"],
        )
    with kpi_c2:
        render_kpi_card(
            label="Gasto del Mes vs Presupuesto",
            value=f"${month_exp:,.2f}",
            delta_text=f"{budget_used_pct:.1f}% de ${total_budget:,.0f} ({currency})",
            delta_positive=(budget_used_pct <= 85.0),
            accent_color=(
                "#10B981"
                if budget_used_pct <= 85.0
                else ("#F59E0B" if budget_used_pct <= 100.0 else "#EF4444")
            ),
        )
    with kpi_c3:
        render_kpi_card(
            label="Deuda Total en TDC",
            value=f"${cc_debt:,.2f}",
            delta_text=f"Utilización global: {util_pct:.1f}% (Disp: ${budget_summary['cc_available']:,.0f})",
            delta_positive=(util_pct <= 30.0),
            accent_color="#10B981" if util_pct <= 30.0 else ("#F59E0B" if util_pct <= 70.0 else "#EF4444"),
        )

    tab_wallet, tab_flow, tab_calendar = st.tabs(
        [
            "💳 Billetera & Simulador TDC",
            "💸 Flujo & Presupuestos",
            "📅 Calendario Financiero",
        ]
    )

    # =================================================================
    # TAB 1: BILLETERA DIGITAL TIPO APPLE WALLET & SIMULADOR TDC
    # =================================================================
    with tab_wallet:
        st.markdown("#### 🪪 Tarjetas de Crédito (Apple Wallet View)")
        if credit_cards:
            cols_cc = st.columns(min(2, len(credit_cards))) if len(credit_cards) > 1 else [st.container()]
            for idx, cc in enumerate(credit_cards):
                target_col = cols_cc[idx % len(cols_cc)]
                with target_col:
                    c_day = int(cc.get("cutoff_day") or 15)
                    p_day = int(cc.get("payment_due_day") or 5)
                    cycle_dates = calculate_card_cycle_dates(
                        cutoff_day=c_day,
                        payment_due_day=p_day,
                        purchase_date=today,
                    )
                    render_credit_card_widget(
institution_name=str(cc.get("institution_name", "Banco")),
alias=str(cc.get("name", "TDC")),
last_four_digits=str(cc.get("last_four_digits", "0000")),
current_balance=float(cc.get("current_balance") or 0.0),
credit_limit=float(cc.get("credit_limit") or 0.0),
cashback_pct=float(cc.get("cashback_pct") or 0.0),
cutoff_day=c_day,
payment_due_day=p_day,
days_until_cutoff=cycle_dates.days_until_cutoff,
days_until_payment=cycle_dates.days_until_payment_due,
float_days_today=cycle_dates.float_days,
interest_rate_cat=float(cc.get("interest_rate_cat") or 0.0),
card_network=str(cc.get("card_network", "visa")),
gradient_theme=str(cc.get("card_gradient_theme", "indigo_neon")),
account_type="credit_card",
                    )
                    with st.expander(f"⚙️ Ajustar saldo o eliminar · {cc['name']}"):
                        new_bal = st.number_input(
                            f"Deuda actual en {cc['name']} ({currency})",
                            min_value=0.0,
                            value=float(cc.get("current_balance") or 0.0),
                            step=250.0,
                            key=f"cc_adj_bal_{cc['id']}",
                        )
                        c_b1, c_b2 = st.columns(2)
                        with c_b1:
                            if st.button("Actualizar deuda", key=f"cc_save_bal_{cc['id']}", use_container_width=True):
                                update_finance_account_balance(user_id, str(cc["id"]), float(new_bal))
                                st.toast("Saldo de tarjeta actualizado.", icon="✅")
                                st.rerun()
                        with c_b2:
                            if st.button("Eliminar TDC", key=f"cc_del_{cc['id']}", use_container_width=True):
                                delete_finance_account(user_id, str(cc["id"]))
                                st.rerun()
        else:
            st.info("No tienes tarjetas de crédito registradas todavía. Usa el botón superior «💳 + Cuenta / TDC».")

        if liquid_accounts:
            st.markdown("#### 🏦 Cuentas de Liquidez (Débito, Efectivo e Inversión)")
            cols_liq = st.columns(min(2, len(liquid_accounts))) if len(liquid_accounts) > 1 else [st.container()]
            for idx, l_acc in enumerate(liquid_accounts):
                with cols_liq[idx % len(cols_liq)]:
                    render_credit_card_widget(
                        institution_name=str(l_acc.get("institution_name", "Banco")),
                        alias=str(l_acc.get("name", "Cuenta")),
                        last_four_digits=str(l_acc.get("last_four_digits", "0000")),
                        current_balance=float(l_acc.get("current_balance") or 0.0),
                        card_network=str(l_acc.get("card_network", "visa")),
                        gradient_theme=str(l_acc.get("card_gradient_theme", "deep_blue")),
                        account_type=str(l_acc.get("account_type", "debit")),
                    )
                    with st.expander(f"⚙️ Ajustar saldo · {l_acc['name']}"):
                        new_lbal = st.number_input(
                            f"Saldo disponible ({currency})",
                            min_value=0.0,
                            value=float(l_acc.get("current_balance") or 0.0),
                            step=500.0,
                            key=f"liq_adj_bal_{l_acc['id']}",
                        )
                        if st.button("Guardar saldo", key=f"liq_save_bal_{l_acc['id']}", use_container_width=True):
                            update_finance_account_balance(user_id, str(l_acc["id"]), float(new_lbal))
                            st.toast("Saldo actualizado.", icon="✅")
                            st.rerun()

        st.divider()
        _render_card_advisor_simulator_fragment(
            accounts=accounts,
            categories=categories,
            budget_summary=budget_summary,
            currency=currency,
        )

        _render_amortization_and_minimum_payment_simulator_fragment(
            credit_cards=credit_cards,
            currency=currency,
        )

    # =================================================================
    # TAB 2: FLUJO DE EFECTIVO, PRESUPUESTOS Y BITÁCORA DE MOVIMIENTOS
    # =================================================================
    with tab_flow:
        st.markdown("#### 📊 Cumplimiento de Presupuesto Mensual por Categoría")
        cat_breakdown = budget_summary.get("categories_breakdown") or []

        if cat_breakdown:
            active_cat_rows = [
                r for r in cat_breakdown if float(r["spent"]) > 0 or float(r["budget_limit"]) > 0
            ][:8]
            if active_cat_rows:
                fig_cat = go.Figure()
                fig_cat.add_trace(
                    go.Bar(
                        y=[f"{r['icon']} {r['name']}" for r in reversed(active_cat_rows)],
                        x=[float(r["spent"]) for r in reversed(active_cat_rows)],
                        orientation="h",
                        name="Gastado Mes Actual",
                        marker_color=[
                            "#EF4444"
                            if r["is_exceeded"]
                            else ("#F59E0B" if r["is_over_85"] else "#10B981")
                            for r in reversed(active_cat_rows)
                        ],
                    )
                )
                fig_cat.add_trace(
                    go.Bar(
                        y=[f"{r['icon']} {r['name']}" for r in reversed(active_cat_rows)],
                        x=[float(r["budget_limit"]) for r in reversed(active_cat_rows)],
                        orientation="h",
                        name="Presupuesto Límite",
                        marker_color="rgba(148, 163, 184, 0.25)",
                    )
                )
                fig_cat.update_layout(barmode="overlay")
                apply_mobile_dark_layout(fig_cat, height=260)
                render_mobile_plotly(fig_cat, key="plotly_finance_cat_budget")

            for row in cat_breakdown:
                spent = float(row["spent"])
                limit_v = float(row["budget_limit"])
                pct_v = float(row["usage_pct"])
                if spent == 0 and limit_v == 0:
                    continue
                if row["is_exceeded"]:
                    bar_col = "#EF4444"
                    badge_alert = "🚨 Excedido (>100%)"
                elif row["is_over_85"]:
                    bar_col = "#F59E0B"
                    badge_alert = "⚠️ Alerta (>85%)"
                else:
                    bar_col = "#10B981"
                    badge_alert = "✅ Saludable"

                st.markdown(
                    f"""
                    <div style="background:#121722; border:1px solid #263044; border-radius:10px;
                                padding:10px 12px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span style="font-size:0.86rem; font-weight:700; color:#F8FAFC;">
                                {row['icon']} {row['name']}
                            </span>
                            <span style="font-size:0.74rem; color:{bar_col}; font-weight:700;">
                                {badge_alert} · ${spent:,.0f} / ${limit_v:,.0f} ({pct_v:.1f}%)
                            </span>
                        </div>
                        <div style="width:100%; height:7px; background:rgba(255,255,255,0.08); border-radius:999px; overflow:hidden;">
                            <div style="width:{min(100.0, pct_v):.1f}%; height:100%; background:{bar_col}; border-radius:999px;"></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.expander("✏️ Configurar límites de presupuesto mensual por categoría"):
                expense_categories = [c for c in categories if str(c.get("kind", "expense")) == "expense"]
                for ec in expense_categories:
                    c_col1, c_col2 = st.columns([2, 1])
                    with c_col1:
                        new_limit = st.number_input(
                            f"{ec.get('icon', '💸')} {ec.get('name')} ({currency}/mes)",
                            min_value=0.0,
                            value=float(ec.get("monthly_budget_limit") or 0.0),
                            step=500.0,
                            key=f"edit_cat_limit_{ec['id']}",
                        )
                    with c_col2:
                        st.write("")
                        if st.button("Guardar", key=f"save_cat_limit_{ec['id']}", use_container_width=True):
                            update_category_budget_limit(user_id, str(ec["id"]), float(new_limit))
                            st.toast(f"Presupuesto de {ec.get('name')} actualizado.", icon="✅")
                            st.rerun()

        st.divider()
        st.markdown("#### 🧾 Historial Reciente de Transacciones")
        tx_filter = (
            st.segmented_control(
                "Filtrar por tipo",
                options=["ALL", "expense", "income", "cc_payment", "transfer"],
                default="ALL",
                format_func=lambda f: "Todos" if f == "ALL" else TX_TYPE_LABELS.get(f, f),
                key="fin_tx_history_filter",
            )
            or "ALL"
        )

        acc_by_id = {str(a["id"]): a for a in accounts}
        cat_by_id = {str(c["id"]): c for c in categories}

        filtered_txs = [
            t for t in transactions if tx_filter == "ALL" or str(t.get("tx_type")) == tx_filter
        ]

        if not filtered_txs:
            st.caption("No hay movimientos registrados para este filtro.")
        else:
            for tx in filtered_txs[:25]:
                tx_id = str(tx["id"])
                t_type = str(tx.get("tx_type", "expense"))
                amt = float(tx.get("amount") or 0.0)
                acc_obj = acc_by_id.get(str(tx.get("account_id")), {})
                cat_obj = cat_by_id.get(str(tx.get("category_id")), {})
                acc_name = acc_obj.get("name", "Cuenta")
                cat_name = cat_obj.get("name", "Transferencia / Pago")
                cat_icon = cat_obj.get("icon", "💳" if t_type == "cc_payment" else "🔄")
                concept = tx.get("merchant_or_concept") or cat_name
                msi = int(tx.get("msi_months") or 1)
                tags = tx.get("tags") or []
                cb_tx = float(tx.get("cashback_earned") or 0.0)

                amt_color = (
                    "#10B981"
                    if t_type == "income"
                    else ("#38BDF8" if t_type in ("cc_payment", "transfer") else "#F8FAFC")
                )
                amt_prefix = "+" if t_type == "income" else ("⇄ " if t_type in ("cc_payment", "transfer") else "-")
                msi_badge = (
                    f"<span style='background:#3B82F622; color:#60A5FA; border:1px solid #3B82F655; "
                    f"padding:1px 6px; border-radius:999px; font-size:0.68rem; margin-left:6px;'>{msi} MSI</span>"
                    if msi > 1
                    else ""
                )
                cb_badge = (
                    f"<span style='background:#10B98122; color:#10B981; border:1px solid #10B98155; "
                    f"padding:1px 6px; border-radius:999px; font-size:0.68rem; margin-left:6px;'>+${cb_tx:,.2f} CB</span>"
                    if cb_tx > 0
                    else ""
                )
                tags_html = "".join(
                    f"<span style='background:#1E293B; color:#94A3B8; padding:1px 6px; "
                    f"border-radius:999px; font-size:0.66rem; margin-right:4px;'>#{tg}</span>"
                    for tg in tags
                )

                col_tx_card, col_tx_del = st.columns([5.5, 1])
                with col_tx_card:
                    st.markdown(
                        f"""
                        <div style="background:#121722; border:1px solid #263044; border-radius:10px;
                                    padding:10px 12px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <div style="font-size:0.88rem; font-weight:700; color:#F8FAFC;">
                                    {cat_icon} {concept} {msi_badge} {cb_badge}
                                </div>
                                <div style="font-size:0.74rem; color:#94A3B8; margin-top:2px;">
                                    {tx.get('tx_date')} · <b>{acc_name}</b> · {cat_name}
                                </div>
                                <div style="margin-top:4px;">{tags_html}</div>
                            </div>
                            <div style="font-family:'JetBrains Mono', monospace; font-size:0.98rem; font-weight:700; color:{amt_color};">
                                {amt_prefix}${amt:,.2f}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_tx_del:
                    if st.button("🗑️", key=f"del_tx_{tx_id}", help="Eliminar movimiento"):
                        delete_finance_transaction(user_id, tx_id)
                        st.toast("Movimiento eliminado.", icon="🗑️")
                        st.rerun()

    # =================================================================
    # TAB 3: CALENDARIO FINANCIERO INTERACTIVO Y SUSCRIPCIONES
    # =================================================================
    with tab_calendar:
        st.markdown("#### 🗓️ Calendario Financiero Interactivo")
        st.caption(
            "Mapea automáticamente: 🔵 Fechas de Corte TDC · 🔴 Fechas Límite de Pago · "
            "🟣 Suscripciones Recurrentes · 🟢 Ingresos."
        )

        col_ym1, col_ym2 = st.columns(2)
        with col_ym1:
            cal_month = st.selectbox(
                "Mes",
                options=list(range(1, 13)),
                index=today.month - 1,
                format_func=lambda m: SPANISH_MONTHS[m - 1],
                key="fin_cal_month",
            )
        with col_ym2:
            cal_year = st.selectbox(
                "Año",
                options=[today.year - 1, today.year, today.year + 1],
                index=1,
                key="fin_cal_year",
            )

        cal_data = build_financial_calendar_events(
            accounts=accounts,
            subscriptions=subscriptions,
            transactions=transactions,
            year=int(cal_year),
            month=int(cal_month),
        )
        events_by_day: Dict[int, List[Dict[str, Any]]] = cal_data.get("events_by_day") or {}
        upcoming_14d: List[Dict[str, Any]] = cal_data.get("upcoming_14d") or []

        # Radar de próximos 14 días
        if upcoming_14d:
            st.markdown("##### ⚡ Radar de Vencimientos y Cortes (Próximos 14 Días)")
            for up in upcoming_14d[:5]:
                up_col = up.get("color", "#3B82F6")
                d_left = int(up.get("days_left") or 0)
                when_txt = "HOY" if d_left == 0 else f"En {d_left} día(s)"
                st.markdown(
                    f"""
                    <div style="background:#121722; border-left:4px solid {up_col}; border-top:1px solid #263044;
                                border-right:1px solid #263044; border-bottom:1px solid #263044;
                                border-radius:10px; padding:8px 12px; margin-bottom:6px;
                                display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-size:0.70rem; font-weight:700; color:{up_col};">{up['badge']} · {when_txt}</span>
                            <div style="font-size:0.86rem; font-weight:700; color:#F8FAFC;">{up['title']}</div>
                        </div>
                        <div style="font-family:'JetBrains Mono', monospace; font-size:0.88rem; font-weight:700; color:#F8FAFC;">
                            ${float(up.get('amount') or 0):,.2f}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Renderizar Grid Mensual de 7 columnas (Lun a Dom)
        cal_matrix = calendar.monthcalendar(int(cal_year), int(cal_month))
        weekdays_header = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

        grid_html = [
            "<div style='display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); gap:5px; margin:10px 0 14px 0;'>"
        ]
        for wd in weekdays_header:
            grid_html.append(
                f"<div style='text-align:center; font-size:0.70rem; font-weight:700; color:#94A3B8; padding:4px 0;'>{wd}</div>"
            )

        for week in cal_matrix:
            for day_num in week:
                if day_num == 0:
                    grid_html.append(
                        "<div style='background:rgba(18,23,34,0.35); border:1px dashed #1E293B; border-radius:8px; min-height:66px;'></div>"
                    )
                else:
                    is_today = (
                        day_num == today.day
                        and int(cal_month) == today.month
                        and int(cal_year) == today.year
                    )
                    day_evs = events_by_day.get(day_num, [])
                    border_col = "#3B82F6" if is_today else ("#334155" if day_evs else "#1E293B")
                    bg_col = "rgba(59,130,246,0.12)" if is_today else "#121722"

                    pills_html = ""
                    for ev in day_evs[:3]:
                        ev_color = ev.get("color", "#94A3B8")
                        ev_badge = ev.get("badge", "•")
                        pills_html += (
                            f"<div style='font-size:0.58rem; background:{ev_color}22; color:{ev_color}; "
                            f"border-left:2px solid {ev_color}; border-radius:3px; padding:1px 3px; "
                            f"margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>"
                            f"{ev_badge}</div>"
                        )
                    if len(day_evs) > 3:
                        pills_html += (
                            f"<div style='font-size:0.58rem; color:#94A3B8; margin-top:1px;'>+{len(day_evs) - 3} más</div>"
                        )

                    grid_html.append(
                        f"<div style='background:{bg_col}; border:1px solid {border_col}; border-radius:8px; "
                        f"padding:4px 5px; min-height:66px; display:flex; flex-direction:column; justify-content:space-between;'>"
                        f"<div style='font-family:JetBrains Mono, monospace; font-size:0.72rem; font-weight:700; "
                        f"color:{'#60A5FA' if is_today else '#F8FAFC'};'>{day_num}</div>"
                        f"<div>{pills_html}</div>"
                        f"</div>"
                    )
        grid_html.append("</div>")
        st.markdown("".join(grid_html), unsafe_allow_html=True)

        # Lista detallada cronológica de eventos del mes seleccionado
        st.markdown(f"#### 📌 Agenda del Mes ({SPANISH_MONTHS[int(cal_month) - 1]} {cal_year})")
        flat_month_events = []
        for d_num in sorted(events_by_day.keys()):
            for ev in events_by_day[d_num]:
                flat_month_events.append(ev)

        if not flat_month_events:
            st.caption("No hay cortes de tarjeta ni pagos recurrentes programados en este mes.")
        else:
            for ev in flat_month_events:
                ev_col = ev.get("color", "#10B981")
                amt_val = float(ev.get("amount") or 0.0)
                st.markdown(
                    f"""
                    <div style="background:#121722; border-left:4px solid {ev_col}; border-top:1px solid #263044;
                                border-right:1px solid #263044; border-bottom:1px solid #263044;
                                border-radius:10px; padding:10px 12px; margin-bottom:7px;
                                display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-size:0.86rem; font-weight:700; color:#F8FAFC;">
                                {ev['badge']} · {ev['title']}
                            </div>
                            <div style="font-size:0.74rem; color:#94A3B8;">
                                📅 {ev['event_date'].strftime('%d/%b/%Y')} · {ev['subtitle']}
                            </div>
                        </div>
                        <div style="font-family:'JetBrains Mono', monospace; font-size:0.88rem; font-weight:700; color:{ev_col};">
                            ${amt_val:,.2f}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.divider()
        st.markdown("#### 🔄 Suscripciones y Cargos Recurrentes Activos")
        if not subscriptions:
            st.caption("Aún no tienes suscripciones activas. Usa el botón «🔄 + Suscripción» para programarlas.")
        else:
            monthly_fixed_total = 0.0
            for s in subscriptions:
                amt_s = float(s.get("amount") or 0.0)
                cyc_s = str(s.get("billing_cycle", "monthly"))
                if cyc_s == "monthly":
                    monthly_fixed_total += amt_s
                elif cyc_s == "yearly":
                    monthly_fixed_total += amt_s / 12.0
                elif cyc_s == "weekly":
                    monthly_fixed_total += amt_s * 4.33

            st.markdown(
                f"""
                <div style="background:rgba(139,92,246,0.12); border:1px solid rgba(139,92,246,0.35);
                            border-radius:10px; padding:10px 12px; margin-bottom:10px;
                            display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.82rem; color:#DDD6FE;">Costo mensualizado de suscripciones fijas:</span>
                    <span style="font-family:'JetBrains Mono', monospace; font-size:0.95rem; font-weight:700; color:#A78BFA;">
                        ${monthly_fixed_total:,.2f} / mes (${monthly_fixed_total * 12:,.0f} / año)
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            for sub in subscriptions:
                sub_id = str(sub["id"])
                s_name = str(sub.get("service_name", "Suscripción"))
                s_amt = float(sub.get("amount") or 0.0)
                s_day = int(sub.get("billing_day_of_month") or 1)
                c1, c2 = st.columns([4.5, 1])
                with c1:
                    st.markdown(
                        f"""
                        <div style="background:#121722; border:1px solid #263044; border-radius:10px;
                                    padding:9px 12px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <div style="font-size:0.86rem; font-weight:700; color:#F8FAFC;">🟣 {s_name}</div>
                                <div style="font-size:0.74rem; color:#94A3B8;">Día {s_day} de cada mes ({BILLING_CYCLE_LABELS.get(str(sub.get('billing_cycle')), 'Mensual')})</div>
                            </div>
                            <div style="font-family:'JetBrains Mono', monospace; font-size:0.92rem; font-weight:700; color:#A78BFA;">
                                ${s_amt:,.2f}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("🗑️", key=f"del_sub_{sub_id}", help="Cancelar suscripción"):
                        delete_finance_subscription(user_id, sub_id)
                        st.rerun()
