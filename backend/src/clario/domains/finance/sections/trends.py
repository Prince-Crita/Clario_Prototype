"""Trends & Analysis tab (plan §22.2): month-on-month cash table, expense trend by category (top
five, stacked), net cash trend (the table's net column), weekly cash flow for the last 10 weeks
(weeks start Monday) and daily cash movement for the last 30 days. All on a cash basis."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from clario.core.dates import DateRange
from clario.domains.finance import repository as repo
from clario.domains.finance.metrics import cash
from clario.domains.finance.periods import last_30_days, last_n_weeks, trend_window
from clario.domains.finance.sections.common import month_out, month_rows
from clario.domains.finance.sections.context import FinanceContext, window
from clario.domains.finance.sections.dto import CashBucketOut, CategoryMonth, Trends

ZERO = Decimal(0)
TOP_CATEGORIES = 5
WEEKS = 10


def _bucket_out(bucket: cash.CashBucket) -> CashBucketOut:
    return CashBucketOut(
        start=bucket.start, cash_in=bucket.cash_in, cash_out=bucket.cash_out, net=bucket.net
    )


def expense_trend(
    rows: list[tuple[date, str, Decimal]], months: list[date]
) -> tuple[list[str], list[CategoryMonth]]:
    """Top five categories over the whole window (ties by name), then per month with the rest
    summed as 'other' so every month's bars add up to its expenses."""
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_month: dict[date, dict[str, Decimal]] = defaultdict(dict)
    for month, name, amount in rows:
        totals[name] += amount
        by_month[month][name] = by_month[month].get(name, ZERO) + amount
    top = [n for n, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_CATEGORIES]]
    trend = [
        CategoryMonth(
            month=month,
            amounts={name: by_month[month].get(name, ZERO) for name in top},
            other=sum((v for n, v in by_month[month].items() if n not in top), ZERO),
        )
        for month in months
    ]
    return top, trend


async def build(ctx: FinanceContext) -> Trends:
    today, fy_month = ctx.today, ctx.fiscal_year_start_month
    trend = trend_window(today, fy_month)
    rows = await month_rows(ctx, trend)
    first = rows[0].month if rows else today.replace(day=1)
    top, categories = expense_trend(
        await repo.expenses_by_category_month(ctx.session, ctx.scope, trend),
        [r.month for r in rows],
    )

    weeks = last_n_weeks(today, WEEKS)
    recent = DateRange(min(weeks[0], last_30_days(today).start), today)
    cash_in = await repo.collected_by_day(ctx.session, ctx.scope, recent)
    cash_out = await repo.expenses_by_day(ctx.session, ctx.scope, recent)
    daily = last_30_days(today)
    days = [daily.start + timedelta(days=i) for i in range(daily.days)]

    return Trends(
        meta=ctx.meta,
        window=window(first, today),
        months=[month_out(r) for r in rows],
        totals=month_out(cash.totals(rows)),
        top_categories=top,
        expense_trend=categories,
        weekly=[_bucket_out(b) for b in cash.buckets(weeks, 7, cash_in, cash_out)],
        daily=[_bucket_out(b) for b in cash.buckets(days, 1, cash_in, cash_out)],
    )
