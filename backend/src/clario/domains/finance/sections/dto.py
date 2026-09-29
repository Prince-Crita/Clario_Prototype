"""Finance section responses (plan §11.1, §25): what each Command Centre tab and each assistant
tool receives. Amounts are exact decimal strings in JSON, in the organisation's base currency;
percentages are unrounded (the UI rounds: 0 dp on KPIs, 1 dp in tables). Every figure carries its
basis, so the UI can label it and nothing is compared across bases by accident.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Basis = Literal["accrual", "cash", "billed", "balance", "ledger"]


class Window(BaseModel):
    start: date
    end: date
    label: str = Field(description='e.g. "FY 2026-27 to date", "Apr 2025 – 25 Sep 2026"')


class Freshness(BaseModel):
    as_of: datetime | None = Field(description="Oldest successful dataset refresh")
    data_version: uuid.UUID | None = Field(description="Id of the last sync that wrote data")
    sync_state: Literal["idle", "running"]


class Meta(BaseModel):
    organisation: str
    currency: str
    fiscal_year: str = Field(description='e.g. "FY 2026-27"')
    fiscal_year_start_month: int
    today: date = Field(description="Today in the organisation's time zone")
    freshness: Freshness


class Change(BaseModel):
    percent: Decimal | None = Field(description="(current − previous) ÷ |previous| × 100")
    compared_to: str


class Kpi(BaseModel):
    key: str
    label: str
    value: Decimal
    basis: Basis
    window: Window
    note: str | None = None
    change: Change | None = None
    related: NamedAmount | None = Field(None, description='e.g. {"billed": 895675} for collected')
    ratio: Decimal | None = Field(None, description="Percent: collection ratio, net margin")
    count: int | None = Field(None, description="e.g. overdue invoices for receivables")


class PnlStatement(BaseModel):
    basis: Basis = "accrual"
    window: Window
    revenue: Decimal
    cogs: Decimal
    operating_expenses: Decimal
    total_costs: Decimal
    gross_profit: Decimal
    gross_margin: Decimal | None
    net_pnl: Decimal
    net_margin: Decimal | None
    other_income: Decimal = Field(description="Non-operating; not in net P&L (director Q4)")
    other_expenses: Decimal = Field(description="Non-operating; not in net P&L (director Q4)")
    largest_cost: NamedAmount | None
    latest_month_spend: Decimal = Field(
        description="Cash expenses of the current month (the PDF's run-rate note; director Q3)"
    )


class NamedAmount(BaseModel):
    name: str
    amount: Decimal


class MonthFigures(BaseModel):
    month: date
    billed: Decimal
    collected: Decimal
    expenses: Decimal
    net_cash: Decimal


class ActionItemOut(BaseModel):
    kind: Literal["overdue_invoice", "gst_payable", "accrual_loss"]
    severity: Literal["high", "medium", "low"]
    title: str
    detail: str
    amount: Decimal
    reference: str | None
    days_overdue: int | None
    due_date: date | None


class ClientBilled(BaseModel):
    party_name: str
    billed: Decimal
    outstanding: Decimal
    overdue: Decimal
    has_overdue: bool


class ExpenseShare(BaseModel):
    name: str
    amount: Decimal
    share: Decimal | None = Field(description="Percent of the total")


class RegisterTotalsOut(BaseModel):
    count: int
    billed: Decimal
    balance: Decimal


class Overview(BaseModel):
    meta: Meta
    kpis: list[Kpi]
    pnl: PnlStatement
    months: list[MonthFigures] = Field(description="Billed vs collected vs expenses (cash)")
    actions: list[ActionItemOut]
    revenue_by_client: list[ClientBilled]
    expense_mix: list[ExpenseShare] = Field(description="Operating expenses by account (accrual)")
    expense_mix_window: Window
    register_totals: RegisterTotalsOut


class CategoryMonth(BaseModel):
    month: date
    amounts: dict[str, Decimal]
    other: Decimal = Field(description="Categories outside the top five")


class CashBucketOut(BaseModel):
    start: date
    cash_in: Decimal
    cash_out: Decimal
    net: Decimal


class Trends(BaseModel):
    meta: Meta
    window: Window
    months: list[MonthFigures]
    totals: MonthFigures
    top_categories: list[str]
    expense_trend: list[CategoryMonth]
    weekly: list[CashBucketOut] = Field(description="Last 10 weeks, weeks start on Monday")
    daily: list[CashBucketOut] = Field(description="Last 30 days")


class AgeBucketOut(BaseModel):
    key: str
    label: str
    amount: Decimal
    count: int


class InvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_number: str
    party_name: str
    invoice_date: date
    due_date: date | None
    total: Decimal
    balance: Decimal
    currency: str
    total_document: Decimal = Field(description="In the invoice's own currency")
    status: Literal["draft", "void", "paid", "partially_paid", "open", "overdue", "unknown"]
    days_overdue: int


class Receivables(BaseModel):
    meta: Meta
    basis: Basis = "balance"
    outstanding: Decimal
    overdue: Decimal
    overdue_count: int
    open_count: int
    ageing: list[AgeBucketOut]
    by_client: list[ClientBilled]
    invoices: list[InvoiceOut] = Field(description="Every receivable, most overdue first")


class GstOut(BaseModel):
    meta: Meta
    basis: Basis = "ledger"
    pending_definition: bool = Field(True, description="Awaiting the director's definition (Q5)")
    as_of: date | None
    output_tax: Decimal | None
    input_tax: Decimal | None
    net_payable: Decimal | None


class BalanceLineOut(BaseModel):
    name: str
    balance: Decimal


class BalanceGroup(BaseModel):
    name: str
    total: Decimal
    lines: list[BalanceLineOut]


class BalanceSheet(BaseModel):
    meta: Meta
    basis: Basis = "balance"
    pending_definition: bool = Field(True, description="Awaiting the director's definition (Q6)")
    as_of: date | None
    cash_on_hand: Decimal
    groups: list[BalanceGroup]


class InvoicePage(BaseModel):
    items: list[InvoiceOut]
    next_cursor: str | None


Kpi.model_rebuild()
PnlStatement.model_rebuild()
