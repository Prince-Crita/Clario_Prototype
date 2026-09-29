"""Canonical finance records (plan §14.3, §23): what every finance connector delivers.

Connector-agnostic and exact: amounts are `Decimal`, dates are business dates. `*_base` amounts
are in the organisation's base currency and are the ones every aggregate uses. References to other
records are by the SOURCE id (`party_source_id`, ...); the ingest resolves them to mirror ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class PartyType(StrEnum):
    CUSTOMER = "customer"
    VENDOR = "vendor"


class InvoiceStatus(StrEnum):
    """Derived from amounts, never from the source label ('overdue' is derived at read time)."""

    DRAFT = "draft"
    OPEN = "open"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOID = "void"
    UNKNOWN = "unknown"


class AccountCategory(StrEnum):
    INCOME = "income"
    OTHER_INCOME = "other_income"
    COST_OF_GOODS_SOLD = "cost_of_goods_sold"
    EXPENSE = "expense"
    OTHER_EXPENSE = "other_expense"
    CASH = "cash"
    BANK = "bank"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    OTHER_CURRENT_ASSET = "other_current_asset"
    FIXED_ASSET = "fixed_asset"
    ACCOUNTS_PAYABLE = "accounts_payable"
    TAX_LIABILITY = "tax_liability"
    OTHER_LIABILITY = "other_liability"
    EQUITY = "equity"
    OTHER = "other"


class TaxRole(StrEnum):
    OUTPUT_TAX = "output_tax"
    INPUT_TAX = "input_tax"


class PnlSection(StrEnum):
    """Profit & loss sections as the source reports them (Revenue = operating income, §24.2)."""

    OPERATING_INCOME = "operating_income"
    COST_OF_GOODS_SOLD = "cost_of_goods_sold"
    OPERATING_EXPENSE = "operating_expense"
    NON_OPERATING_INCOME = "non_operating_income"
    NON_OPERATING_EXPENSE = "non_operating_expense"


@dataclass(frozen=True, slots=True)
class Party:
    source_id: str
    party_type: PartyType
    display_name: str
    company_name: str | None
    gstin: str | None
    currency: str | None
    source_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class Invoice:
    source_id: str
    invoice_number: str
    party_source_id: str | None
    party_name: str
    invoice_date: date
    due_date: date | None
    source_status: str
    status: InvoiceStatus
    currency: str
    exchange_rate: Decimal
    subtotal: Decimal | None
    tax_total: Decimal | None
    total: Decimal
    balance: Decimal
    total_base: Decimal
    balance_base: Decimal
    source_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class PaymentReceived:
    source_id: str
    party_source_id: str | None
    party_name: str
    payment_date: date
    amount: Decimal
    amount_base: Decimal
    currency: str
    payment_mode: str | None
    reference: str | None
    source_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class Expense:
    source_id: str
    expense_date: date
    account_name: str
    vendor_name: str | None
    amount_net: Decimal  # base currency, without tax
    tax_amount: Decimal  # base currency
    total: Decimal  # document currency
    total_base: Decimal
    currency: str
    paid_through: str | None
    source_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class PaymentMade:
    source_id: str
    party_source_id: str | None
    party_name: str
    payment_date: date
    amount: Decimal
    amount_base: Decimal
    currency: str
    paid_through: str | None
    source_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class Account:
    source_id: str
    name: str
    code: str | None
    source_account_type: str
    category: AccountCategory
    tax_role: TaxRole | None
    is_active: bool
    source_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class LedgerAmount:
    """One account's own amount in one P&L section for one calendar month (accrual)."""

    account_source_id: str
    account_name: str
    section: PnlSection
    period_month: date  # first day of the month
    amount: Decimal


@dataclass(frozen=True, slots=True)
class BalanceAmount:
    """One balance-sheet line as of a date. `account_source_id` is None for computed lines
    (e.g. current-year earnings)."""

    account_source_id: str | None
    account_name: str
    group: str  # the source's grouping, e.g. "Cash", "Bank", "Accounts Receivable"
    as_of: date
    balance: Decimal
