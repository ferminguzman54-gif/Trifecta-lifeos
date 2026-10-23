"""
Esquemas Pydantic para cuentas, TDC, transacciones, suscripciones y presupuestos
según 05_Backend_Schema_Supabase.md (§2.2).
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field

AccountType = Literal["debit", "cash", "investment", "credit_card"]
CardNetwork = Literal["visa", "mastercard", "amex", "other"]
CategoryKind = Literal["expense", "income", "transfer"]
TransactionType = Literal["expense", "income", "transfer", "cc_payment"]
BillingCycle = Literal["weekly", "biweekly", "monthly", "bimonthly", "quarterly", "yearly"]


class FinanceAccountModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    name: str = Field(..., min_length=1)
    institution_name: str = "Banco"
    account_type: AccountType = "credit_card"
    card_network: CardNetwork = "visa"
    last_four_digits: str = Field(default="0000", max_length=4)
    card_gradient_theme: str = "indigo_neon"
    current_balance: float = 0.0
    credit_limit: float = Field(default=0.0, ge=0.0)
    cutoff_day: Optional[int] = Field(default=None, ge=1, le=31)
    payment_due_day: Optional[int] = Field(default=None, ge=1, le=31)
    cashback_pct: float = Field(default=0.0, ge=0.0)
    annual_fee: float = Field(default=0.0, ge=0.0)
    interest_rate_cat: float = Field(default=0.0, ge=0.0)
    is_active: bool = True


class FinanceCategoryModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    name: str
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
    tx_date: date
    merchant_or_concept: str = Field(..., min_length=1)
    is_msi: bool = False
    msi_months: int = Field(default=1, ge=1)
    notes: str = ""
