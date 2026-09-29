"""The FinanceSource port (plan §23.1): what a finance connector implements.

The ingest decides windows; a source returns exactly what it is asked for and must never truncate
silently: if it cannot return everything, it raises (e.g. `zoho.too_many_records`).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from clario.core.dates import DateRange
from clario.domains.finance.schemas import (
    Account,
    BalanceAmount,
    Expense,
    Invoice,
    LedgerAmount,
    Party,
    PaymentMade,
    PaymentReceived,
)


@runtime_checkable
class FinanceSource(Protocol):
    async def fetch_accounts(self) -> Sequence[Account]: ...

    async def fetch_parties(self) -> Sequence[Party]: ...

    async def fetch_invoices(self) -> Sequence[Invoice]: ...

    async def fetch_payments_received(self, window: DateRange) -> Sequence[PaymentReceived]: ...

    async def fetch_expenses(self, window: DateRange) -> Sequence[Expense]: ...

    async def fetch_payments_made(self, window: DateRange) -> Sequence[PaymentMade]: ...

    async def fetch_ledger_month(self, month: date) -> Sequence[LedgerAmount]:
        """Accrual P&L of one calendar month, per account and section."""
        ...

    async def fetch_balances(self, as_of: date) -> Sequence[BalanceAmount]: ...
