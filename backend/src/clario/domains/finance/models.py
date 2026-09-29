"""The `finance` schema: a connector-agnostic mirror (plan §14.3).

Every table carries the lineage columns (workspace, connection, source system, source record id,
source/sync times, sync run) and a composite FK `(connection_id, workspace_id)` to its connection,
so a row can only ever belong to a connection of its own workspace. `(connection_id,
source_record_id)` is unique: re-syncing upserts instead of duplicating. Ledger and balance lines
have no record id in the source, so theirs is built from account, section/date and month.

Money is `numeric(19,4)` (base-currency `*_base` columns are what aggregates use); rates are
`numeric(18,8)`. Invoice status excludes 'overdue': it is derived at read time from the due date.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from clario.core.db import Base, UUIDPrimaryKey

SCHEMA = "finance"
Money = Numeric(19, 4)
Rate = Numeric(18, 8)


def lineage_args(table: str, *extra: Any) -> tuple[Any, ...]:
    return (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name=f"fk_{table}_connection",
            ondelete="CASCADE",
        ),
        UniqueConstraint("connection_id", "source_record_id", name=f"uq_{table}_source_record"),
        *extra,
        {"schema": SCHEMA},
    )


class Lineage(UUIDPrimaryKey):
    workspace_id: Mapped[uuid.UUID] = mapped_column()
    connection_id: Mapped[uuid.UUID] = mapped_column()
    source_system: Mapped[str] = mapped_column(String(32))
    source_record_id: Mapped[str] = mapped_column(String(128))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sync_run_id: Mapped[uuid.UUID] = mapped_column()


class Party(Lineage, Base):
    __tablename__ = "parties"
    __table_args__ = lineage_args(
        "parties", CheckConstraint("party_type IN ('customer', 'vendor')", name="party_type")
    )

    party_type: Mapped[str] = mapped_column(String(16))
    display_name: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str | None] = mapped_column(String(255))
    gstin: Mapped[str | None] = mapped_column(String(15))
    currency: Mapped[str | None] = mapped_column(String(3))


class Account(Lineage, Base):
    __tablename__ = "accounts"
    __table_args__ = lineage_args(
        "accounts",
        CheckConstraint(
            "category IN ('income', 'other_income', 'cost_of_goods_sold', 'expense', "
            "'other_expense', 'cash', 'bank', 'accounts_receivable', 'other_current_asset', "
            "'fixed_asset', 'accounts_payable', 'tax_liability', 'other_liability', 'equity', "
            "'other')",
            name="category",
        ),
        CheckConstraint("tax_role IN ('output_tax', 'input_tax')", name="tax_role"),
    )

    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str | None] = mapped_column(String(64))
    source_account_type: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    tax_role: Mapped[str | None] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Invoice(Lineage, Base):
    __tablename__ = "invoices"
    __table_args__ = lineage_args(
        "invoices",
        CheckConstraint(
            "status IN ('draft', 'open', 'partially_paid', 'paid', 'void', 'unknown')",
            name="status",
        ),
        Index("ix_invoices_connection_id_invoice_date", "connection_id", "invoice_date"),
        Index(
            "ix_invoices_connection_id_due_date_open",
            "connection_id",
            "due_date",
            postgresql_where=text("balance > 0"),
        ),
        Index("ix_invoices_connection_id_party_id", "connection_id", "party_id"),
    )

    invoice_number: Mapped[str] = mapped_column(String(64))
    party_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.parties.id", ondelete="SET NULL")
    )
    party_name: Mapped[str] = mapped_column(String(255))
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    source_status: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3))
    exchange_rate: Mapped[Decimal] = mapped_column(Rate)
    subtotal: Mapped[Decimal | None] = mapped_column(Money)
    tax_total: Mapped[Decimal | None] = mapped_column(Money)
    total: Mapped[Decimal] = mapped_column(Money)
    balance: Mapped[Decimal] = mapped_column(Money)
    total_base: Mapped[Decimal] = mapped_column(Money)
    balance_base: Mapped[Decimal] = mapped_column(Money)


class PaymentReceived(Lineage, Base):
    __tablename__ = "payments_received"
    __table_args__ = lineage_args(
        "payments_received",
        Index("ix_payments_received_connection_id_payment_date", "connection_id", "payment_date"),
    )

    party_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.parties.id", ondelete="SET NULL")
    )
    party_name: Mapped[str] = mapped_column(String(255))
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)
    amount_base: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    payment_mode: Mapped[str | None] = mapped_column(String(64))
    reference: Mapped[str | None] = mapped_column(String(128))


class Expense(Lineage, Base):
    __tablename__ = "expenses"
    __table_args__ = lineage_args(
        "expenses",
        Index("ix_expenses_connection_id_expense_date", "connection_id", "expense_date"),
    )

    expense_date: Mapped[date] = mapped_column(Date)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.accounts.id", ondelete="SET NULL")
    )
    account_name: Mapped[str] = mapped_column(String(255))
    vendor_name: Mapped[str | None] = mapped_column(String(255))
    amount_net: Mapped[Decimal] = mapped_column(Money)
    tax_amount: Mapped[Decimal] = mapped_column(Money)
    total: Mapped[Decimal] = mapped_column(Money)
    total_base: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    paid_through: Mapped[str | None] = mapped_column(String(255))


class PaymentMade(Lineage, Base):
    __tablename__ = "payments_made"
    __table_args__ = lineage_args(
        "payments_made",
        Index("ix_payments_made_connection_id_payment_date", "connection_id", "payment_date"),
    )

    party_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.parties.id", ondelete="SET NULL")
    )
    party_name: Mapped[str] = mapped_column(String(255))
    payment_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)
    amount_base: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    paid_through: Mapped[str | None] = mapped_column(String(255))


class LedgerMonthlyAmount(Lineage, Base):
    __tablename__ = "ledger_monthly_amounts"
    __table_args__ = lineage_args(
        "ledger_monthly_amounts",
        CheckConstraint(
            "section IN ('operating_income', 'cost_of_goods_sold', 'operating_expense', "
            "'non_operating_income', 'non_operating_expense')",
            name="section",
        ),
        Index(
            "ix_ledger_monthly_amounts_connection_id_period_month", "connection_id", "period_month"
        ),
    )

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.accounts.id", ondelete="SET NULL")
    )
    account_source_id: Mapped[str] = mapped_column(String(128))
    account_name: Mapped[str] = mapped_column(String(255))
    section: Mapped[str] = mapped_column(String(32))
    period_month: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)


class BalanceSnapshot(Lineage, Base):
    __tablename__ = "balance_snapshots"
    __table_args__ = lineage_args(
        "balance_snapshots",
        Index("ix_balance_snapshots_connection_id_as_of_date", "connection_id", "as_of_date"),
    )

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.accounts.id", ondelete="SET NULL")
    )
    account_source_id: Mapped[str | None] = mapped_column(String(128))
    account_name: Mapped[str] = mapped_column(String(255))
    account_group: Mapped[str] = mapped_column(String(64))
    as_of_date: Mapped[date] = mapped_column(Date)
    balance: Mapped[Decimal] = mapped_column(Money)
