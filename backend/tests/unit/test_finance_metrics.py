"""Pure finance formulas (plan §24): margins, cash buckets, receivables, actions, GST."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from clario.core.money import round_half_up
from clario.domains.finance.metrics import actions, cash, gst, pnl
from clario.domains.finance.metrics.receivables import (
    OpenInvoice,
    ageing,
    days_overdue,
    display_status,
)
from clario.domains.finance.periods import fy_to_date, last_n_weeks, previous_month, this_month
from clario.domains.finance.schemas import PnlSection
from clario.domains.finance.sections.trends import expense_trend

D = Decimal
TODAY = date(2026, 9, 25)


def test_pnl_reproduces_the_pdf_statement() -> None:
    summary = pnl.summarise(
        {
            PnlSection.OPERATING_INCOME: D(728_540),
            PnlSection.COST_OF_GOODS_SOLD: D(336_078),
            PnlSection.OPERATING_EXPENSE: D(1_040_490),
            PnlSection.NON_OPERATING_INCOME: D(500),
        }
    )
    assert summary.total_costs == D(1_376_568)
    assert summary.net_pnl == D(-648_028)  # other income is reported, not included (Q4)
    assert summary.gross_margin is not None
    assert round_half_up(summary.gross_margin, 0) == D(54)
    assert summary.net_margin is not None
    assert round_half_up(summary.net_margin, 0) == D(-89)


def test_margins_are_undefined_without_revenue() -> None:
    summary = pnl.summarise({PnlSection.OPERATING_EXPENSE: D(100)})
    assert (summary.gross_margin, summary.net_margin, summary.net_pnl) == (None, None, D(-100))


def test_month_rows_start_at_the_first_active_month() -> None:
    months = [date(2026, m, 1) for m in (1, 2, 3, 4)]
    rows = cash.month_rows(months, {date(2026, 3, 1): D(36_000)}, {}, {date(2026, 4, 1): D(9_656)})
    assert [(r.month.month, r.net_cash) for r in rows] == [(3, D(0)), (4, D(-9_656))]
    assert cash.totals(rows).billed == D(36_000)
    assert round_half_up(cash.collection_ratio(D(837_581), D(895_675)) or D(0), 0) == D(94)
    assert cash.collection_ratio(D(1), D(0)) is None


def test_buckets_sum_consecutive_days() -> None:
    weeks = last_n_weeks(TODAY, 10)
    assert (weeks[0], weeks[-1]) == (date(2026, 7, 20), date(2026, 9, 21))  # Mondays
    buckets = cash.buckets(
        [date(2026, 9, 7)], 7, {date(2026, 9, 8): D(150_000)}, {date(2026, 9, 13): D(1)}
    )
    assert (buckets[0].cash_in, buckets[0].cash_out, buckets[0].net) == (
        D(150_000),
        D(1),
        D(149_999),
    )


def test_periods() -> None:
    assert fy_to_date(TODAY, 4).start == date(2026, 4, 1)
    assert (this_month(TODAY).start, previous_month(TODAY).start, previous_month(TODAY).end) == (
        date(2026, 9, 1),
        date(2026, 8, 1),
        date(2026, 8, 31),
    )


def invoice(number: str, due: date | None, balance: int, status: str = "open") -> OpenInvoice:
    return OpenInvoice(number, "Client", date(2026, 1, 1), due, D(100_000), D(balance), status)


def test_overdue_is_derived_from_the_due_date() -> None:
    assert days_overdue(date(2026, 3, 24), TODAY) == 185
    assert days_overdue(TODAY, TODAY) == 0
    assert days_overdue(None, TODAY) == 0
    assert display_status("open", D(10), date(2026, 9, 1), TODAY) == "overdue"
    assert display_status("partially_paid", D(10), date(2026, 10, 1), TODAY) == "partially_paid"
    assert display_status("open", D(0), date(2026, 9, 1), TODAY) == "paid"
    assert display_status("void", D(10), date(2026, 9, 1), TODAY) == "void"  # never receivable


def test_ageing_buckets() -> None:
    items = [
        invoice("a", date(2026, 10, 1), 1),  # not due
        invoice("b", date(2026, 9, 24), 2),  # 1 day
        invoice("c", date(2026, 8, 26), 4),  # 30 days
        invoice("d", date(2026, 8, 25), 8),  # 31 days
        invoice("e", date(2026, 6, 27), 16),  # 90 days
        invoice("f", date(2026, 6, 26), 32),  # 91 days
        invoice("g", date(2026, 1, 1), 64, status="draft"),  # not receivable
    ]
    assert [(b.key, b.amount, b.count) for b in ageing(items, TODAY)] == [
        ("not_due", D(1), 1),
        ("1_30", D(6), 2),
        ("31_60", D(8), 1),
        ("61_90", D(16), 1),
        ("over_90", D(32), 1),
    ]


@pytest.mark.parametrize(
    ("days", "severity"),
    [
        (90, actions.Severity.HIGH),
        (89, actions.Severity.MEDIUM),
        (30, actions.Severity.MEDIUM),
        (29, actions.Severity.LOW),
    ],
)
def test_overdue_severity_thresholds(days: int, severity: actions.Severity) -> None:
    assert actions.overdue_severity(days) is severity


def test_action_items_are_ordered_and_worded_observationally() -> None:
    items = actions.overdue_invoices(
        [
            invoice("INV-1", date(2026, 3, 24), 17_000),
            invoice("INV-2", date(2026, 3, 24), 13_000),
            invoice("INV-3", date(2026, 9, 16), 8_700),
            invoice("INV-4", date(2026, 10, 1), 5),  # not yet due
        ],
        TODAY,
    )
    assert [(i.reference, i.days_overdue) for i in items] == [
        ("INV-2", 185),
        ("INV-1", 185),
        ("INV-3", 9),
    ]
    assert items[0].title == "INV-2 · Client: ₹13,000 overdue 185 days"
    assert items[0].detail == "Due 24 Mar 2026."
    position = gst.GstPosition(D(131_137), D(125_472))
    [gst_item] = actions.gst_payable(position, TODAY)
    assert gst_item.title == "GST payable ₹5,665"
    assert "₹1,31,137" in gst_item.detail
    assert "₹1,25,472" in gst_item.detail
    assert actions.gst_payable(gst.GstPosition(D(1), D(2)), TODAY) == []
    summary = pnl.summarise(
        {PnlSection.OPERATING_INCOME: D(728_540), PnlSection.OPERATING_EXPENSE: D(1_376_568)}
    )
    [loss] = actions.accrual_loss(summary, ("Salaries and Employee Wages", D(758_800)))
    assert loss.title == "Accrual loss of ₹6,48,028 this fiscal year"
    assert "Salaries and Employee Wages, ₹7,58,800" in loss.detail


def test_gst_position_needs_tax_accounts() -> None:
    assert gst.position([("output_tax", D(10)), (None, D(99)), ("input_tax", D(4))]) == (
        gst.GstPosition(D(10), D(4))
    )
    assert gst.position([(None, D(1))]) is None


def test_expense_trend_keeps_the_top_five_and_totals_the_rest() -> None:
    months = [date(2026, 8, 1), date(2026, 9, 1)]
    rows = [
        (months[0], "A", D(60)),
        (months[1], "A", D(50)),
        (months[0], "B", D(90)),
        (months[1], "C", D(80)),
        (months[1], "D", D(70)),
        (months[1], "E", D(60)),
        (months[1], "F", D(5)),
    ]
    top, trend = expense_trend(rows, months)
    assert top == ["A", "B", "C", "D", "E"]
    assert trend[1].amounts["A"] == D(50)
    assert trend[1].other == D(5)
    assert sum(trend[1].amounts.values()) + trend[1].other == D(265)
