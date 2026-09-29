from __future__ import annotations

from datetime import date
from decimal import Decimal

from freezegun import freeze_time

from clario.analytics.dates import DateRange, equivalent_previous_period
from clario.analytics.rules import (
    average_invoice_value,
    days_overdue,
    expense_summary,
    outstanding_receivables,
    overdue_invoices,
    percent_change,
    receivable_summary,
    sales_summary,
    top_customers,
)


def test_percent_change_and_zero_previous():
    assert percent_change(Decimal("840000"), Decimal("735000")) == Decimal("14.3")
    assert percent_change(Decimal("0"), Decimal("0")) == Decimal("0")
    assert percent_change(Decimal("100"), Decimal("0")) is None


def test_average_invoice_value():
    assert average_invoice_value(Decimal("1000"), 4) == Decimal("250.00")
    assert average_invoice_value(Decimal("1000"), 0) == Decimal("0")


def test_revenue_comparison_excludes_drafts(sample_invoices):
    current = DateRange(date(2026, 9, 1), date(2026, 9, 22))
    previous = DateRange(date(2026, 8, 1), date(2026, 8, 31))
    current_sales = sales_summary(sample_invoices, current, "INR")
    previous_sales = sales_summary(sample_invoices, previous, "INR")
    assert current_sales.total_sales == Decimal("1400.00")
    assert current_sales.invoice_count == 2
    assert previous_sales.total_sales == Decimal("700.00")
    assert current_sales.average_invoice_value == Decimal("700.00")


@freeze_time("2026-09-22")
def test_receivables_and_days_overdue(sample_invoices):
    summary = receivable_summary(sample_invoices, date(2026, 9, 22))
    assert summary.outstanding == Decimal("600.00")
    overdue = overdue_invoices(sample_invoices, date(2026, 9, 22))
    numbers = [inv.invoice_number for inv in overdue]
    assert numbers[0] == "INV-003"
    assert "INV-002" in numbers
    assert overdue[0].days_overdue == 33
    assert days_overdue(date(2026, 9, 12), date(2026, 9, 22)) == 10


def test_expense_comparison(sample_expenses):
    current = DateRange(date(2026, 9, 1), date(2026, 9, 22))
    previous = equivalent_previous_period(current)
    current_exp = expense_summary(sample_expenses, current, "INR")
    previous_exp = expense_summary(sample_expenses, previous, "INR")
    assert current_exp.total_expenses == Decimal("200.00")
    assert current_exp.by_category[0].category == "Travel"
    assert previous_exp.total_expenses == Decimal("50.00")


def test_customer_concentration(sample_invoices):
    current = DateRange(date(2026, 9, 1), date(2026, 9, 22))
    ranked = top_customers(sample_invoices, current, limit=5)
    assert ranked[0].customer == "Acme"
    assert ranked[0].share_percent == Decimal("71.4")
    assert outstanding_receivables(sample_invoices) == Decimal("600.00")
