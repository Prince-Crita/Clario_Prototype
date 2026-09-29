"""Receivables (plan §23.3, §24.2): what customers owe, as of today.

Receivable = an invoice with a balance that is not draft or void (Zoho keeps a balance on those).
Overdue is DERIVED: balance > 0 and due date before today (Zoho's own label is not trusted).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from clario.domains.finance.schemas import InvoiceStatus

ZERO = Decimal(0)
NOT_RECEIVABLE = frozenset({InvoiceStatus.DRAFT.value, InvoiceStatus.VOID.value})

DisplayStatus = Literal["draft", "void", "paid", "partially_paid", "open", "overdue", "unknown"]


@dataclass(frozen=True, slots=True)
class OpenInvoice:
    invoice_number: str
    party_name: str
    invoice_date: date
    due_date: date | None
    total: Decimal  # base currency
    balance: Decimal  # base currency
    status: str


def days_overdue(due_date: date | None, today: date) -> int:
    """Whole days past the due date (0 when not yet due or no due date)."""
    if due_date is None or due_date >= today:
        return 0
    return (today - due_date).days


def is_receivable(status: str, balance: Decimal) -> bool:
    return balance > ZERO and status not in NOT_RECEIVABLE


def is_overdue(status: str, balance: Decimal, due_date: date | None, today: date) -> bool:
    return is_receivable(status, balance) and days_overdue(due_date, today) > 0


def display_status(
    status: str, balance: Decimal, due_date: date | None, today: date
) -> DisplayStatus:
    if status in NOT_RECEIVABLE or status == InvoiceStatus.UNKNOWN.value:
        return status  # type: ignore[return-value]
    if balance <= ZERO:
        return "paid"
    if days_overdue(due_date, today) > 0:
        return "overdue"
    return "partially_paid" if status == InvoiceStatus.PARTIALLY_PAID.value else "open"


@dataclass(frozen=True, slots=True)
class AgeBucket:
    key: str
    label: str
    amount: Decimal
    count: int


# (key, label, lowest days overdue, highest or None)
AGEING = (
    ("not_due", "Not yet due", 0, 0),
    ("1_30", "1-30 days overdue", 1, 30),
    ("31_60", "31-60 days overdue", 31, 60),
    ("61_90", "61-90 days overdue", 61, 90),
    ("over_90", "Over 90 days overdue", 91, None),
)


def ageing(invoices: Iterable[OpenInvoice], today: date) -> list[AgeBucket]:
    open_items = [i for i in invoices if is_receivable(i.status, i.balance)]
    result = []
    for key, label, low, high in AGEING:
        inside = [
            i
            for i in open_items
            if low <= days_overdue(i.due_date, today)
            and (high is None or days_overdue(i.due_date, today) <= high)
        ]
        result.append(AgeBucket(key, label, sum((i.balance for i in inside), ZERO), len(inside)))
    return result
