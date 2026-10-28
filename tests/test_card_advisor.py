"""
Pruebas unitarias para el Motor de Ciclo de Facturación, Recomendador Inteligente de TDC
y Simulador de Pago para No Generar Intereses / Pago Mínimo / Amortización (Sprint 4).
"""
from __future__ import annotations

from datetime import date

from src.config.theme import CARD_GRADIENTS
from src.services.card_advisor_engine import (
    build_financial_calendar_events,
    calculate_card_cycle_dates,
    calculate_float_days,
    evaluate_best_payment_cards,
    filter_financial_calendar_events,
    is_home_service_item,
    simulate_credit_card_amortization,
)


def test_post_cutoff_purchase_grants_maximum_float_days() -> None:
    """
    Comprar el día siguiente a la fecha de corte (ej. corte día 8, compra día 9)
    debe entrar hasta el corte del mes siguiente y otorgar ~45-50 días sin intereses.
    """
    cycle = calculate_card_cycle_dates(
        cutoff_day=8,
        payment_due_day=28,
        purchase_date=date(2026, 3, 9),
    )
    assert cycle.statement_cutoff_date == date(2026, 4, 8)
    assert cycle.payment_due_date == date(2026, 4, 28)
    assert cycle.float_days == 50
    assert cycle.optimal_purchase_window is True


def test_pre_cutoff_purchase_enters_current_cycle_and_triggers_wait_tip() -> None:
    """
    Comprar 2 días antes de la fecha de corte (ej. corte día 10, compra día 8)
    entra en el corte actual (~22 días de financiamiento) y genera alerta recomendando
    esperar al día 11 para ganar un mes adicional libre de intereses.
    """
    float_days = calculate_float_days(
        purchase_date=date(2026, 5, 8),
        cutoff_day=10,
        payment_due_day=30,
    )
    assert float_days == 22

    accounts = [
        {
            "id": "cc-1",
            "name": "TDC Próxima al Corte",
            "institution_name": "BBVA",
            "account_type": "credit_card",
            "current_balance": 2000.0,
            "credit_limit": 30000.0,
            "cutoff_day": 10,
            "payment_due_day": 30,
            "cashback_pct": 1.0,
            "interest_rate_cat": 65.0,
            "is_active": True,
        }
    ]
    recs = evaluate_best_payment_cards(
        credit_cards=accounts,
        amount=1500.0,
        purchase_date=date(2026, 5, 8),
    )
    assert len(recs) == 1
    assert recs[0].wait_for_cutoff_tip is not None
    assert "ganarás" in recs[0].wait_for_cutoff_tip


def test_evaluate_best_payment_cards_ranks_post_cutoff_and_low_utilization_first() -> None:
    """
    Verifica que el algoritmo de 4 factores (45% Float, 25% Cashback, 20% Utilización, 10% Presupuesto)
    priorice la tarjeta que acaba de cortar y mantiene utilización saludable (<30%).
    """
    accounts = [
        {
            "id": "cc-just-cut",
            "name": "Nu Crédito (Recién cortó)",
            "institution_name": "Nu",
            "account_type": "credit_card",
            "current_balance": 3000.0,
            "credit_limit": 40000.0,
            "cutoff_day": 8,
            "payment_due_day": 28,
            "cashback_pct": 1.5,
            "interest_rate_cat": 65.0,
            "is_active": True,
        },
        {
            "id": "cc-almost-cutting",
            "name": "TDC Saturada y por cortar",
            "institution_name": "Banco X",
            "account_type": "credit_card",
            "current_balance": 26000.0,
            "credit_limit": 30000.0,
            "cutoff_day": 11,
            "payment_due_day": 1,
            "cashback_pct": 1.0,
            "interest_rate_cat": 75.0,
            "is_active": True,
        },
    ]
    recs = evaluate_best_payment_cards(
        credit_cards=accounts,
        amount=2000.0,
        purchase_date=date(2026, 3, 9),
    )
    assert len(recs) == 2
    assert recs[0].account_id == "cc-just-cut"
    assert recs[0].total_score > recs[1].total_score
    assert recs[0].float_days == 50
    assert recs[0].cashback_earned == 30.0


def test_simulate_credit_card_amortization_and_minimum_payment_cost() -> None:
    """
    Valida que el simulador de amortización calcule:
    - Pago para no generar intereses = 100% de la deuda
    - Costo financiero de pagar solo el mínimo > 0 cuando CAT > 0
    - Tabla de amortización que liquida el saldo a $0.00 en N meses
    """
    sim = simulate_credit_card_amortization(
        card_name="TDC Prueba",
        current_balance=20000.0,
        annual_cat_pct=60.0,
        minimum_payment_pct=5.0,
        plan_months=6,
    )
    assert sim.no_interest_payment == 20000.0
    assert sim.minimum_payment == 1000.0
    assert sim.first_month_interest_if_minimum > 0.0
    assert sim.total_interest_if_minimum_only > sim.plan_total_interest
    assert len(sim.schedule) == 6
    assert sim.schedule[-1]["end_balance"] == 0.0


def test_build_financial_calendar_events_maps_cutoffs_and_due_dates() -> None:
    """Verifica que el calendario mapee cortes, fechas límite de pago y suscripciones."""
    accounts = [
        {
            "id": "cc-1",
            "name": "BBVA Azul",
            "account_type": "credit_card",
            "current_balance": 8500.0,
            "credit_limit": 50000.0,
            "cutoff_day": 12,
            "payment_due_day": 2,
            "is_active": True,
        }
    ]
    subs = [
        {
            "id": "sub-1",
            "service_name": "Spotify Duo",
            "amount": 199.0,
            "billing_cycle": "monthly",
            "billing_day_of_month": 15,
            "is_active": True,
        }
    ]
    cal = build_financial_calendar_events(
        accounts=accounts,
        subscriptions=subs,
        transactions=[],
        year=2026,
        month=4,
    )
    events_by_day = cal["events_by_day"]
    assert any(e["kind"] == "cutoff" for e in events_by_day[12])
    assert any(e["kind"] == "payment_due" for e in events_by_day[2])
    assert any(e["kind"] == "subscription" for e in events_by_day[15])


def test_smart_financial_calendar_filters_and_card_gradients() -> None:
    """Verifica los 5 filtros inteligentes del calendario y las nuevas carátulas de tarjetas."""
    for expected_theme in (
        "obsidian_gold",
        "emerald_minimal",
        "cyberpunk_cyan",
        "sunset_orange",
        "titanium_silver",
        "rose_velvet",
    ):
        assert expected_theme in CARD_GRADIENTS

    assert is_home_service_item("Internet Fibra Telmex", "Vivienda y Servicios") is True
    assert is_home_service_item("Spotify Premium", "Suscripciones y Digital") is False

    accounts = [
        {
            "id": "cc-1",
            "name": "BBVA Azul",
            "account_type": "credit_card",
            "current_balance": 8500.0,
            "credit_limit": 50000.0,
            "cutoff_day": 12,
            "payment_due_day": 2,
            "is_active": True,
        }
    ]
    subs = [
        {
            "id": "sub-1",
            "service_name": "Spotify Duo",
            "amount": 199.0,
            "billing_cycle": "monthly",
            "billing_day_of_month": 15,
            "is_active": True,
        },
        {
            "id": "sub-2",
            "service_name": "Internet Fibra Óptica",
            "amount": 699.0,
            "billing_cycle": "monthly",
            "billing_day_of_month": 18,
            "is_active": True,
        },
    ]
    cal = build_financial_calendar_events(
        accounts=accounts,
        subscriptions=subs,
        transactions=[],
        year=2026,
        month=4,
    )
    only_cutoffs = filter_financial_calendar_events(cal, "Solo Cortes TDC")
    assert len(only_cutoffs["events_by_day"][12]) == 1
    assert len(only_cutoffs["events_by_day"][2]) == 0

    only_due = filter_financial_calendar_events(cal, "Solo Fechas de Pago")
    assert len(only_due["events_by_day"][2]) == 1
    assert len(only_due["events_by_day"][12]) == 0

    only_subs = filter_financial_calendar_events(cal, "Solo Suscripciones")
    assert len(only_subs["events_by_day"][15]) == 1
    assert len(only_subs["events_by_day"][18]) == 0

    only_home = filter_financial_calendar_events(cal, "Solo Servicios del Hogar")
    assert len(only_home["events_by_day"][18]) == 1
    assert len(only_home["events_by_day"][15]) == 0
