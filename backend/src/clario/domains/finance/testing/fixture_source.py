"""`FixtureFinanceSource`: a `FinanceSource` backed by records in the repository (plan §32).

Three datasets:
  * `golden_dataset()` — reproduces every figure in the director's Command Centre PDFs (§22.3);
    the finance acceptance test (§24.4). With `FINANCE_FIXTURE_SOURCE=true` (refused in
    production) development syncs serve it, so dashboards look like the PDF without Zoho.
    Its amounts are real: never send them to the AI provider (R6).
  * `evaluation_dataset()` — synthetic TEST figures for the assistant evaluation (§32) and for
    trying the assistant locally (`FINANCE_FIXTURE_DATASET=evaluation`).
  * `test_dataset()` — the Phase 0 TEST data from the Zoho trial organisation, as canonical
    records (what a real sync of that organisation produces).
"""

from __future__ import annotations

import json
import types
from collections.abc import Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from clario.core.dates import DateRange
from clario.domains.finance import schemas
from clario.settings import Settings

TEST_DATASET = Path(__file__).with_name("fixture_dataset.json")


@dataclass(frozen=True, slots=True)
class FinanceRecords:
    accounts: tuple[schemas.Account, ...]
    parties: tuple[schemas.Party, ...]
    invoices: tuple[schemas.Invoice, ...]
    payments_received: tuple[schemas.PaymentReceived, ...]
    expenses: tuple[schemas.Expense, ...]
    payments_made: tuple[schemas.PaymentMade, ...]
    ledger: tuple[schemas.LedgerAmount, ...]
    balances: tuple[schemas.BalanceAmount, ...]  # `as_of` is replaced by the requested date


def _convert(kind: Any, value: Any) -> Any:
    if value is None:
        return None
    if get_origin(kind) in (Union, types.UnionType):
        options = [k for k in get_args(kind) if k is not type(None)]
        return _convert(options[0], value)
    if kind is Decimal:
        return Decimal(value)
    if kind is date:
        return date.fromisoformat(value)
    if kind is datetime:
        return datetime.fromisoformat(value)
    if isinstance(kind, type) and issubclass(kind, Enum):
        return kind(value)
    return value


def _build[R](cls: type[R], data: dict[str, Any]) -> R:
    assert is_dataclass(cls)
    hints = get_type_hints(cls)
    return cls(**{f.name: _convert(hints[f.name], data[f.name]) for f in fields(cls)})


@cache
def test_dataset() -> FinanceRecords:
    raw: dict[str, Any] = json.loads(TEST_DATASET.read_text(encoding="utf-8"))

    def rows[R](key: str, cls: type[R]) -> tuple[R, ...]:
        return tuple(_build(cls, row) for row in raw[key])

    return FinanceRecords(
        accounts=rows("accounts", schemas.Account),
        parties=rows("parties", schemas.Party),
        invoices=rows("invoices", schemas.Invoice),
        payments_received=rows("payments_received", schemas.PaymentReceived),
        expenses=rows("expenses", schemas.Expense),
        payments_made=rows("payments_made", schemas.PaymentMade),
        ledger=rows("ledger", schemas.LedgerAmount),
        balances=rows("balances", schemas.BalanceAmount),
    )


class FixtureFinanceSource:
    api_calls = 0
    rate_limit = None

    def __init__(self, records: FinanceRecords) -> None:
        self.records = records

    async def fetch_accounts(self) -> Sequence[schemas.Account]:
        return self.records.accounts

    async def fetch_parties(self) -> Sequence[schemas.Party]:
        return self.records.parties

    async def fetch_invoices(self) -> Sequence[schemas.Invoice]:
        return self.records.invoices

    async def fetch_payments_received(self, window: DateRange) -> Sequence[schemas.PaymentReceived]:
        return [r for r in self.records.payments_received if r.payment_date in window]

    async def fetch_expenses(self, window: DateRange) -> Sequence[schemas.Expense]:
        return [r for r in self.records.expenses if r.expense_date in window]

    async def fetch_payments_made(self, window: DateRange) -> Sequence[schemas.PaymentMade]:
        return [r for r in self.records.payments_made if r.payment_date in window]

    async def fetch_ledger_month(self, month: date) -> Sequence[schemas.LedgerAmount]:
        return [r for r in self.records.ledger if r.period_month == month]

    async def fetch_balances(self, as_of: date) -> Sequence[schemas.BalanceAmount]:
        return [
            schemas.BalanceAmount(r.account_source_id, r.account_name, r.group, as_of, r.balance)
            for r in self.records.balances
        ]


def fixture_source(settings: Settings) -> FixtureFinanceSource | None:
    if not settings.finance_fixture_source:
        return None
    if settings.finance_fixture_dataset == "evaluation":
        from clario.domains.finance.testing.evaluation import evaluation_dataset

        return FixtureFinanceSource(evaluation_dataset())
    from clario.domains.finance.testing.golden import golden_dataset

    return FixtureFinanceSource(golden_dataset())
