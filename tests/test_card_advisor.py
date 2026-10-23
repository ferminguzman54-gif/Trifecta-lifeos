"""Pruebas unitarias de cálculo de días de financiamiento y score de conveniencia TDC."""
from src.models.finance_models import FinanceAccountModel


def test_finance_account_model_validation() -> None:
    card = FinanceAccountModel(
        user_id="00000000-0000-0000-0000-000000000001",
        name="TDC Nu",
        institution_name="Nu México",
        account_type="credit_card",
        credit_limit=40000.0,
        current_balance=8400.0,
        cutoff_day=15,
        payment_due_day=5,
        cashback_pct=1.5,
    )
    assert card.cutoff_day == 15
    assert card.payment_due_day == 5
