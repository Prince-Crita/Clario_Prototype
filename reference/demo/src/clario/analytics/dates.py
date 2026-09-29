"""Date period helpers used by analytics and tools."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import NamedTuple


class DateRange(NamedTuple):
    start: date
    end: date

    def as_iso(self) -> tuple[str, str]:
        return self.start.isoformat(), self.end.isoformat()

    def day_count(self) -> int:
        return (self.end - self.start).days + 1


def parse_iso_date(value: str | date | None, field_name: str = "date") -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}: {value!r}. Use YYYY-MM-DD.") from exc


def today() -> date:
    return date.today()


def month_to_date(as_of: date | None = None) -> DateRange:
    as_of = as_of or today()
    return DateRange(start=as_of.replace(day=1), end=as_of)


def previous_month(as_of: date | None = None) -> DateRange:
    as_of = as_of or today()
    first_this_month = as_of.replace(day=1)
    last_prev = first_this_month - timedelta(days=1)
    return DateRange(start=last_prev.replace(day=1), end=last_prev)


def equivalent_previous_period(current: DateRange) -> DateRange:
    length = current.day_count()
    prev_end = current.start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return DateRange(start=prev_start, end=prev_end)


def days_between(start: date, end: date) -> int:
    return (end - start).days


def in_range(value: date | None, rng: DateRange) -> bool:
    if value is None:
        return False
    return rng.start <= value <= rng.end


def validate_range(
    start: date,
    end: date,
    *,
    max_days: int = 366,
) -> DateRange:
    if end < start:
        raise ValueError("end_date must be on or after start_date.")
    rng = DateRange(start=start, end=end)
    if rng.day_count() > max_days:
        raise ValueError(f"Date range cannot exceed {max_days} days.")
    return rng
