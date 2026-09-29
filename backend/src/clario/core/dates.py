"""Business-date helpers. Business dates are interpreted in the workspace/organisation time zone.

The server clock is UTC in production; `date.today()` would make "days overdue" off by one for
Indian users around midnight (a defect found in the demo). Always use `today_in(tz)`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

INDIA = ZoneInfo("Asia/Kolkata")


def utc_now() -> datetime:
    return datetime.now(UTC)


def today_in(tz: ZoneInfo, now: datetime | None = None) -> date:
    """Today's date in `tz`. `now` must be timezone-aware when given (for tests)."""
    moment = now or utc_now()
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return moment.astimezone(tz).date()


@dataclass(frozen=True, slots=True)
class DateRange:
    """Inclusive date range."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("end must be on or after start")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def __contains__(self, day: object) -> bool:
        return isinstance(day, date) and self.start <= day <= self.end


def month_start(day: date) -> date:
    return day.replace(day=1)


def next_month_start(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def month_range(day: date) -> DateRange:
    return DateRange(month_start(day), next_month_start(day) - timedelta(days=1))


def iter_month_starts(start: date, end: date) -> Iterator[date]:
    """First day of every month touching [start, end]."""
    current = month_start(start)
    while current <= end:
        yield current
        current = next_month_start(current)


def week_start(day: date) -> date:
    """Monday of the week containing `day` (the director's weekly view starts on Monday)."""
    return day - timedelta(days=day.weekday())


def last_n_days(today: date, n: int) -> DateRange:
    if n < 1:
        raise ValueError("n must be at least 1")
    return DateRange(today - timedelta(days=n - 1), today)


def fiscal_year_start(day: date, start_month: int = 4) -> date:
    """Start of the fiscal year containing `day`. India: April (4)."""
    if not 1 <= start_month <= 12:
        raise ValueError("start_month must be 1..12")
    year = day.year if day.month >= start_month else day.year - 1
    return date(year, start_month, 1)


def fiscal_year_range(day: date, start_month: int = 4) -> DateRange:
    start = fiscal_year_start(day, start_month)
    end = date(start.year + 1, start.month, 1) - timedelta(days=1)
    return DateRange(start, end)


def fiscal_year_label(day: date, start_month: int = 4) -> str:
    """'FY 2026-27' style label; calendar-year fiscal years render as 'FY 2026'."""
    fy = fiscal_year_range(day, start_month)
    if fy.start.year == fy.end.year:
        return f"FY {fy.start.year}"
    return f"FY {fy.start.year}-{str(fy.end.year)[-2:]}"
