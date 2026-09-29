"""The finance datasets, in the order the sync engine writes them (plan §23.2).

Accounts and parties come first because later datasets reference them. Each dataset fetches from
the connection's `FinanceSource`, maps to mirror rows, and replaces its window in one transaction.
Windows: accounts, parties, invoices — everything; payments, expenses, vendor payments and the
monthly ledger — current + previous fiscal year up to today; balances — today.
Tax periods (GST) are not synced yet: no GST-enabled organisation has been available to verify the
source (plan risk R2).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.errors import UpstreamError
from clario.domains.finance import ingest
from clario.domains.finance import models as m
from clario.domains.finance.periods import ledger_months, sync_window
from clario.domains.finance.ports import FinanceSource
from clario.platform.access.scopes import ConnectionScope
from clario.platform.integrations.contract import IngestContext, IngestResult

Ingest = Callable[[IngestContext, FinanceSource], Awaitable[IngestResult]]


@dataclass(frozen=True, slots=True)
class FinanceDataset:
    key: str
    label: str
    model: type[m.Lineage]
    run: Ingest

    async def ingest(self, context: IngestContext) -> IngestResult:
        source = context.source
        if not isinstance(source, FinanceSource):
            raise TypeError(f"{type(source).__name__} does not implement FinanceSource")
        return await self.run(context, source)

    async def purge(self, session: AsyncSession, scope: ConnectionScope) -> None:
        await ingest.purge(session, self.model, scope)


def _replace(
    context: IngestContext, model: type[m.Lineage], rows: list[dict[str, Any]], **kw: Any
) -> Awaitable[int]:
    return ingest.replace_window(
        context.session, model, context.scope, context.run_id, ingest.unique_by_source(rows), **kw
    )


# ---------------------------------------------------------------- reference data


async def _accounts(context: IngestContext, source: FinanceSource) -> IngestResult:
    rows = [
        {
            "source_record_id": a.source_id,
            "source_updated_at": a.source_updated_at,
            "name": a.name,
            "code": a.code,
            "source_account_type": a.source_account_type,
            "category": a.category.value,
            "tax_role": a.tax_role.value if a.tax_role else None,
            "is_active": a.is_active,
        }
        for a in await source.fetch_accounts()
    ]
    return IngestResult(await _replace(context, m.Account, rows))


async def _parties(context: IngestContext, source: FinanceSource) -> IngestResult:
    rows = [
        {
            "source_record_id": p.source_id,
            "source_updated_at": p.source_updated_at,
            "party_type": p.party_type.value,
            "display_name": p.display_name,
            "company_name": p.company_name,
            "gstin": p.gstin,
            "currency": p.currency,
        }
        for p in await source.fetch_parties()
    ]
    return IngestResult(await _replace(context, m.Party, rows))


# ---------------------------------------------------------------- documents


async def _invoices(context: IngestContext, source: FinanceSource) -> IngestResult:
    parties = await ingest.party_ids(context.session, context.scope)
    rows = [
        {
            "source_record_id": i.source_id,
            "source_updated_at": i.source_updated_at,
            "invoice_number": i.invoice_number,
            "party_id": parties.get(i.party_source_id or ""),
            "party_name": i.party_name,
            "invoice_date": i.invoice_date,
            "due_date": i.due_date,
            "source_status": i.source_status,
            "status": i.status.value,
            "currency": i.currency,
            "exchange_rate": i.exchange_rate,
            "subtotal": i.subtotal,
            "tax_total": i.tax_total,
            "total": i.total,
            "balance": i.balance,
            "total_base": i.total_base,
            "balance_base": i.balance_base,
        }
        for i in await source.fetch_invoices()
    ]
    return IngestResult(await _replace(context, m.Invoice, rows))


async def _payments_received(context: IngestContext, source: FinanceSource) -> IngestResult:
    window = sync_window(context.today, context.fiscal_year_start_month)
    parties = await ingest.party_ids(context.session, context.scope)
    rows = [
        {
            "source_record_id": p.source_id,
            "source_updated_at": p.source_updated_at,
            "party_id": parties.get(p.party_source_id or ""),
            "party_name": p.party_name,
            "payment_date": p.payment_date,
            "amount": p.amount,
            "amount_base": p.amount_base,
            "currency": p.currency,
            "payment_mode": p.payment_mode,
            "reference": p.reference,
        }
        for p in await source.fetch_payments_received(window)
        if p.payment_date in window  # never trust a source's date filter
    ]
    count = await _replace(
        context,
        m.PaymentReceived,
        rows,
        window=m.PaymentReceived.payment_date.between(window.start, window.end),
    )
    return IngestResult(count, window.start, window.end)


async def _expenses(context: IngestContext, source: FinanceSource) -> IngestResult:
    window = sync_window(context.today, context.fiscal_year_start_month)
    accounts = await ingest.account_ids_by_name(context.session, context.scope)
    rows = [
        {
            "source_record_id": e.source_id,
            "source_updated_at": e.source_updated_at,
            "expense_date": e.expense_date,
            "account_id": accounts.get(e.account_name.casefold()),
            "account_name": e.account_name,
            "vendor_name": e.vendor_name,
            "amount_net": e.amount_net,
            "tax_amount": e.tax_amount,
            "total": e.total,
            "total_base": e.total_base,
            "currency": e.currency,
            "paid_through": e.paid_through,
        }
        for e in await source.fetch_expenses(window)
        if e.expense_date in window
    ]
    count = await _replace(
        context, m.Expense, rows, window=m.Expense.expense_date.between(window.start, window.end)
    )
    return IngestResult(count, window.start, window.end)


async def _payments_made(context: IngestContext, source: FinanceSource) -> IngestResult:
    window = sync_window(context.today, context.fiscal_year_start_month)
    parties = await ingest.party_ids(context.session, context.scope)
    rows = [
        {
            "source_record_id": p.source_id,
            "source_updated_at": p.source_updated_at,
            "party_id": parties.get(p.party_source_id or ""),
            "party_name": p.party_name,
            "payment_date": p.payment_date,
            "amount": p.amount,
            "amount_base": p.amount_base,
            "currency": p.currency,
            "paid_through": p.paid_through,
        }
        for p in await source.fetch_payments_made(window)
        if p.payment_date in window
    ]
    count = await _replace(
        context,
        m.PaymentMade,
        rows,
        window=m.PaymentMade.payment_date.between(window.start, window.end),
    )
    return IngestResult(count, window.start, window.end)


# ---------------------------------------------------------------- reports


async def _ledger_monthly(context: IngestContext, source: FinanceSource) -> IngestResult:
    months = ledger_months(context.today, context.fiscal_year_start_month)
    accounts = await ingest.account_ids(context.session, context.scope)
    rows: list[dict[str, Any]] = []
    for month in months:
        for line in await source.fetch_ledger_month(month):
            if line.period_month != month:
                raise UpstreamError(
                    "The source returned a different month than requested.",
                    code="finance.ledger_month_mismatch",
                )
            rows.append(
                {
                    "source_record_id": (
                        f"{line.account_source_id}:{line.section.value}:{month:%Y-%m}"
                    ),
                    "source_updated_at": None,
                    "account_id": accounts.get(line.account_source_id),
                    "account_source_id": line.account_source_id,
                    "account_name": line.account_name,
                    "section": line.section.value,
                    "period_month": month,
                    "amount": line.amount,
                }
            )
    first, last = months[0], months[-1]
    count = await _replace(
        context,
        m.LedgerMonthlyAmount,
        rows,
        window=m.LedgerMonthlyAmount.period_month.between(first, last),
    )
    return IngestResult(count, first, context.today)


async def _balances(context: IngestContext, source: FinanceSource) -> IngestResult:
    today = context.today
    accounts = await ingest.account_ids(context.session, context.scope)
    rows = [
        {
            "source_record_id": f"{b.account_source_id or 'line:' + b.account_name}:{today}",
            "source_updated_at": None,
            "account_id": accounts.get(b.account_source_id or ""),
            "account_source_id": b.account_source_id,
            "account_name": b.account_name,
            "account_group": b.group,
            "as_of_date": today,
            "balance": b.balance,
        }
        for b in await source.fetch_balances(today)
    ]
    count = await _replace(
        context, m.BalanceSnapshot, rows, window=m.BalanceSnapshot.as_of_date == today
    )
    return IngestResult(count, today, today)


DATASETS: tuple[FinanceDataset, ...] = (
    FinanceDataset("accounts", "Chart of accounts", m.Account, _accounts),
    FinanceDataset("parties", "Customers and vendors", m.Party, _parties),
    FinanceDataset("invoices", "Invoices", m.Invoice, _invoices),
    FinanceDataset("payments_received", "Customer payments", m.PaymentReceived, _payments_received),
    FinanceDataset("expenses", "Expenses", m.Expense, _expenses),
    FinanceDataset("payments_made", "Vendor payments", m.PaymentMade, _payments_made),
    FinanceDataset(
        "ledger_monthly", "Monthly profit & loss", m.LedgerMonthlyAmount, _ledger_monthly
    ),
    FinanceDataset("balances", "Balance sheet", m.BalanceSnapshot, _balances),
)
