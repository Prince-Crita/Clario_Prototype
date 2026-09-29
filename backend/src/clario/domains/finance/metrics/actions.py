"""Action items (plan §24.3): what needs attention today. Deterministic, observational wording.

Rules and thresholds live here and are tested; the dashboard and the assistant's
`get_action_items` return the same list.
  * Overdue invoice — each receivable past its due date, most overdue first;
    high at 90+ days, medium at 30+, otherwise low.
  * GST payable — net GST payable > 0 (medium).
  * Accrual loss — net P&L for the fiscal year to date < 0 (high).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from clario.core.money import format_inr
from clario.domains.finance.metrics.gst import GstPosition
from clario.domains.finance.metrics.pnl import PnlSummary
from clario.domains.finance.metrics.receivables import OpenInvoice, days_overdue, is_overdue

HIGH_AFTER_DAYS = 90
MEDIUM_AFTER_DAYS = 30


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionKind(StrEnum):
    OVERDUE_INVOICE = "overdue_invoice"
    GST_PAYABLE = "gst_payable"
    ACCRUAL_LOSS = "accrual_loss"


@dataclass(frozen=True, slots=True)
class ActionItem:
    kind: ActionKind
    severity: Severity
    title: str
    detail: str
    amount: Decimal
    reference: str | None = None  # e.g. the invoice number
    days_overdue: int | None = None
    due_date: date | None = None


def _day_text(days: int) -> str:
    return f"{days} day" if days == 1 else f"{days} days"


def _date_text(day: date) -> str:
    return f"{day.day} {day:%b %Y}"


def overdue_severity(days: int) -> Severity:
    if days >= HIGH_AFTER_DAYS:
        return Severity.HIGH
    if days >= MEDIUM_AFTER_DAYS:
        return Severity.MEDIUM
    return Severity.LOW


def overdue_invoices(invoices: Iterable[OpenInvoice], today: date) -> list[ActionItem]:
    overdue = [i for i in invoices if is_overdue(i.status, i.balance, i.due_date, today)]
    overdue.sort(key=lambda i: (days_overdue(i.due_date, today), i.invoice_number), reverse=True)
    items = []
    for invoice in overdue:
        days = days_overdue(invoice.due_date, today)
        assert invoice.due_date is not None  # overdue implies a due date
        items.append(
            ActionItem(
                kind=ActionKind.OVERDUE_INVOICE,
                severity=overdue_severity(days),
                title=(
                    f"{invoice.invoice_number} · {invoice.party_name}: "
                    f"{format_inr(invoice.balance)} overdue {_day_text(days)}"
                ),
                detail=f"Due {_date_text(invoice.due_date)}.",
                amount=invoice.balance,
                reference=invoice.invoice_number,
                days_overdue=days,
                due_date=invoice.due_date,
            )
        )
    return items


def gst_payable(position: GstPosition | None, as_of: date) -> list[ActionItem]:
    if position is None or position.net_payable <= 0:
        return []
    return [
        ActionItem(
            kind=ActionKind.GST_PAYABLE,
            severity=Severity.MEDIUM,
            title=f"GST payable {format_inr(position.net_payable)}",
            detail=(
                f"Output GST {format_inr(position.output_tax)} − input credit "
                f"{format_inr(position.input_tax)}, as of {_date_text(as_of)}."
            ),
            amount=position.net_payable,
        )
    ]


def accrual_loss(pnl: PnlSummary, largest_cost: tuple[str, Decimal] | None) -> list[ActionItem]:
    if pnl.net_pnl >= 0:
        return []
    detail = f"Revenue {format_inr(pnl.revenue)} against total costs {format_inr(pnl.total_costs)}."
    if largest_cost is not None:
        detail += f" Largest cost: {largest_cost[0]}, {format_inr(largest_cost[1])}."
    return [
        ActionItem(
            kind=ActionKind.ACCRUAL_LOSS,
            severity=Severity.HIGH,
            title=f"Accrual loss of {format_inr(-pnl.net_pnl)} this fiscal year",
            detail=detail,
            amount=pnl.net_pnl,
        )
    ]
