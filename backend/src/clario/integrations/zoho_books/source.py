"""`ZohoFinanceSource`: Zoho Books as a `FinanceSource` (plan §16.4, §23).

Lists are read in full and filtered to the window here, not with Zoho date parameters: those
parameters were not verified in Phase 0, and a filter Zoho silently ignored or misread would change
figures. The cost is small for an SME (200 records per call).
Reports: the monthly P&L is one call per month (Zoho ignores `group_by=month`), the balance sheet
one call. A refresh of two fiscal years is about 35-45 calls.
"""

from __future__ import annotations

import calendar
from collections.abc import Awaitable, Callable, Sequence
from datetime import date
from functools import partial
from typing import Any, TypeVar

from clario.core.dates import DateRange
from clario.core.errors import ConflictError
from clario.domains.finance.schemas import (
    Account,
    BalanceAmount,
    Expense,
    Invoice,
    LedgerAmount,
    Party,
    PartyType,
    PaymentMade,
    PaymentReceived,
)
from clario.integrations.zoho_books import mapping
from clario.integrations.zoho_books.client import ZohoBooksClient
from clario.integrations.zoho_books.tokens import valid_secret
from clario.platform.connections import repository as connection_repo
from clario.platform.integrations.contract import ConnectionContext

T = TypeVar("T")


class ZohoFinanceSource:
    def __init__(self, context: ConnectionContext) -> None:
        self._context = context
        self._client: ZohoBooksClient | None = None
        self._token: str | None = None
        self.api_calls = 0
        self.rate_limit: dict[str, Any] | None = None

    async def _call(self, work: Callable[[ZohoBooksClient], Awaitable[T]]) -> T:
        client = await self._ready()
        before = client.calls
        try:
            return await work(client)
        finally:
            self.api_calls += client.calls - before
            self.rate_limit = client.rate_limit or self.rate_limit

    async def _ready(self) -> ZohoBooksClient:
        context = self._context
        secret = await valid_secret(context)  # refreshes (and stores) the token when needed
        await context.session.commit()
        if self._client is None or secret.access_token != self._token:
            if self._client is not None:
                await self._client.__aexit__(None, None, None)
            connection = await connection_repo.get_live(
                context.session, context.scope, context.scope.connection_id
            )
            if connection is None or not connection.external_account_id:
                raise ConflictError(
                    "This connection has no Zoho Books organisation.", code="connection.no_account"
                )
            self._client = ZohoBooksClient(
                secret.api_domain,
                secret.access_token,
                organization_id=connection.external_account_id,
                max_pages=context.settings.zoho_max_pages,
                requests_per_minute=context.settings.zoho_requests_per_minute,
            )
            self._token = secret.access_token
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    # ------------------------------------------------------------ FinanceSource

    async def fetch_accounts(self) -> Sequence[Account]:
        rows = await self._call(lambda c: c.paginate("chartofaccounts", "chartofaccounts"))
        return [mapping.to_account(r) for r in rows]

    async def fetch_parties(self) -> Sequence[Party]:
        parties: list[Party] = []
        for party_type in (PartyType.CUSTOMER, PartyType.VENDOR):
            rows = await self._call(partial(_contacts, contact_type=party_type.value))
            parties.extend(mapping.to_party(r, party_type) for r in rows)
        return parties

    async def fetch_invoices(self) -> Sequence[Invoice]:
        rows = await self._call(lambda c: c.paginate("invoices", "invoices"))
        return [mapping.to_invoice(r) for r in rows]

    async def fetch_payments_received(self, window: DateRange) -> Sequence[PaymentReceived]:
        rows = await self._call(lambda c: c.paginate("customerpayments", "customerpayments"))
        payments = [mapping.to_payment_received(r) for r in rows]
        return [p for p in payments if p.payment_date in window]

    async def fetch_expenses(self, window: DateRange) -> Sequence[Expense]:
        rows = await self._call(lambda c: c.paginate("expenses", "expenses"))
        expenses = [mapping.to_expense(r) for r in rows]
        return [e for e in expenses if e.expense_date in window]

    async def fetch_payments_made(self, window: DateRange) -> Sequence[PaymentMade]:
        rows = await self._call(lambda c: c.paginate("vendorpayments", "vendorpayments"))
        payments = [mapping.to_payment_made(r) for r in rows]
        return [p for p in payments if p.payment_date in window]

    async def fetch_ledger_month(self, month: date) -> Sequence[LedgerAmount]:
        last = month.replace(day=calendar.monthrange(month.year, month.month)[1])
        report = await self._call(
            lambda c: c.get(
                "reports/profitandloss",
                {"from_date": month.isoformat(), "to_date": last.isoformat()},
            )
        )
        return mapping.ledger_month(report, month)

    async def fetch_balances(self, as_of: date) -> Sequence[BalanceAmount]:
        report = await self._call(
            lambda c: c.get("reports/balancesheet", {"to_date": as_of.isoformat()})
        )
        return mapping.balance_lines(report, as_of)


async def _contacts(client: ZohoBooksClient, *, contact_type: str) -> list[dict[str, Any]]:
    return await client.paginate("contacts", "contacts", {"contact_type": contact_type})
