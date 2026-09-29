"""Normalized Clario business models. These are what tools and the agent see."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _as_date(value: Any) -> date | None:
    if value in (None, "", " "):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class Organization(BaseModel):
    model_config = ConfigDict(extra="ignore")

    organization_id: str
    name: str
    currency_code: str = ""
    currency_symbol: str = ""
    time_zone: str = ""
    is_org_active: bool = True
    is_default_org: bool = False

    @field_validator("organization_id", mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> str:
        return _as_str(value)


class Invoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    invoice_id: str
    invoice_number: str = ""
    customer_id: str = ""
    customer: str = ""
    invoice_date: date | None = None
    due_date: date | None = None
    status: str = ""
    total: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    currency: str = ""

    @field_validator("invoice_id", "customer_id", mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> str:
        return _as_str(value)

    @field_validator("total", "balance", mode="before")
    @classmethod
    def coerce_money(cls, value: Any) -> Decimal:
        return _as_decimal(value)

    @field_validator("invoice_date", "due_date", mode="before")
    @classmethod
    def coerce_date(cls, value: Any) -> date | None:
        return _as_date(value)


class Customer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    customer_id: str
    name: str
    company_name: str = ""
    email: str = ""
    status: str = ""
    outstanding: Decimal = Decimal("0")
    unused_credits: Decimal = Decimal("0")
    currency: str = ""
    contact_type: str = "customer"

    @field_validator("customer_id", mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> str:
        return _as_str(value)

    @field_validator("outstanding", "unused_credits", mode="before")
    @classmethod
    def coerce_money(cls, value: Any) -> Decimal:
        return _as_decimal(value)


class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    payment_id: str
    customer_id: str = ""
    customer: str = ""
    payment_date: date | None = None
    amount: Decimal = Decimal("0")
    unused_amount: Decimal = Decimal("0")
    payment_mode: str = ""
    invoice_numbers: str = ""
    currency: str = ""

    @field_validator("payment_id", "customer_id", mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> str:
        return _as_str(value)

    @field_validator("amount", "unused_amount", mode="before")
    @classmethod
    def coerce_money(cls, value: Any) -> Decimal:
        return _as_decimal(value)

    @field_validator("payment_date", mode="before")
    @classmethod
    def coerce_date(cls, value: Any) -> date | None:
        return _as_date(value)


class Expense(BaseModel):
    model_config = ConfigDict(extra="ignore")

    expense_id: str
    expense_date: date | None = None
    account_name: str = ""
    category: str = ""
    vendor: str = ""
    total: Decimal = Decimal("0")
    currency: str = ""
    description: str = ""
    status: str = ""

    @field_validator("expense_id", mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> str:
        return _as_str(value)

    @field_validator("total", mode="before")
    @classmethod
    def coerce_money(cls, value: Any) -> Decimal:
        return _as_decimal(value)

    @field_validator("expense_date", mode="before")
    @classmethod
    def coerce_date(cls, value: Any) -> date | None:
        return _as_date(value)


class Item(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_id: str
    name: str
    sku: str = ""
    rate: Decimal = Decimal("0")
    status: str = ""
    description: str = ""

    @field_validator("item_id", mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> str:
        return _as_str(value)

    @field_validator("rate", mode="before")
    @classmethod
    def coerce_money(cls, value: Any) -> Decimal:
        return _as_decimal(value)


class OverdueInvoice(Invoice):
    days_overdue: int = 0


class SalesSummary(BaseModel):
    start_date: date
    end_date: date
    total_sales: Decimal
    invoice_count: int
    average_invoice_value: Decimal
    currency: str = ""
    paid_count: int = 0
    unpaid_balance: Decimal = Decimal("0")


class PeriodComparison(BaseModel):
    metric: str
    current_period: Decimal
    previous_period: Decimal
    change_amount: Decimal
    change_percent: Decimal | None
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date
    currency: str = ""
    note: str = ""


class CustomerBalance(BaseModel):
    customer_id: str
    customer: str
    outstanding: Decimal
    overdue: Decimal = Decimal("0")
    invoice_count: int = 0
    currency: str = ""


class ReceivableSummary(BaseModel):
    as_of: date
    outstanding: Decimal
    overdue: Decimal
    invoice_count: int
    overdue_count: int
    by_customer: list[CustomerBalance] = Field(default_factory=list)
    currency: str = ""


class ExpenseCategoryTotal(BaseModel):
    category: str
    total: Decimal
    count: int


class ExpenseSummary(BaseModel):
    start_date: date
    end_date: date
    total_expenses: Decimal
    expense_count: int
    by_category: list[ExpenseCategoryTotal] = Field(default_factory=list)
    currency: str = ""


class CustomerSales(BaseModel):
    customer_id: str
    customer: str
    sales: Decimal
    invoice_count: int
    share_percent: Decimal | None = None
    currency: str = ""


class ItemSales(BaseModel):
    item_id: str = ""
    item: str
    quantity: Decimal = Decimal("0")
    sales: Decimal
    currency: str = ""


class BusinessSignal(BaseModel):
    name: str
    severity: str
    observation: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class BusinessSummary(BaseModel):
    generated_at: datetime
    organization_name: str
    organization_id: str
    currency: str
    current_period_start: date
    current_period_end: date
    sales: SalesSummary
    previous_sales: SalesSummary | None = None
    sales_change: PeriodComparison | None = None
    expenses: ExpenseSummary
    previous_expenses: ExpenseSummary | None = None
    expense_change: PeriodComparison | None = None
    receivables: ReceivableSummary
    top_customers: list[CustomerSales] = Field(default_factory=list)
    signals: list[BusinessSignal] = Field(default_factory=list)


class FinancialReport(BaseModel):
    report_name: str
    start_date: date | None = None
    end_date: date | None = None
    currency: str = ""
    totals: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "zoho_report"
    note: str = ""
