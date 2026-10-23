"""
Esquemas Pydantic para cuentas bancarias, tarjetas de crédito (con días de corte/pago,
cashback, CAT y pago mínimo), categorías, transacciones con etiquetas, suscripciones,
recomendaciones del simulador de TDC y proyecciones de amortización.
Implementado según 01_PRD (§3), 02_TRD (§5.2), 05_Backend_Schema (§2) y Sprint 4.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

AccountType = Literal["debit", "cash", "investment", "credit_card"]
CardNetwork = Literal["visa", "mastercard", "amex", "other"]
CategoryKind = Literal["expense", "income", "transfer"]
TransactionType = Literal["expense", "income", "transfer", "cc_payment"]
BillingCycle = Literal["weekly", "biweekly", "monthly", "bimonthly", "quarterly", "yearly"]

ACCOUNT_TYPE_LABELS: Dict[str, str] = {
    "credit_card": "💳 Tarjeta de Crédito (TDC)",
    "debit": "🏦 Cuenta de Débito / Nómina",
    "cash": "💵 Efectivo / Billetera Física",
    "investment": "📈 Ahorro / Inversión",
}

TX_TYPE_LABELS: Dict[str, str] = {
    "expense": "💸 Gasto / Compra",
    "income": "💰 Ingreso / Abono",
    "cc_payment": "💳 Pago a Tarjeta de Crédito",
    "transfer": "🔄 Transferencia entre Cuentas",
}

BILLING_CYCLE_LABELS: Dict[str, str] = {
    "weekly": "Semanal",
    "biweekly": "Quincenal",
    "monthly": "Mensual",
    "bimonthly": "Bimestral",
    "quarterly": "Trimestral",
    "yearly": "Anual",
}


class FinanceAccountModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    name: str = Field(..., min_length=1, max_length=90)
    institution_name: str = Field(default="Banco", min_length=1, max_length=60)
    account_type: AccountType = "credit_card"
    card_network: CardNetwork = "visa"
    last_four_digits: str = Field(default="0000", max_length=4)
    card_gradient_theme: str = "indigo_neon"
    current_balance: float = 0.0
    credit_limit: float = Field(default=0.0, ge=0.0)
    cutoff_day: Optional[int] = Field(default=15, ge=1, le=31)
    payment_due_day: Optional[int] = Field(default=5, ge=1, le=31)
    cashback_pct: float = Field(default=0.0, ge=0.0, le=25.0)
    annual_fee: float = Field(default=0.0, ge=0.0)
    interest_rate_cat: float = Field(default=45.0, ge=0.0, le=250.0)
    minimum_payment_pct: float = Field(default=5.0, ge=1.0, le=100.0)
    grace_days: int = Field(default=20, ge=10, le=35)
    is_active: bool = True


class FinanceCategoryModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    name: str = Field(..., min_length=1, max_length=80)
    kind: CategoryKind = "expense"
    monthly_budget_limit: float = Field(default=0.0, ge=0.0)
    icon: str = "💳"
    color_hex: str = "#10B981"
    is_essential: bool = True


class FinanceTransactionModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    account_id: str
    destination_account_id: Optional[str] = None
    category_id: Optional[str] = None
    tx_type: TransactionType = "expense"
    amount: float = Field(..., gt=0.0)
    cashback_earned: float = Field(default=0.0, ge=0.0)
    tx_date: date = Field(default_factory=date.today)
    merchant_or_concept: str = Field(..., min_length=1, max_length=140)
    tags: List[str] = Field(default_factory=list)
    is_msi: bool = False
    msi_months: int = Field(default=1, ge=1, le=48)
    notes: str = ""


class FinanceSubscriptionModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    account_id: Optional[str] = None
    category_id: Optional[str] = None
    service_name: str = Field(..., min_length=1, max_length=90)
    amount: float = Field(..., gt=0.0)
    billing_cycle: BillingCycle = "monthly"
    billing_day_of_month: int = Field(default=1, ge=1, le=31)
    next_billing_date: date
    is_active: bool = True


class CardCycleDates(BaseModel):
    cutoff_day: int
    payment_due_day: int
    statement_cutoff_date: date
    payment_due_date: date
    days_until_cutoff: int
    days_until_payment_due: int
    float_days: int
    optimal_purchase_window: bool
    window_badge: str
    wait_for_cutoff_tip: Optional[str] = None


class CardAdvisorRecommendation(BaseModel):
    account_id: str
    card_name: str
    institution_name: str
    card_network: str
    last_four_digits: str
    card_gradient_theme: str
    total_score: float
    is_eligible: bool = True
    rejection_reason: Optional[str] = None
    float_days: int
    statement_cutoff_date: date
    payment_due_date: date
    cashback_pct: float
    cashback_earned: float
    current_balance: float
    credit_limit: float
    available_credit_before: float
    available_credit_after: float
    utilization_before_pct: float
    utilization_after_pct: float
    score_float: float
    score_cashback: float
    score_utilization: float
    score_budget: float
    budget_remaining_after: float
    optimal_window_badge: str
    wait_for_cutoff_tip: Optional[str] = None


class AmortizationSimulation(BaseModel):
    card_name: str
    current_balance: float
    annual_cat_pct: float
    monthly_rate_pct: float
    no_interest_payment: float
    minimum_payment: float
    first_month_interest_if_minimum: float
    months_if_minimum_only: int
    total_interest_if_minimum_only: float
    plan_months: int
    plan_monthly_payment: float
    plan_total_interest: float
    plan_total_paid: float
    schedule: List[Dict[str, Any]] = Field(default_factory=list)
