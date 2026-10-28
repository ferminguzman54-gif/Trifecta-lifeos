"""
Motor Financiero y Recomendador Inteligente de Tarjetas de Crédito (TDC):
- Cálculo exacto de fechas de corte, fechas límite de pago y días de financiamiento (float_days).
- Algoritmo de Score de Conveniencia (0–100 puntos: 45% Float, 25% Cashback, 20% Utilización, 10% Presupuesto).
- Simulador de Pago para no generar intereses, costo financiero de pago mínimo y proyección de amortización.
- Generador de eventos del Calendario Financiero y operaciones CRUD con actualización automática de saldos.
Implementado según 01_PRD (§3), 02_TRD (§5.2), 03_Appflow (§5) y Sprint 4.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
import math
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from src.auth.supabase_client import get_supabase_client
from src.models.finance_models import (
    AmortizationSimulation,
    CardAdvisorRecommendation,
    CardCycleDates,
    FinanceAccountModel,
    FinanceCategoryModel,
    FinanceSubscriptionModel,
    FinanceTransactionModel,
)


# ============================================================================
# 1. CÁLCULO EXACTO DE CICLO DE FACTURACIÓN, CORTE, PAGO Y DÍAS DE FINANCIAMIENTO
# ============================================================================

def _safe_date_in_month(year: int, month: int, day: int) -> date:
    """Construye un objeto date ajustando días 29-31 al último día válido del mes."""
    last_day = calendar.monthrange(year, month)[1]
    clamped_day = max(1, min(int(day), last_day))
    return date(year, month, clamped_day)


def _next_year_month(year: int, month: int) -> Tuple[int, int]:
    """Retorna (año, mes) del mes inmediato siguiente."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def calculate_card_cycle_dates(
    cutoff_day: int,
    payment_due_day: int,
    purchase_date: Optional[date] = None,
) -> CardCycleDates:
    """
    Calcula las fechas exactas de corte y límite de pago para una compra realizada en `purchase_date`
    según 02_TRD_Requisitos_Tecnicos.md (§5.2):
    1. Si purchase_date.day <= cutoff_day, la compra entra en el corte del mes en curso.
    2. Si purchase_date.day > cutoff_day, la compra entra en el corte del mes siguiente.
    3. La fecha límite de pago (due_date) es el próximo payment_due_day posterior al corte
       (típicamente ~20 días después del corte).
    4. float_days = (due_date - purchase_date).days.
    """
    ref_date = purchase_date or date.today()
    c_day = max(1, min(31, int(cutoff_day or 15)))
    p_day = max(1, min(31, int(payment_due_day or 5)))

    this_month_cutoff = _safe_date_in_month(ref_date.year, ref_date.month, c_day)
    if ref_date <= this_month_cutoff:
        statement_cutoff_date = this_month_cutoff
    else:
        ny, nm = _next_year_month(ref_date.year, ref_date.month)
        statement_cutoff_date = _safe_date_in_month(ny, nm, c_day)

    # Determinar la fecha límite de pago correspondiente a ese corte (mínimo 12 días después del corte)
    same_month_due = _safe_date_in_month(
        statement_cutoff_date.year,
        statement_cutoff_date.month,
        p_day,
    )
    if same_month_due > statement_cutoff_date and (same_month_due - statement_cutoff_date).days >= 12:
        payment_due_date = same_month_due
    else:
        due_y, due_m = _next_year_month(statement_cutoff_date.year, statement_cutoff_date.month)
        payment_due_date = _safe_date_in_month(due_y, due_m, p_day)

    float_days = max(1, (payment_due_date - ref_date).days)
    days_until_cutoff = max(0, (statement_cutoff_date - ref_date).days)

    # Calcular también cuántos días faltan para la próxima fecha de pago calendario desde hoy
    this_month_pay = _safe_date_in_month(ref_date.year, ref_date.month, p_day)
    if this_month_pay >= ref_date:
        next_calendar_pay = this_month_pay
    else:
        py, pm = _next_year_month(ref_date.year, ref_date.month)
        next_calendar_pay = _safe_date_in_month(py, pm, p_day)
    days_until_payment_due = max(0, (next_calendar_pay - ref_date).days)

    optimal_window = float_days >= 38
    if float_days >= 40:
        window_badge = "🔥 Ventana Óptima (Recién cortó)"
    elif float_days >= 28:
        window_badge = "✅ Financiamiento Medio"
    else:
        window_badge = "⚠️ Próxima a cortar"

    # Alerta sobre días óptimos de compra si faltan <= 5 días para el corte
    wait_tip: Optional[str] = None
    if days_until_cutoff <= 5:
        day_after_cutoff = statement_cutoff_date + timedelta(days=1)
        after_cut_y, after_cut_m = _next_year_month(statement_cutoff_date.year, statement_cutoff_date.month)
        next_stmt_cutoff = _safe_date_in_month(after_cut_y, after_cut_m, c_day)
        same_m_due_next = _safe_date_in_month(next_stmt_cutoff.year, next_stmt_cutoff.month, p_day)
        if same_m_due_next > next_stmt_cutoff and (same_m_due_next - next_stmt_cutoff).days >= 12:
            next_due_date = same_m_due_next
        else:
            ny2, nm2 = _next_year_month(next_stmt_cutoff.year, next_stmt_cutoff.month)
            next_due_date = _safe_date_in_month(ny2, nm2, p_day)
        future_float = (next_due_date - day_after_cutoff).days
        wait_days = days_until_cutoff + 1
        wait_tip = (
            f"💡 Si esperas {wait_days} día(s) al {day_after_cutoff.strftime('%d/%m')} (día posterior al corte), "
            f"ganarás {future_float} días sin intereses en lugar de {float_days} días."
        )

    return CardCycleDates(
        cutoff_day=c_day,
        payment_due_day=p_day,
        statement_cutoff_date=statement_cutoff_date,
        payment_due_date=payment_due_date,
        days_until_cutoff=days_until_cutoff,
        days_until_payment_due=days_until_payment_due,
        float_days=float_days,
        optimal_purchase_window=optimal_window,
        window_badge=window_badge,
        wait_for_cutoff_tip=wait_tip,
    )


def calculate_float_days(
    purchase_date: date,
    cutoff_day: int,
    payment_due_day: int,
) -> int:
    """Función directa que retorna los días naturales de financiamiento gratuito (float_days)."""
    return calculate_card_cycle_dates(
        cutoff_day=cutoff_day,
        payment_due_day=payment_due_day,
        purchase_date=purchase_date,
    ).float_days


# ============================================================================
# 2. ALGORITMO RECOMENDADOR "¿CON QUÉ TARJETA PAGO HOY?" (SCORE 0 A 100)
# ============================================================================

def evaluate_best_payment_cards(
    credit_cards: List[Dict[str, Any]],
    amount: float,
    purchase_date: Optional[date] = None,
    category_remaining_budget: Optional[float] = None,
) -> List[CardAdvisorRecommendation]:
    """
    Evalúa todas las tarjetas de crédito activas del usuario y las ordena mediante el
    Score de Conveniencia (0 a 100 puntos) definido en 01_PRD (§3.2) y 02_TRD (§5.2):
    - 45% Días de Financiamiento Gratuito (float_days / 50 * 45)
    - 25% Retorno por Cashback normalizado
    - 20% Salud de Utilización de Línea (óptimo <= 30%, descarta si > 100%)
    - 10% Impacto en Presupuesto Mensual de la Categoría
    """
    ref_date = purchase_date or date.today()
    purchase_amt = max(0.01, float(amount or 0.0))

    active_tcs = [
        c for c in credit_cards
        if str(c.get("account_type", "credit_card")) == "credit_card"
        and bool(c.get("is_active", True))
    ]
    if not active_tcs:
        return []

    max_cashback_pct = max(float(c.get("cashback_pct") or 0.0) for c in active_tcs)
    rem_budget = float(category_remaining_budget) if category_remaining_budget is not None else purchase_amt

    recommendations: List[CardAdvisorRecommendation] = []

    for card in active_tcs:
        cid = str(card.get("id", ""))
        cname = str(card.get("name", "TDC"))
        inst = str(card.get("institution_name", "Banco"))
        net = str(card.get("card_network", "visa"))
        last4 = str(card.get("last_four_digits", "0000"))
        theme = str(card.get("card_gradient_theme", "indigo_neon"))

        curr_bal = max(0.0, float(card.get("current_balance") or 0.0))
        limit = max(1.0, float(card.get("credit_limit") or 1.0))
        cb_pct = max(0.0, float(card.get("cashback_pct") or 0.0))
        cut_day = int(card.get("cutoff_day") or 15)
        pay_day = int(card.get("payment_due_day") or 5)

        cycle = calculate_card_cycle_dates(cut_day, pay_day, purchase_date=ref_date)
        float_days = cycle.float_days
        cb_earned = round(purchase_amt * (cb_pct / 100.0), 2)

        avail_before = max(0.0, limit - curr_bal)
        avail_after = limit - (curr_bal + purchase_amt)
        util_before_pct = round((curr_bal / limit) * 100.0, 1)
        new_utilization = (curr_bal + purchase_amt) / limit
        util_after_pct = round(new_utilization * 100.0, 1)

        # 1. Score Float (45 pts)
        score_float = round(min(float_days / 50.0, 1.0) * 45.0, 2)

        # 2. Score Cashback (25 pts)
        if max_cashback_pct > 0:
            score_cashback = round((cb_pct / max_cashback_pct) * 25.0, 2)
        else:
            score_cashback = 12.5

        # 4. Score Budget (10 pts)
        if rem_budget >= purchase_amt:
            score_budget = 10.0
        elif rem_budget <= 0:
            score_budget = 0.0
        else:
            score_budget = round(max(0.0, 10.0 * (rem_budget / purchase_amt)), 2)

        # 3. Score Utilization (20 pts) y verificación de límite disponible
        if new_utilization > 1.0:
            recommendations.append(
                CardAdvisorRecommendation(
                    account_id=cid,
                    card_name=cname,
                    institution_name=inst,
                    card_network=net,
                    last_four_digits=last4,
                    card_gradient_theme=theme,
                    total_score=-1.0,
                    is_eligible=False,
                    rejection_reason=f"Excede el crédito disponible (${avail_before:,.2f} disponibles).",
                    float_days=float_days,
                    statement_cutoff_date=cycle.statement_cutoff_date,
                    payment_due_date=cycle.payment_due_date,
                    cashback_pct=cb_pct,
                    cashback_earned=cb_earned,
                    current_balance=curr_bal,
                    credit_limit=limit,
                    available_credit_before=avail_before,
                    available_credit_after=avail_after,
                    utilization_before_pct=util_before_pct,
                    utilization_after_pct=util_after_pct,
                    score_float=score_float,
                    score_cashback=score_cashback,
                    score_utilization=0.0,
                    score_budget=score_budget,
                    budget_remaining_after=rem_budget - purchase_amt,
                    optimal_window_badge=cycle.window_badge,
                    wait_for_cutoff_tip=cycle.wait_for_cutoff_tip,
                )
            )
            continue

        if new_utilization <= 0.30:
            score_utilization = 20.0
        else:
            score_utilization = round(
                max(0.0, 20.0 * (1.0 - (new_utilization - 0.30) / 0.70)),
                2,
            )

        total_score = round(score_float + score_cashback + score_utilization + score_budget, 1)

        recommendations.append(
            CardAdvisorRecommendation(
                account_id=cid,
                card_name=cname,
                institution_name=inst,
                card_network=net,
                last_four_digits=last4,
                card_gradient_theme=theme,
                total_score=total_score,
                is_eligible=True,
                rejection_reason=None,
                float_days=float_days,
                statement_cutoff_date=cycle.statement_cutoff_date,
                payment_due_date=cycle.payment_due_date,
                cashback_pct=cb_pct,
                cashback_earned=cb_earned,
                current_balance=curr_bal,
                credit_limit=limit,
                available_credit_before=avail_before,
                available_credit_after=avail_after,
                utilization_before_pct=util_before_pct,
                utilization_after_pct=util_after_pct,
                score_float=score_float,
                score_cashback=score_cashback,
                score_utilization=score_utilization,
                score_budget=score_budget,
                budget_remaining_after=rem_budget - purchase_amt,
                optimal_window_badge=cycle.window_badge,
                wait_for_cutoff_tip=cycle.wait_for_cutoff_tip,
            )
        )

    recommendations.sort(key=lambda r: (r.is_eligible, r.total_score, r.float_days), reverse=True)
    return recommendations


# ============================================================================
# 3. SIMULADOR DE PAGO SIN INTERESES, COSTO DE PAGO MÍNIMO Y AMORTIZACIÓN
# ============================================================================

def simulate_credit_card_amortization(
    card_name: str,
    current_balance: float,
    annual_cat_pct: float = 48.0,
    minimum_payment_pct: float = 5.0,
    plan_months: int = 6,
) -> AmortizationSimulation:
    """
    Calcula para el saldo actual de una tarjeta de crédito:
    - Pago para no generar intereses (100% del saldo al corte).
    - Pago mínimo exigido y el costo financiero inmediato por intereses del primer mes.
    - Tiempo y costo total si solo se cubriera el pago mínimo.
    - Tabla de amortización proyectada a `plan_months` meses.
    """
    bal = max(0.0, round(float(current_balance or 0.0), 2))
    cat = max(0.0, float(annual_cat_pct or 0.0))
    min_pct = max(1.0, min(100.0, float(minimum_payment_pct or 5.0)))
    months = max(1, min(60, int(plan_months or 6)))

    monthly_rate = (cat / 100.0) / 12.0
    monthly_rate_pct = round(monthly_rate * 100.0, 2)

    if bal <= 0.0:
        return AmortizationSimulation(
            card_name=card_name,
            current_balance=0.0,
            annual_cat_pct=cat,
            monthly_rate_pct=monthly_rate_pct,
            no_interest_payment=0.0,
            minimum_payment=0.0,
            first_month_interest_if_minimum=0.0,
            months_if_minimum_only=0,
            total_interest_if_minimum_only=0.0,
            plan_months=months,
            plan_monthly_payment=0.0,
            plan_total_interest=0.0,
            plan_total_paid=0.0,
            schedule=[],
        )

    no_interest_payment = bal
    min_payment = round(min(bal, max(250.0, bal * (min_pct / 100.0))), 2)
    unpaid_after_min = max(0.0, bal - min_payment)
    first_month_interest = round(unpaid_after_min * monthly_rate, 2)

    # Simulación pagando únicamente el mínimo cada mes (acotado a 120 meses)
    sim_bal = bal
    min_months_count = 0
    min_total_interest = 0.0
    while sim_bal > 1.0 and min_months_count < 120:
        min_months_count += 1
        m_int = sim_bal * monthly_rate
        min_total_interest += m_int
        m_pay = max(250.0, (sim_bal + m_int) * (min_pct / 100.0))
        if m_pay <= m_int:
            m_pay = m_int + (sim_bal * 0.02)
        if m_pay >= sim_bal + m_int:
            sim_bal = 0.0
        else:
            sim_bal = (sim_bal + m_int) - m_pay

    # Tabla de amortización para liquidar en `plan_months` meses
    if months == 1 or monthly_rate <= 0.0:
        fixed_payment = bal / months
    else:
        fixed_payment = bal * (monthly_rate * ((1.0 + monthly_rate) ** months)) / (((1.0 + monthly_rate) ** months) - 1.0)
    fixed_payment = round(fixed_payment, 2)

    schedule: List[Dict[str, Any]] = []
    rem = bal
    total_plan_interest = 0.0
    for m in range(1, months + 1):
        start_b = rem
        interest_m = 0.0 if months == 1 else round(start_b * monthly_rate, 2)
        if m == months:
            payment_m = round(start_b + interest_m, 2)
            principal_m = round(start_b, 2)
            end_b = 0.0
        else:
            payment_m = fixed_payment
            principal_m = round(payment_m - interest_m, 2)
            end_b = max(0.0, round(start_b - principal_m, 2))
        total_plan_interest += interest_m
        rem = end_b
        schedule.append(
            {
                "month": m,
                "start_balance": round(start_b, 2),
                "payment": payment_m,
                "interest": interest_m,
                "principal": principal_m,
                "end_balance": end_b,
            }
        )

    total_plan_interest = round(total_plan_interest, 2)
    return AmortizationSimulation(
        card_name=card_name,
        current_balance=bal,
        annual_cat_pct=cat,
        monthly_rate_pct=monthly_rate_pct,
        no_interest_payment=no_interest_payment,
        minimum_payment=min_payment,
        first_month_interest_if_minimum=first_month_interest,
        months_if_minimum_only=min_months_count,
        total_interest_if_minimum_only=round(min_total_interest, 2),
        plan_months=months,
        plan_monthly_payment=fixed_payment,
        plan_total_interest=total_plan_interest,
        plan_total_paid=round(bal + total_plan_interest, 2),
        schedule=schedule,
    )


# ============================================================================
# ============================================================================
# 4. CALENDARIO FINANCIERO INTERACTIVO, FILTROS INTELIGENTES Y FLUJO DE CAJA
# ============================================================================

HOME_SERVICE_KEYWORDS: Tuple[str, ...] = (
    "internet",
    "fibra",
    "telmex",
    "izzi",
    "totalplay",
    "megacable",
    "starlink",
    "luz",
    "cfe",
    "electricidad",
    "agua",
    "gas",
    "renta",
    "alquiler",
    "hipoteca",
    "mantenimiento",
    "predial",
    "telefono",
    "teléfono",
    "hogar",
    "vivienda",
    "limpieza",
    "seguridad",
    "alarma",
    "servicio",
)


def is_home_service_item(service_name: str, category_name: str = "") -> bool:
    """Determina si una suscripción o cargo corresponde a un Servicio del Hogar."""
    combined = f"{service_name or ''} {category_name or ''}".lower()
    return any(kw in combined for kw in HOME_SERVICE_KEYWORDS)


def build_financial_calendar_events(
    accounts: List[Dict[str, Any]],
    subscriptions: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    year: Optional[int] = None,
    month: Optional[int] = None,
    categories: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Construye el mapa de eventos financieros del mes (y radar de próximos 14 días):
    - 🔵 Fechas de Corte de TDC
    - 🔴 Fechas Límite de Pago de TDC (con saldo actual a pagar)
    - 🟣 Suscripciones Recurrentes y 🏠 Servicios del Hogar
    - 🟢 Ingresos y Gastos registrados
    """
    today = date.today()
    y = int(year or today.year)
    m = int(month or today.month)
    days_in_month = calendar.monthrange(y, m)[1]

    cat_by_id: Dict[str, Dict[str, Any]] = {
        str(c["id"]): c for c in (categories or []) if c.get("id")
    }

    events_by_day: Dict[int, List[Dict[str, Any]]] = {d: [] for d in range(1, days_in_month + 1)}
    upcoming_14d: List[Dict[str, Any]] = []

    # 1. Eventos de Tarjetas de Crédito (Corte y Fecha Límite de Pago)
    for acc in accounts:
        if str(acc.get("account_type")) != "credit_card" or not bool(acc.get("is_active", True)):
            continue
        cname = str(acc.get("name", "TDC"))
        bal = float(acc.get("current_balance") or 0.0)
        cut_d = int(acc.get("cutoff_day") or 15)
        pay_d = int(acc.get("payment_due_day") or 5)

        cut_date_m = _safe_date_in_month(y, m, cut_d)
        events_by_day[cut_date_m.day].append(
            {
                "kind": "cutoff",
                "is_home_service": False,
                "badge": "🔵 Corte TDC",
                "color": "#3B82F6",
                "title": f"Corte · {cname}",
                "subtitle": "Al día siguiente inicia tu ventana de ~48 días sin intereses",
                "amount": bal,
                "event_date": cut_date_m,
            }
        )

        pay_date_m = _safe_date_in_month(y, m, pay_d)
        events_by_day[pay_date_m.day].append(
            {
                "kind": "payment_due",
                "is_home_service": False,
                "badge": "🔴 Pago Límite TDC",
                "color": "#EF4444",
                "title": f"Límite de Pago · {cname}",
                "subtitle": f"Pago para no generar intereses: ${bal:,.2f}",
                "amount": bal,
                "event_date": pay_date_m,
            }
        )

        # Evaluar radar de próximos 14 días desde hoy
        cycle = calculate_card_cycle_dates(cut_d, pay_d, purchase_date=today)
        if 0 <= cycle.days_until_cutoff <= 14:
            upcoming_14d.append(
                {
                    "kind": "cutoff",
                    "is_home_service": False,
                    "days_left": cycle.days_until_cutoff,
                    "event_date": cycle.statement_cutoff_date,
                    "badge": "🔵 Corte TDC",
                    "color": "#3B82F6",
                    "title": f"Corte de {cname}",
                    "amount": bal,
                }
            )
        if 0 <= cycle.days_until_payment_due <= 14:
            pay_dt = today + timedelta(days=cycle.days_until_payment_due)
            upcoming_14d.append(
                {
                    "kind": "payment_due",
                    "is_home_service": False,
                    "days_left": cycle.days_until_payment_due,
                    "event_date": pay_dt,
                    "badge": "🔴 Pago Límite TDC",
                    "color": "#EF4444",
                    "title": f"Pago sin intereses · {cname}",
                    "amount": bal,
                }
            )

    # 2. Eventos de Suscripciones Recurrentes y Servicios del Hogar
    for sub in subscriptions:
        if not bool(sub.get("is_active", True)):
            continue
        sname = str(sub.get("service_name", "Suscripción"))
        samt = float(sub.get("amount") or 0.0)
        bday = int(sub.get("billing_day_of_month") or 1)
        cat_obj = cat_by_id.get(str(sub.get("category_id") or ""), {})
        cat_name = str(cat_obj.get("name") or "")
        is_home = is_home_service_item(sname, cat_name)
        badge_lbl = "🏠 Servicio Hogar" if is_home else "🟣 Suscripción"
        ev_color = "#F59E0B" if is_home else "#8B5CF6"

        sub_date_m = _safe_date_in_month(y, m, bday)
        events_by_day[sub_date_m.day].append(
            {
                "kind": "subscription",
                "is_home_service": is_home,
                "badge": badge_lbl,
                "color": ev_color,
                "title": f"Cobro · {sname}",
                "subtitle": f"Cargo recurrente ({sub.get('billing_cycle', 'monthly')})"
                + (f" · {cat_name}" if cat_name else ""),
                "amount": samt,
                "event_date": sub_date_m,
            }
        )

        if 0 <= (sub_date_m - today).days <= 14:
            upcoming_14d.append(
                {
                    "kind": "subscription",
                    "is_home_service": is_home,
                    "days_left": (sub_date_m - today).days,
                    "event_date": sub_date_m,
                    "badge": badge_lbl,
                    "color": ev_color,
                    "title": f"Cargo recurrente · {sname}",
                    "amount": samt,
                }
            )

    # 3. Movimientos de Ingreso / Gasto del Hogar registrados en el mes
    for tx in transactions:
        raw_d = str(tx.get("tx_date") or "")[:10]
        try:
            tx_d = date.fromisoformat(raw_d)
        except ValueError:
            continue
        if tx_d.year == y and tx_d.month == m:
            tx_type = str(tx.get("tx_type", "expense"))
            amt = float(tx.get("amount") or 0.0)
            concept = str(tx.get("merchant_or_concept", "Movimiento"))
            cat_obj = cat_by_id.get(str(tx.get("category_id") or ""), {})
            cat_name = str(cat_obj.get("name") or "")
            if tx_type == "income":
                events_by_day[tx_d.day].append(
                    {
                        "kind": "income",
                        "is_home_service": False,
                        "badge": "🟢 Ingreso",
                        "color": "#10B981",
                        "title": concept,
                        "subtitle": f"+${amt:,.2f}",
                        "amount": amt,
                        "event_date": tx_d,
                    }
                )
            elif tx_type == "expense" and is_home_service_item(concept, cat_name):
                events_by_day[tx_d.day].append(
                    {
                        "kind": "home_service",
                        "is_home_service": True,
                        "badge": "🏠 Servicio Hogar",
                        "color": "#F59E0B",
                        "title": concept,
                        "subtitle": f"Gasto hogar · -${amt:,.2f}",
                        "amount": amt,
                        "event_date": tx_d,
                    }
                )

    upcoming_14d.sort(key=lambda x: int(x["days_left"]))
    return {
        "year": y,
        "month": m,
        "days_in_month": days_in_month,
        "events_by_day": events_by_day,
        "upcoming_14d": upcoming_14d,
    }


def filter_financial_calendar_events(
    cal_data: Dict[str, Any],
    filter_option: str = "Todos",
) -> Dict[str, Any]:
    """
    Filtra de forma instantánea los eventos del calendario financiero según la opción:
    [Todos, Solo Cortes TDC, Solo Fechas de Pago, Solo Suscripciones, Solo Servicios del Hogar].
    """
    mode = (filter_option or "Todos").strip()
    if mode == "Todos":
        return cal_data

    def _matches(ev: Dict[str, Any]) -> bool:
        kind = str(ev.get("kind", ""))
        is_home = bool(ev.get("is_home_service", False)) or kind == "home_service"
        if mode == "Solo Cortes TDC":
            return kind == "cutoff"
        if mode == "Solo Fechas de Pago":
            return kind == "payment_due"
        if mode == "Solo Suscripciones":
            return kind == "subscription" and not is_home
        if mode == "Solo Servicios del Hogar":
            return is_home
        return True

    raw_by_day: Dict[int, List[Dict[str, Any]]] = cal_data.get("events_by_day") or {}
    filtered_by_day: Dict[int, List[Dict[str, Any]]] = {
        day_num: [ev for ev in ev_list if _matches(ev)]
        for day_num, ev_list in raw_by_day.items()
    }
    raw_upcoming: List[Dict[str, Any]] = cal_data.get("upcoming_14d") or []
    filtered_upcoming = [ev for ev in raw_upcoming if _matches(ev)]

    return {
        **cal_data,
        "events_by_day": filtered_by_day,
        "upcoming_14d": filtered_upcoming,
    }


def calculate_cashflow_and_budget_summary(
    accounts: List[Dict[str, Any]],
    categories: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Calcula los KPIs ejecutivos de finanzas del mes en curso:
    - Liquidez Disponible (Débito + Efectivo) y Capital en Inversión
    - Deuda Total en TDC y Crédito Total Disponible
    - Ingresos vs. Gastos del mes, Tasa de Ahorro (%) y Consumo por Categoría vs. Presupuesto.
    """
    ref = reference_date or date.today()
    active_accs = [a for a in accounts if bool(a.get("is_active", True))]

    liquid_balance = sum(
        float(a.get("current_balance") or 0.0)
        for a in active_accs
        if str(a.get("account_type")) in ("debit", "cash")
    )
    investment_balance = sum(
        float(a.get("current_balance") or 0.0)
        for a in active_accs
        if str(a.get("account_type")) == "investment"
    )
    cc_debt = sum(
        float(a.get("current_balance") or 0.0)
        for a in active_accs
        if str(a.get("account_type")) == "credit_card"
    )
    cc_total_limit = sum(
        float(a.get("credit_limit") or 0.0)
        for a in active_accs
        if str(a.get("account_type")) == "credit_card"
    )

    # Filtrar transacciones del mes calendario actual
    month_txs = []
    for tx in transactions:
        try:
            d = date.fromisoformat(str(tx.get("tx_date") or "")[:10])
            if d.year == ref.year and d.month == ref.month:
                month_txs.append(tx)
        except ValueError:
            pass

    month_income = sum(
        float(t.get("amount") or 0.0) for t in month_txs if str(t.get("tx_type")) == "income"
    )
    month_expenses = sum(
        float(t.get("amount") or 0.0) for t in month_txs if str(t.get("tx_type")) == "expense"
    )
    month_cashback = sum(float(t.get("cashback_earned") or 0.0) for t in month_txs)
    savings_rate_pct = (
        round(((month_income - month_expenses) / month_income) * 100.0, 1)
        if month_income > 0
        else 0.0
    )

    # Desglose por categoría de gasto vs. presupuesto mensual
    spent_by_cat: Dict[str, float] = {}
    for t in month_txs:
        if str(t.get("tx_type")) == "expense" and t.get("category_id"):
            cid = str(t["category_id"])
            spent_by_cat[cid] = spent_by_cat.get(cid, 0.0) + float(t.get("amount") or 0.0)

    cat_breakdown: List[Dict[str, Any]] = []
    total_monthly_budget = 0.0
    for c in categories:
        if str(c.get("kind", "expense")) != "expense":
            continue
        cid = str(c["id"])
        limit_b = float(c.get("monthly_budget_limit") or 0.0)
        spent_b = round(spent_by_cat.get(cid, 0.0), 2)
        total_monthly_budget += limit_b
        rem_b = limit_b - spent_b
        pct_b = round((spent_b / limit_b) * 100.0, 1) if limit_b > 0 else 0.0
        cat_breakdown.append(
            {
                "id": cid,
                "name": str(c.get("name", "Categoría")),
                "icon": str(c.get("icon", "💳")),
                "color_hex": str(c.get("color_hex", "#10B981")),
                "budget_limit": limit_b,
                "spent": spent_b,
                "remaining": rem_b,
                "usage_pct": pct_b,
                "is_over_85": pct_b >= 85.0 and limit_b > 0,
                "is_exceeded": spent_b > limit_b and limit_b > 0,
            }
        )

    cat_breakdown.sort(key=lambda item: float(item["spent"]), reverse=True)

    return {
        "liquid_balance": round(liquid_balance, 2),
        "investment_balance": round(investment_balance, 2),
        "net_worth": round(liquid_balance + investment_balance - cc_debt, 2),
        "cc_debt": round(cc_debt, 2),
        "cc_total_limit": round(cc_total_limit, 2),
        "cc_available": round(max(0.0, cc_total_limit - cc_debt), 2),
        "month_income": round(month_income, 2),
        "month_expenses": round(month_expenses, 2),
        "month_cashback": round(month_cashback, 2),
        "total_monthly_budget": round(total_monthly_budget, 2),
        "budget_remaining_total": round(total_monthly_budget - month_expenses, 2),
        "savings_rate_pct": savings_rate_pct,
        "categories_breakdown": cat_breakdown,
    }


# ============================================================================
# 5. LECTURAS CACHEADAS Y OPERACIONES CRUD EN SUPABASE CON SALDOS AUTOMÁTICOS
# ============================================================================

@st.cache_data(ttl=300)
def fetch_finance_accounts(
    user_id: str,
    access_token: str,
    include_inactive: bool = False,
) -> List[Dict[str, Any]]:
    """Lee las cuentas y tarjetas del usuario aisladas por RLS (activas o todas si include_inactive=True)."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    query = (
        client.table("finance_accounts")
        .select("*")
        .eq("user_id", user_id)
    )
    if not include_inactive:
        query = query.eq("is_active", True)
    res = query.order("account_type").order("created_at").execute()
    return res.data or []


@st.cache_data(ttl=300)
def fetch_finance_categories(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    """Lee las categorías financieras y presupuestos mensuales del usuario."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("finance_categories")
        .select("*")
        .eq("user_id", user_id)
        .order("kind")
        .order("name")
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=300)
def fetch_finance_transactions(
    user_id: str,
    access_token: str,
    days_back: int = 120,
) -> List[Dict[str, Any]]:
    """Lee los movimientos financieros recientes del usuario."""
    if not user_id or not access_token:
        return []
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("finance_transactions")
        .select("*")
        .eq("user_id", user_id)
        .gte("tx_date", cutoff)
        .order("tx_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


@st.cache_data(ttl=300)
def fetch_finance_subscriptions(user_id: str, access_token: str) -> List[Dict[str, Any]]:
    """Lee las suscripciones y pagos recurrentes del usuario."""
    if not user_id or not access_token:
        return []
    client = get_supabase_client(access_token=access_token)
    res = (
        client.table("finance_subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("billing_day_of_month", desc=False)
        .execute()
    )
    return res.data or []


def clear_finance_cache() -> None:
    """Invalida selectivamente las cachés financieras tras cualquier escritura."""
    fetch_finance_accounts.clear()
    fetch_finance_categories.clear()
    fetch_finance_transactions.clear()
    fetch_finance_subscriptions.clear()
    try:
        from src.views.home_hub_view import _fetch_hub_summary_counts
        _fetch_hub_summary_counts.clear()
    except Exception:
        pass


def create_finance_account(
    user_id: str,
    name: str,
    institution_name: str,
    account_type: str,
    card_network: str = "visa",
    last_four_digits: str = "0000",
    card_gradient_theme: str = "indigo_neon",
    current_balance: float = 0.0,
    credit_limit: float = 0.0,
    cutoff_day: Optional[int] = 15,
    payment_due_day: Optional[int] = 5,
    cashback_pct: float = 0.0,
    annual_fee: float = 0.0,
    interest_rate_cat: float = 45.0,
    minimum_payment_pct: float = 5.0,
    grace_days: int = 20,
) -> Tuple[bool, str]:
    """Crea una nueva cuenta o tarjeta de crédito en la billetera del usuario."""
    try:
        access_token = st.session_state.get("access_token") or ""
        is_cc = account_type == "credit_card"
        validated = FinanceAccountModel(
            user_id=user_id,
            name=name.strip(),
            institution_name=institution_name.strip() or "Banco",
            account_type=account_type,  # type: ignore[arg-type]
            card_network=card_network,  # type: ignore[arg-type]
            last_four_digits=(last_four_digits.strip() or "0000")[-4:],
            card_gradient_theme=card_gradient_theme,
            current_balance=float(current_balance),
            credit_limit=float(credit_limit) if is_cc else 0.0,
            cutoff_day=int(cutoff_day) if (is_cc and cutoff_day) else None,
            payment_due_day=int(payment_due_day) if (is_cc and payment_due_day) else None,
            cashback_pct=float(cashback_pct) if is_cc else 0.0,
            annual_fee=float(annual_fee) if is_cc else 0.0,
            interest_rate_cat=float(interest_rate_cat) if is_cc else 0.0,
            minimum_payment_pct=float(minimum_payment_pct) if is_cc else 5.0,
            grace_days=int(grace_days) if is_cc else 20,
            is_active=True,
        )

        payload = validated.model_dump(exclude={"id"})
        client = get_supabase_client(access_token=access_token)
        try:
            client.table("finance_accounts").insert(payload).execute()
        except Exception:
            # Fallback compatible si aún no se corrió 04_sprint4_finance_wallet_migration.sql
            legacy_payload = {
                k: v for k, v in payload.items() if k not in ("minimum_payment_pct", "grace_days")
            }
            client.table("finance_accounts").insert(legacy_payload).execute()

        clear_finance_cache()
        return True, f"Cuenta/Tarjeta «{validated.name}» agregada a tu billetera."
    except Exception as exc:
        return False, f"Error al crear cuenta/tarjeta: {exc}"


def set_finance_account_active_status(
    user_id: str,
    account_id: str,
    is_active: bool,
) -> Tuple[bool, str]:
    """
    Soft-Delete / Reactivación: Actualiza la columna booleana `is_active` de una cuenta
    de débito o tarjeta de crédito sin destruir el historial de transacciones vinculadas.
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("finance_accounts").update({"is_active": bool(is_active)}).eq(
            "id", account_id
        ).eq("user_id", user_id).execute()
        clear_finance_cache()
        if is_active:
            return True, "Cuenta / Tarjeta reactivada y visible nuevamente en tu Billetera."
        return True, "Cuenta / Tarjeta desactivada y archivada (historial conservado intacto)."
    except Exception as exc:
        return False, f"Error al cambiar estado de la cuenta: {exc}"


def delete_finance_account(user_id: str, account_id: str) -> Tuple[bool, str]:
    """
    Desactiva / archiva la cuenta mediante Soft-Delete (`is_active = False`) para
    proteger la integridad referencial (Foreign Keys) con transacciones pasadas.
    """
    return set_finance_account_active_status(user_id=user_id, account_id=account_id, is_active=False)


def update_finance_account_details(
    user_id: str,
    account_id: str,
    new_balance: float,
    card_gradient_theme: Optional[str] = None,
    name: Optional[str] = None,
) -> Tuple[bool, str]:
    """Actualiza el saldo/deuda, alias o la carátula visual (`card_gradient_theme`) de una cuenta/TDC."""
    try:
        access_token = st.session_state.get("access_token") or ""
        payload: Dict[str, Any] = {"current_balance": max(0.0, round(float(new_balance), 2))}
        if card_gradient_theme:
            payload["card_gradient_theme"] = str(card_gradient_theme)
        if name and name.strip():
            payload["name"] = name.strip()
        client = get_supabase_client(access_token=access_token)
        client.table("finance_accounts").update(payload).eq("id", account_id).eq("user_id", user_id).execute()
        clear_finance_cache()
        return True, "Cuenta / Tarjeta actualizada correctamente."
    except Exception as exc:
        return False, f"Error al actualizar la cuenta: {exc}"


def seed_sample_wallet_for_user(user_id: str) -> Tuple[bool, str]:
    """
    Crea 1 cuenta de débito y 2 tarjetas de crédito con distintas fechas de corte
    (ej. día 5 y día 20) para validar de inmediato el Simulador de TDC y Apple Wallet.
    """
    today_d = date.today().day
    # Configurar una tarjeta recién cortada hace 2 días y otra próxima a cortar en 2 días
    recent_cutoff = ((today_d - 3) % 28) + 1
    recent_pay = ((recent_cutoff + 19) % 28) + 1
    soon_cutoff = ((today_d + 1) % 28) + 1
    soon_pay = ((soon_cutoff + 19) % 28) + 1

    samples = [
        {
            "name": "Nómina / Débito Liquidez",
            "institution_name": "BBVA México",
            "account_type": "debit",
            "card_network": "visa",
            "last_four_digits": "4410",
            "card_gradient_theme": "deep_blue",
            "current_balance": 28500.0,
            "credit_limit": 0.0,
            "cutoff_day": None,
            "payment_due_day": None,
            "cashback_pct": 0.0,
            "interest_rate_cat": 0.0,
        },
        {
            "name": "TDC Nu Morada (Recién Cortada)",
            "institution_name": "Nu México",
            "account_type": "credit_card",
            "card_network": "mastercard",
            "last_four_digits": "9042",
            "card_gradient_theme": "violet_nu",
            "current_balance": 6200.0,
            "credit_limit": 45000.0,
            "cutoff_day": recent_cutoff,
            "payment_due_day": recent_pay,
            "cashback_pct": 1.5,
            "interest_rate_cat": 46.5,
        },
        {
            "name": "TDC Cashback Gold (2% Reembolso)",
            "institution_name": "Santander / Amex",
            "account_type": "credit_card",
            "card_network": "amex",
            "last_four_digits": "7815",
            "card_gradient_theme": "metallic_gold",
            "current_balance": 9400.0,
            "credit_limit": 60000.0,
            "cutoff_day": soon_cutoff,
            "payment_due_day": soon_pay,
            "cashback_pct": 2.0,
            "interest_rate_cat": 54.0,
        },
    ]

    for s in samples:
        create_finance_account(user_id=user_id, **s)

    return True, "Billetera de prueba creada (1 Débito + 2 TDC con distintas fechas de corte)."


def create_finance_transaction(
    user_id: str,
    account_id: str,
    tx_type: str,
    amount: float,
    merchant_or_concept: str,
    tx_date: Optional[date] = None,
    category_id: Optional[str] = None,
    destination_account_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_msi: bool = False,
    msi_months: int = 1,
    notes: str = "",
) -> Tuple[bool, str]:
    """
    Inserta un movimiento en `finance_transactions`, calcula el cashback ganado
    si se pagó con una TDC y actualiza automáticamente el saldo de la(s) cuenta(s).
    """
    try:
        access_token = st.session_state.get("access_token") or ""
        accounts = fetch_finance_accounts(user_id, access_token)
        accs_by_id = {str(a["id"]): a for a in accounts}
        src_acc = accs_by_id.get(str(account_id))
        if not src_acc:
            return False, "Selecciona una cuenta o tarjeta válida."

        amt = round(float(amount), 2)
        src_type = str(src_acc.get("account_type", "debit"))
        cb_pct = float(src_acc.get("cashback_pct") or 0.0) if src_type == "credit_card" else 0.0
        cb_earned = round(amt * (cb_pct / 100.0), 2) if (tx_type == "expense" and cb_pct > 0) else 0.0

        validated = FinanceTransactionModel(
            user_id=user_id,
            account_id=str(account_id),
            destination_account_id=str(destination_account_id) if destination_account_id else None,
            category_id=str(category_id) if category_id else None,
            tx_type=tx_type,  # type: ignore[arg-type]
            amount=amt,
            cashback_earned=cb_earned,
            tx_date=tx_date or date.today(),
            merchant_or_concept=merchant_or_concept.strip(),
            tags=[t.strip() for t in (tags or []) if t and t.strip()],
            is_msi=bool(is_msi),
            msi_months=int(msi_months) if is_msi else 1,
            notes=notes.strip(),
        )

        payload = validated.model_dump(exclude={"id"})
        payload["tx_date"] = validated.tx_date.isoformat()

        client = get_supabase_client(access_token=access_token)
        try:
            client.table("finance_transactions").insert(payload).execute()
        except Exception:
            legacy_payload = {k: v for k, v in payload.items() if k != "tags"}
            client.table("finance_transactions").insert(legacy_payload).execute()

        # Actualizar saldo de la cuenta origen
        curr_src_bal = float(src_acc.get("current_balance") or 0.0)
        if src_type == "credit_card":
            # En TDC, current_balance es el saldo utilizado / deuda
            if tx_type == "expense":
                new_src_bal = curr_src_bal + amt
            elif tx_type in ("income", "cc_payment"):
                new_src_bal = max(0.0, curr_src_bal - amt)
            else:
                new_src_bal = curr_src_bal + amt
        else:
            # En Débito / Efectivo / Inversión, current_balance es saldo líquido a favor
            if tx_type == "income":
                new_src_bal = curr_src_bal + amt
            else:
                new_src_bal = curr_src_bal - amt

        client.table("finance_accounts").update(
            {"current_balance": round(new_src_bal, 2)}
        ).eq("id", str(account_id)).eq("user_id", user_id).execute()

        # Si es transferencia o pago a tarjeta (cc_payment) con cuenta destino
        if destination_account_id and str(destination_account_id) in accs_by_id:
            dst_acc = accs_by_id[str(destination_account_id)]
            dst_type = str(dst_acc.get("account_type", "debit"))
            curr_dst_bal = float(dst_acc.get("current_balance") or 0.0)
            if dst_type == "credit_card":
                new_dst_bal = max(0.0, curr_dst_bal - amt)
            else:
                new_dst_bal = curr_dst_bal + amt
            client.table("finance_accounts").update(
                {"current_balance": round(new_dst_bal, 2)}
            ).eq("id", str(destination_account_id)).eq("user_id", user_id).execute()

        clear_finance_cache()
        cb_msg = f" · Cashback ganado: +${cb_earned:,.2f}" if cb_earned > 0 else ""
        return True, f"Movimiento registrado (${amt:,.2f}){cb_msg}."
    except Exception as exc:
        return False, f"Error al registrar movimiento: {exc}"


def delete_finance_transaction(user_id: str, tx_id: str) -> Tuple[bool, str]:
    """Elimina una transacción financiera."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("finance_transactions").delete().eq("id", tx_id).eq("user_id", user_id).execute()
        clear_finance_cache()
        return True, "Transacción eliminada."
    except Exception as exc:
        return False, f"Error al eliminar transacción: {exc}"


def create_finance_subscription(
    user_id: str,
    service_name: str,
    amount: float,
    billing_cycle: str,
    billing_day_of_month: int,
    account_id: Optional[str] = None,
    category_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """Registra una suscripción o cargo fijo recurrente en el calendario financiero."""
    try:
        access_token = st.session_state.get("access_token") or ""
        today = date.today()
        bday = max(1, min(31, int(billing_day_of_month or 1)))
        this_m_date = _safe_date_in_month(today.year, today.month, bday)
        if this_m_date >= today:
            next_bill = this_m_date
        else:
            ny, nm = _next_year_month(today.year, today.month)
            next_bill = _safe_date_in_month(ny, nm, bday)

        validated = FinanceSubscriptionModel(
            user_id=user_id,
            account_id=account_id if account_id else None,
            category_id=category_id if category_id else None,
            service_name=service_name.strip(),
            amount=float(amount),
            billing_cycle=billing_cycle,  # type: ignore[arg-type]
            billing_day_of_month=bday,
            next_billing_date=next_bill,
            is_active=True,
        )
        payload = validated.model_dump(exclude={"id"})
        payload["next_billing_date"] = validated.next_billing_date.isoformat()

        client = get_supabase_client(access_token=access_token)
        client.table("finance_subscriptions").insert(payload).execute()
        clear_finance_cache()
        return True, f"Suscripción «{validated.service_name}» programada (Día {bday})."
    except Exception as exc:
        return False, f"Error al crear suscripción: {exc}"


def update_finance_subscription(
    user_id: str,
    subscription_id: str,
    service_name: str,
    amount: float,
    billing_cycle: str,
    billing_day_of_month: int,
    next_billing_date: Optional[date] = None,
    account_id: Optional[str] = None,
    category_id: Optional[str] = None,
    is_active: bool = True,
) -> Tuple[bool, str]:
    """Actualiza en Supabase una suscripción o pago recurrente existente."""
    try:
        access_token = st.session_state.get("access_token") or ""
        today = date.today()
        bday = max(1, min(31, int(billing_day_of_month or 1)))
        if next_billing_date is not None:
            next_bill = next_billing_date
        else:
            this_m_date = _safe_date_in_month(today.year, today.month, bday)
            if this_m_date >= today:
                next_bill = this_m_date
            else:
                ny, nm = _next_year_month(today.year, today.month)
                next_bill = _safe_date_in_month(ny, nm, bday)

        validated = FinanceSubscriptionModel(
            user_id=user_id,
            account_id=account_id if account_id else None,
            category_id=category_id if category_id else None,
            service_name=service_name.strip(),
            amount=float(amount),
            billing_cycle=billing_cycle,  # type: ignore[arg-type]
            billing_day_of_month=bday,
            next_billing_date=next_bill,
            is_active=bool(is_active),
        )
        payload = validated.model_dump(exclude={"id", "user_id"})
        payload["next_billing_date"] = validated.next_billing_date.isoformat()

        client = get_supabase_client(access_token=access_token)
        client.table("finance_subscriptions").update(payload).eq("id", subscription_id).eq(
            "user_id", user_id
        ).execute()
        clear_finance_cache()
        return True, f"Suscripción «{validated.service_name}» actualizada correctamente."
    except Exception as exc:
        return False, f"Error al actualizar suscripción: {exc}"


def delete_finance_subscription(user_id: str, sub_id: str) -> Tuple[bool, str]:
    """Elimina una suscripción recurrente."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("finance_subscriptions").delete().eq("id", sub_id).eq("user_id", user_id).execute()
        clear_finance_cache()
        return True, "Suscripción eliminada."
    except Exception as exc:
        return False, f"Error al eliminar suscripción: {exc}"


def create_finance_category(
    user_id: str,
    name: str,
    kind: str = "expense",
    icon: str = "💳",
    monthly_budget_limit: float = 0.0,
    color_hex: str = "#10B981",
    is_essential: bool = True,
) -> Tuple[bool, str]:
    """Crea una nueva categoría personalizada de gasto, ingreso o transferencia en Supabase."""
    try:
        access_token = st.session_state.get("access_token") or ""
        validated = FinanceCategoryModel(
            user_id=user_id,
            name=name.strip(),
            kind=kind,  # type: ignore[arg-type]
            monthly_budget_limit=max(0.0, round(float(monthly_budget_limit or 0.0), 2))
            if kind == "expense"
            else 0.0,
            icon=(icon or "💳").strip(),
            color_hex=color_hex or ("#10B981" if kind == "income" else "#3B82F6"),
            is_essential=bool(is_essential),
        )
        payload = validated.model_dump(exclude={"id"})
        client = get_supabase_client(access_token=access_token)
        client.table("finance_categories").insert(payload).execute()
        clear_finance_cache()
        return True, f"Categoría «{validated.icon} {validated.name}» creada exitosamente."
    except Exception as exc:
        return False, f"Error al crear categoría: {exc}"


def update_finance_category(
    user_id: str,
    category_id: str,
    name: str,
    kind: str = "expense",
    icon: str = "💳",
    monthly_budget_limit: float = 0.0,
    color_hex: str = "#10B981",
    is_essential: bool = True,
) -> Tuple[bool, str]:
    """Actualiza el nombre, icono emoji, tipo (gasto/ingreso) y límite mensual de una categoría."""
    try:
        access_token = st.session_state.get("access_token") or ""
        validated = FinanceCategoryModel(
            user_id=user_id,
            name=name.strip(),
            kind=kind,  # type: ignore[arg-type]
            monthly_budget_limit=max(0.0, round(float(monthly_budget_limit or 0.0), 2))
            if kind == "expense"
            else 0.0,
            icon=(icon or "💳").strip(),
            color_hex=color_hex or "#10B981",
            is_essential=bool(is_essential),
        )
        payload = validated.model_dump(exclude={"id", "user_id"})
        client = get_supabase_client(access_token=access_token)
        client.table("finance_categories").update(payload).eq("id", category_id).eq(
            "user_id", user_id
        ).execute()
        clear_finance_cache()
        return True, f"Categoría «{validated.icon} {validated.name}» actualizada."
    except Exception as exc:
        return False, f"Error al actualizar categoría: {exc}"


def update_category_budget_limit(
    user_id: str,
    category_id: str,
    new_monthly_limit: float,
) -> Tuple[bool, str]:
    """Actualiza el presupuesto mensual asignado a una categoría de gasto."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("finance_categories").update(
            {"monthly_budget_limit": max(0.0, round(float(new_monthly_limit), 2))}
        ).eq("id", category_id).eq("user_id", user_id).execute()
        clear_finance_cache()
        return True, "Presupuesto mensual actualizado."
    except Exception as exc:
        return False, f"Error al actualizar presupuesto: {exc}"


def update_finance_account_balance(
    user_id: str,
    account_id: str,
    new_balance: float,
) -> Tuple[bool, str]:
    """Actualiza directamente el saldo o deuda utilizada de una cuenta/tarjeta."""
    try:
        access_token = st.session_state.get("access_token") or ""
        client = get_supabase_client(access_token=access_token)
        client.table("finance_accounts").update(
            {"current_balance": max(0.0, round(float(new_balance), 2))}
        ).eq("id", account_id).eq("user_id", user_id).execute()
        clear_finance_cache()
        return True, "Saldo actualizado."
    except Exception as exc:
        return False, f"Error al actualizar saldo: {exc}"

