"""Exact money arithmetic and Indian-style formatting (plan §14.1, §19.3, §24.2).

Rules:
  * Amounts are `Decimal` end to end. Floats are rejected, because Zoho sends JSON floats and they
    must be parsed with `json.loads(..., parse_float=Decimal)` before reaching domain code.
  * Compute at full precision; round only for presentation, half-up.
  * Formatting uses Indian digit grouping (12,45,300) and a true minus sign (−).

The formatting behaviour is pinned by `contracts/money-format-vectors.json`, which the frontend's
formatter must also pass, so the dashboard and the assistant display identical strings.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MINUS = "−"
RUPEE = "₹"
_LAKH = Decimal(100_000)
_CRORE = Decimal(10_000_000)


def to_decimal(value: Decimal | int | str | None) -> Decimal:
    """Convert to Decimal. None/'' → 0. Floats are refused to protect precision."""
    if isinstance(value, bool):
        raise TypeError("bool is not a monetary value")
    if isinstance(value, float):
        raise TypeError("float is not allowed for money; parse JSON with parse_float=Decimal")
    if value is None or value == "":
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"not a decimal amount: {value!r}") from exc


def round_half_up(value: Decimal, places: int = 2) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def percent_change(current: Decimal, previous: Decimal) -> Decimal | None:
    """(current − previous) ÷ |previous| × 100; None when previous is zero (undefined)."""
    if previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


def ratio_percent(part: Decimal, whole: Decimal) -> Decimal | None:
    return None if whole == 0 else part / whole * 100


def _group_indian(integer_digits: str) -> str:
    if len(integer_digits) <= 3:
        return integer_digits
    head, tail = integer_digits[:-3], integer_digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def format_inr(value: Decimal, *, decimals: int = 0, symbol: bool = True) -> str:
    """₹12,45,300 · −₹6,48,028 · ₹1,234.50 (decimals=2)."""
    rounded = round_half_up(value, decimals)
    sign = MINUS if rounded < 0 else ""
    integer, _, fraction = f"{abs(rounded):.{decimals}f}".partition(".")
    body = _group_indian(integer) + (f".{fraction}" if decimals else "")
    return f"{sign}{RUPEE if symbol else ''}{body}"


def format_inr_compact(value: Decimal) -> str:
    """Business-friendly short form: ₹4.82 lakh · ₹1.2 crore · ₹62,000 (below one lakh)."""
    magnitude = abs(value)
    if magnitude < _LAKH:
        return format_inr(value)
    unit, divisor = ("crore", _CRORE) if magnitude >= _CRORE else ("lakh", _LAKH)
    scaled = round_half_up(magnitude / divisor, 2)
    if unit == "lakh" and scaled >= 100:  # 99.999… lakh rounds to 100 lakh → show as 1 crore
        unit, scaled = "crore", round_half_up(magnitude / _CRORE, 2)
    scaled = scaled.normalize()
    text = f"{scaled:f}"
    sign = MINUS if value < 0 else ""
    return f"{sign}{RUPEE}{text} {unit}"


def format_percent(value: Decimal | None, *, decimals: int = 0) -> str:
    """67% · −89% · 11.4% (decimals=1) · 'n/a' when undefined."""
    if value is None:
        return "n/a"
    rounded = round_half_up(value, decimals)
    sign = MINUS if rounded < 0 else ""
    return f"{sign}{abs(rounded):.{decimals}f}%"
