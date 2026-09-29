"""Finance windows (plan §23.2, §24.2). All relative to "today" in the organisation's time zone and
its fiscal year, resolved on the server (the assistant never does date arithmetic)."""

from __future__ import annotations

from datetime import date, timedelta

from clario.core.dates import (
    DateRange,
    fiscal_year_label,
    fiscal_year_start,
    iter_month_starts,
    last_n_days,
    month_start,
    week_start,
)


def sync_window(today: date, fiscal_year_start_month: int) -> DateRange:
    """Current plus previous fiscal year, up to today (payments, expenses, the monthly ledger)."""
    current = fiscal_year_start(today, fiscal_year_start_month)
    return DateRange(current.replace(year=current.year - 1), today)


def ledger_months(today: date, fiscal_year_start_month: int) -> list[date]:
    """First day of every month in the sync window: one P&L request each (Zoho has no by-month
    grouping, verified in Phase 0)."""
    window = sync_window(today, fiscal_year_start_month)
    return list(iter_month_starts(window.start, window.end))


def fy_to_date(today: date, fiscal_year_start_month: int) -> DateRange:
    """Accrual KPIs: fiscal year to date (plan §24.2)."""
    return DateRange(fiscal_year_start(today, fiscal_year_start_month), today)


def fy_label(today: date, fiscal_year_start_month: int) -> str:
    return fiscal_year_label(today, fiscal_year_start_month)


def trend_window(today: date, fiscal_year_start_month: int) -> DateRange:
    """Billed, collected and the monthly trends: everything mirrored (current + previous FY).

    This reproduces the director's PDF, whose billed and collected figures include March 2026,
    before the fiscal year started (§22.3). Pending director question 1.
    """
    return sync_window(today, fiscal_year_start_month)


def this_month(today: date) -> DateRange:
    return DateRange(month_start(today), today)


def previous_month(today: date) -> DateRange:
    end = month_start(today) - timedelta(days=1)
    return DateRange(month_start(end), end)


def last_n_weeks(today: date, n: int) -> list[date]:
    """Mondays of the last `n` weeks, the current week last (the PDF's weekly view)."""
    current = week_start(today)
    return [current - timedelta(weeks=i) for i in range(n - 1, -1, -1)]


def last_30_days(today: date) -> DateRange:
    return last_n_days(today, 30)


# ---------------------------------------------------------------- assistant periods (plan §19.4)

PRESETS = (
    "this_month",
    "last_month",
    "this_quarter",
    "last_quarter",
    "fy_to_date",
    "last_fy",
    "last_n_days",
    "custom",
)


class PeriodError(ValueError):
    """A period the user asked for cannot be resolved (e.g. custom without dates)."""


def _quarter_start(day: date, fiscal_year_start_month: int) -> date:
    start = fiscal_year_start(day, fiscal_year_start_month)
    months = ((day.year - start.year) * 12 + day.month - start.month) // 3 * 3
    year, month = divmod(start.month - 1 + months, 12)
    return date(start.year + year, month + 1, 1)


def _label(window: DateRange) -> str:
    return f"{window.start.day} {window.start:%b %Y} – {window.end.day} {window.end:%b %Y}"


def resolve_period(
    preset: str,
    today: date,
    fiscal_year_start_month: int,
    *,
    days: int | None = None,
    start: date | None = None,
    end: date | None = None,
) -> tuple[DateRange, str]:
    """A named period → (inclusive dates, human label), in the organisation's calendar."""
    fy = fiscal_year_start_month
    if preset == "this_month":
        window = this_month(today)
        return window, f"{today:%B %Y} to date"
    if preset == "last_month":
        window = previous_month(today)
        return window, f"{window.start:%B %Y}"
    if preset == "this_quarter":
        window = DateRange(_quarter_start(today, fy), today)
        return window, f"This quarter to date ({_label(window)})"
    if preset == "last_quarter":
        current = _quarter_start(today, fy)
        previous = _quarter_start(current - timedelta(days=1), fy)
        window = DateRange(previous, current - timedelta(days=1))
        return window, f"Last quarter ({_label(window)})"
    if preset == "fy_to_date":
        window = fy_to_date(today, fy)
        return window, f"{fy_label(today, fy)} to date"
    if preset == "last_fy":
        current = fiscal_year_start(today, fy)
        window = DateRange(current.replace(year=current.year - 1), current - timedelta(days=1))
        return window, fy_label(window.start, fy)
    if preset == "last_n_days":
        n = days or 30
        if not 1 <= n <= 400:
            raise PeriodError("days must be between 1 and 400")
        window = last_n_days(today, n)
        return window, f"Last {n} days"
    if preset == "custom":
        if start is None or end is None:
            raise PeriodError("custom periods need start_date and end_date")
        if end < start:
            raise PeriodError("end_date is before start_date")
        if start > today:
            raise PeriodError("the period is in the future")
        window = DateRange(start, min(end, today))
        return window, _label(window)
    raise PeriodError(f"unknown period {preset!r}")
