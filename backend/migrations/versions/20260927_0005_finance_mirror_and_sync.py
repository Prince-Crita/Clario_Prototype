"""Finance mirror and sync bookkeeping (Phase 6; plan §14.2, §14.3, §31).

* `core.sync_runs`, `core.connection_datasets`: runs and per-dataset freshness.
* `finance.*`: parties, accounts, invoices, payments received, expenses, payments made, monthly
  ledger amounts, balance snapshots — each with lineage columns, a composite FK to its connection
  (same workspace, cascade) and a unique `(connection_id, source_record_id)`.
  (Tax periods wait for a GST-enabled organisation to verify the source: plan risk R2.)

Revision ID: 0005_finance
Revises: 0004_connections
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_finance"
down_revision: str | None = "0004_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'partial', 'failed')",
            name=op.f("ck_sync_runs_status"),
        ),
        sa.CheckConstraint(
            "trigger IN ('initial', 'manual', 'stale', 'scheduled')",
            name=op.f("ck_sync_runs_trigger"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_sync_runs_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["core.users.id"],
            name=op.f("fk_sync_runs_requested_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_runs")),
        schema="core",
    )
    op.create_index(
        "ix_sync_runs_connection_id_started_at",
        "sync_runs",
        ["connection_id", sa.literal_column("started_at DESC")],
        unique=False,
        schema="core",
    )
    op.create_table(
        "accounts",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("source_account_type", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("tax_role", sa.String(length=16), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "category IN ('income', 'other_income', 'cost_of_goods_sold', 'expense', 'other_expense', 'cash', 'bank', 'accounts_receivable', 'other_current_asset', 'fixed_asset', 'accounts_payable', 'tax_liability', 'other_liability', 'equity', 'other')",
            name=op.f("ck_accounts_category"),
        ),
        sa.CheckConstraint(
            "tax_role IN ('output_tax', 'input_tax')", name=op.f("ck_accounts_tax_role")
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_accounts_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("connection_id", "source_record_id", name="uq_accounts_source_record"),
        schema="finance",
    )
    op.create_table(
        "parties",
        sa.Column("party_type", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "party_type IN ('customer', 'vendor')", name=op.f("ck_parties_party_type")
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_parties_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parties")),
        sa.UniqueConstraint("connection_id", "source_record_id", name="uq_parties_source_record"),
        schema="finance",
    )
    op.create_table(
        "connection_datasets",
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_id", sa.Uuid(), nullable=True),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IN ('ok', 'failed')", name=op.f("ck_connection_datasets_status")
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_connection_datasets_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["last_run_id"],
            ["core.sync_runs.id"],
            name=op.f("fk_connection_datasets_last_run_id_sync_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("connection_id", "dataset", name=op.f("pk_connection_datasets")),
        schema="core",
    )
    op.create_table(
        "balance_snapshots",
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("account_source_id", sa.String(length=128), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("account_group", sa.String(length=64), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("balance", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["finance.accounts.id"],
            name=op.f("fk_balance_snapshots_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_balance_snapshots_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_balance_snapshots")),
        sa.UniqueConstraint(
            "connection_id", "source_record_id", name="uq_balance_snapshots_source_record"
        ),
        schema="finance",
    )
    op.create_index(
        "ix_balance_snapshots_connection_id_as_of_date",
        "balance_snapshots",
        ["connection_id", "as_of_date"],
        unique=False,
        schema="finance",
    )
    op.create_table(
        "expenses",
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("vendor_name", sa.String(length=255), nullable=True),
        sa.Column("amount_net", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("total", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("total_base", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("paid_through", sa.String(length=255), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["finance.accounts.id"],
            name=op.f("fk_expenses_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_expenses_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
        sa.UniqueConstraint("connection_id", "source_record_id", name="uq_expenses_source_record"),
        schema="finance",
    )
    op.create_index(
        "ix_expenses_connection_id_expense_date",
        "expenses",
        ["connection_id", "expense_date"],
        unique=False,
        schema="finance",
    )
    op.create_table(
        "invoices",
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("party_id", sa.Uuid(), nullable=True),
        sa.Column("party_name", sa.String(length=255), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("source_status", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=19, scale=4), nullable=True),
        sa.Column("tax_total", sa.Numeric(precision=19, scale=4), nullable=True),
        sa.Column("total", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("balance", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("total_base", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("balance_base", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'partially_paid', 'paid', 'void', 'unknown')",
            name=op.f("ck_invoices_status"),
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_invoices_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["finance.parties.id"],
            name=op.f("fk_invoices_party_id_parties"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint("connection_id", "source_record_id", name="uq_invoices_source_record"),
        schema="finance",
    )
    op.create_index(
        "ix_invoices_connection_id_due_date_open",
        "invoices",
        ["connection_id", "due_date"],
        unique=False,
        schema="finance",
        postgresql_where=sa.text("balance > 0"),
    )
    op.create_index(
        "ix_invoices_connection_id_invoice_date",
        "invoices",
        ["connection_id", "invoice_date"],
        unique=False,
        schema="finance",
    )
    op.create_index(
        "ix_invoices_connection_id_party_id",
        "invoices",
        ["connection_id", "party_id"],
        unique=False,
        schema="finance",
    )
    op.create_table(
        "ledger_monthly_amounts",
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("account_source_id", sa.String(length=128), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("section", sa.String(length=32), nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "section IN ('operating_income', 'cost_of_goods_sold', 'operating_expense', 'non_operating_income', 'non_operating_expense')",
            name=op.f("ck_ledger_monthly_amounts_section"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["finance.accounts.id"],
            name=op.f("fk_ledger_monthly_amounts_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_ledger_monthly_amounts_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ledger_monthly_amounts")),
        sa.UniqueConstraint(
            "connection_id", "source_record_id", name="uq_ledger_monthly_amounts_source_record"
        ),
        schema="finance",
    )
    op.create_index(
        "ix_ledger_monthly_amounts_connection_id_period_month",
        "ledger_monthly_amounts",
        ["connection_id", "period_month"],
        unique=False,
        schema="finance",
    )
    op.create_table(
        "payments_made",
        sa.Column("party_id", sa.Uuid(), nullable=True),
        sa.Column("party_name", sa.String(length=255), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("amount_base", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("paid_through", sa.String(length=255), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_payments_made_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["finance.parties.id"],
            name=op.f("fk_payments_made_party_id_parties"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments_made")),
        sa.UniqueConstraint(
            "connection_id", "source_record_id", name="uq_payments_made_source_record"
        ),
        schema="finance",
    )
    op.create_index(
        "ix_payments_made_connection_id_payment_date",
        "payments_made",
        ["connection_id", "payment_date"],
        unique=False,
        schema="finance",
    )
    op.create_table(
        "payments_received",
        sa.Column("party_id", sa.Uuid(), nullable=True),
        sa.Column("party_name", sa.String(length=255), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("amount_base", sa.Numeric(precision=19, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_mode", sa.String(length=64), nullable=True),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_payments_received_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["finance.parties.id"],
            name=op.f("fk_payments_received_party_id_parties"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments_received")),
        sa.UniqueConstraint(
            "connection_id", "source_record_id", name="uq_payments_received_source_record"
        ),
        schema="finance",
    )
    op.create_index(
        "ix_payments_received_connection_id_payment_date",
        "payments_received",
        ["connection_id", "payment_date"],
        unique=False,
        schema="finance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payments_received_connection_id_payment_date",
        table_name="payments_received",
        schema="finance",
    )
    op.drop_table("payments_received", schema="finance")
    op.drop_index(
        "ix_payments_made_connection_id_payment_date", table_name="payments_made", schema="finance"
    )
    op.drop_table("payments_made", schema="finance")
    op.drop_index(
        "ix_ledger_monthly_amounts_connection_id_period_month",
        table_name="ledger_monthly_amounts",
        schema="finance",
    )
    op.drop_table("ledger_monthly_amounts", schema="finance")
    op.drop_index("ix_invoices_connection_id_party_id", table_name="invoices", schema="finance")
    op.drop_index("ix_invoices_connection_id_invoice_date", table_name="invoices", schema="finance")
    op.drop_index(
        "ix_invoices_connection_id_due_date_open",
        table_name="invoices",
        schema="finance",
        postgresql_where=sa.text("balance > 0"),
    )
    op.drop_table("invoices", schema="finance")
    op.drop_index("ix_expenses_connection_id_expense_date", table_name="expenses", schema="finance")
    op.drop_table("expenses", schema="finance")
    op.drop_index(
        "ix_balance_snapshots_connection_id_as_of_date",
        table_name="balance_snapshots",
        schema="finance",
    )
    op.drop_table("balance_snapshots", schema="finance")
    op.drop_table("connection_datasets", schema="core")
    op.drop_table("parties", schema="finance")
    op.drop_table("accounts", schema="finance")
    op.drop_index("ix_sync_runs_connection_id_started_at", table_name="sync_runs", schema="core")
    op.drop_table("sync_runs", schema="core")
