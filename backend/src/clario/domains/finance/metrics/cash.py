"""Cash views (plan §24.2): billed vs collected vs spent, by month, week (Monday) and day.

Billed = invoice totals incl. GST (draft and void excluded) by invoice date. Collected = customer
payments by payment date. Expenses = expense records by expense date (vendor bill payments are
not included: pending director question 7). Net cash = collected − expenses.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from clario.core.money import ratio_percent

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class MonthRow:
    month: date  # first day of the month
    billed: Decimal
    collected: Decimal
    expenses: Decimal

    @property
    def net_cash(self) -> Decimal:
        return self.collected - self.expenses


@dataclass(frozen=True, slots=True)
class CashBucket:
    start: date
    cash_in: Decimal
    cash_out: Decimal

    @property
    def net(self) -> Decimal:
        return self.cash_in - self.cash_out


def month_rows(
    months: Iterable[date],
    billed: Mapping[date, Decimal],
    collected: Mapping[date, Decimal],
    expenses: Mapping[date, Decimal],
) -> list[MonthRow]:
    """One row per month, starting at the first month with any activity (so a young
    organisation's trend does not open with a year of empty months)."""
    rows = [
        MonthRow(m, billed.get(m, ZERO), collected.get(m, ZERO), expenses.get(m, ZERO))
        for m in months
    ]
    while rows and not (rows[0].billed or rows[0].collected or rows[0].expenses):
        rows.pop(0)
    return rows


def totals(rows: Iterable[MonthRow]) -> MonthRow:
    rows = list(rows)
    return MonthRow(
        rows[0].month if rows else date.min,
        sum((r.billed for r in rows), ZERO),
        sum((r.collected for r in rows), ZERO),
        sum((r.expenses for r in rows), ZERO),
    )


def collection_ratio(collected: Decimal, billed: Decimal) -> Decimal | None:
    """Collected ÷ billed × 100 over the same window."""
    return ratio_percent(collected, billed)


def buckets(
    starts: Iterable[date],
    days: int,
    cash_in: Mapping[date, Decimal],
    cash_out: Mapping[date, Decimal],
) -> list[CashBucket]:
    """Sum daily amounts into consecutive buckets of `days` days beginning at each start."""
    result = []
    for start in starts:
        span = [start + timedelta(days=i) for i in range(days)]
        result.append(
            CashBucket(
                start,
                sum((cash_in.get(d, ZERO) for d in span), ZERO),
                sum((cash_out.get(d, ZERO) for d in span), ZERO),
            )
        )
    return result
