"""Zoho → canonical mapping, against the sanitised Phase 0 TEST responses (tests/fixtures)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from clario.domains.finance.periods import ledger_months, sync_window
from clario.domains.finance.schemas import AccountCategory, InvoiceStatus, PnlSection, TaxRole
from clario.integrations.zoho_books import mapping
from clario.integrations.zoho_books.mapping import ZohoMappingError

FIXTURES = Path(__file__).parents[1] / "fixtures" / "zoho_books"


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (FIXTURES / f"{name}.json").read_text(encoding="utf-8"), parse_float=Decimal
    )
    return data


def test_invoice_status_comes_from_amounts_not_zoho_labels() -> None:
    invoices = {
        i.invoice_number: i for i in map(mapping.to_invoice, fixture("invoices")["invoices"])
    }
    assert {n: (i.source_status, i.status) for n, i in invoices.items()} == {
        "INV-000007": ("void", InvoiceStatus.VOID),
        "INV-000006": ("draft", InvoiceStatus.DRAFT),
        "INV-000005": ("sent", InvoiceStatus.OPEN),
        "INV-000004": ("overdue", InvoiceStatus.OPEN),
        "INV-000003": ("overdue", InvoiceStatus.PARTIALLY_PAID),  # Zoho hides the part payment
        "INV-000002": ("paid", InvoiceStatus.PAID),
        "INV-000001": ("paid", InvoiceStatus.PAID),
    }
    receivable = [
        i for i in invoices.values() if i.status not in (InvoiceStatus.DRAFT, InvoiceStatus.VOID)
    ]
    assert sum(i.balance_base for i in receivable) == Decimal("43000")  # = balance-sheet AR
    assert all(isinstance(i.total_base, Decimal) for i in invoices.values())


def test_foreign_currency_invoice_uses_the_exchange_rate() -> None:
    usd = mapping.to_invoice(
        {
            "invoice_id": "1",
            "invoice_number": "INV-9",
            "date": "2026-09-01",
            "status": "sent",
            "currency_code": "USD",
            "exchange_rate": Decimal("83.25"),
            "total": Decimal("100.10"),
            "balance": Decimal("100.10"),
        }
    )
    assert (usd.total_base, usd.balance_base, usd.due_date) == (
        Decimal("8333.3250"),
        Decimal("8333.3250"),
        None,
    )


def test_floats_are_rejected() -> None:
    with pytest.raises(ZohoMappingError):
        mapping.to_payment_received(
            {"payment_id": "1", "date": "2026-09-01", "amount": 10.5, "bcy_amount": 10.5}
        )


def test_accounts_are_classified() -> None:
    accounts = [mapping.to_account(r) for r in fixture("chartofaccounts")["chartofaccounts"]]
    assert len(accounts) == 67
    by_name = {a.name: a for a in accounts}
    assert by_name["Petty Cash"].category is AccountCategory.CASH
    assert by_name["Sales"].category is AccountCategory.INCOME
    assert (
        mapping.to_account({"account_id": "9", "account_type": "output_tax"}).tax_role
        is TaxRole.OUTPUT_TAX
    )
    assert (
        mapping.to_account({"account_id": "9", "account_type": "mystery"}).category
        is AccountCategory.OTHER
    )


def test_monthly_pnl_gives_each_account_its_own_amount_per_section() -> None:
    lines = mapping.ledger_month(fixture("pnl_2026_09"), date(2026, 9, 1))
    assert {(line.section, line.account_name, line.amount) for line in lines} == {
        (PnlSection.OPERATING_INCOME, "Sales", Decimal("8000")),
        (PnlSection.COST_OF_GOODS_SOLD, "Cost of Goods Sold", Decimal("9000")),
        (PnlSection.OPERATING_EXPENSE, "IT and Internet Expenses", Decimal("2500")),
    }


def test_sub_accounts_are_not_double_counted() -> None:
    report = {
        "page_context": {"report_basis": "Accrual"},
        "profit_and_loss": [
            {
                "name": "Operating Profit",
                "account_transactions": [
                    {
                        "name": "Operating Expense",
                        "total": Decimal("300"),
                        "account_transactions": [
                            {
                                "name": "Office",
                                "account_id": "1",
                                "total": Decimal("300"),
                                "account_transactions": [
                                    {
                                        "name": "Stationery",
                                        "account_id": "2",
                                        "total": Decimal("120"),
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    lines = mapping.ledger_month(report, date(2026, 9, 1))
    assert {(line.account_name, line.amount) for line in lines} == {
        ("Office", Decimal("180")),
        ("Stationery", Decimal("120")),
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda r: r["profit_and_loss"][0]["account_transactions"][0].update(total=Decimal(1)),
            "add up",
        ),
        (
            lambda r: r["profit_and_loss"][0]["account_transactions"][0].update(name="Mystery"),
            "Unknown",
        ),
        (lambda r: r["page_context"].update(report_basis="Cash"), "accrual"),
    ],
)
def test_reports_that_do_not_reconcile_fail_loudly(change: Any, message: str) -> None:
    report = fixture("pnl_2026_09")
    change(report)
    with pytest.raises(ZohoMappingError, match=message):
        mapping.ledger_month(report, date(2026, 9, 1))


def test_balance_sheet_lines() -> None:
    lines = mapping.balance_lines(fixture("balancesheet"), date(2026, 9, 26))
    got = {(b.group, b.account_name, b.balance, b.account_source_id is None) for b in lines}
    assert got == {
        ("Cash", "Petty Cash", Decimal("-2500"), False),
        ("Bank", "TEST Bank Current", Decimal("8000"), False),
        ("Accounts Receivable", "Accounts Receivable", Decimal("43000"), False),
        ("Equities", "Current Year Earnings", Decimal("38500"), True),
        ("Equities", "Retained Earnings", Decimal("10000"), False),
    }
    cash_and_bank = sum(b.balance for b in lines if b.group in ("Cash", "Bank"))
    assert cash_and_bank == Decimal("5500")  # = the bank-accounts API (Phase 0 cross-check)


def test_balance_group_that_does_not_add_up_fails() -> None:
    report = fixture("balancesheet")
    report["balance_sheet"][0]["account_transactions"][0]["total"] = Decimal(1)
    with pytest.raises(ZohoMappingError, match="does not add up"):
        mapping.balance_lines(report, date(2026, 9, 26))


def test_sync_windows_cover_current_and_previous_fiscal_year() -> None:
    window = sync_window(date(2026, 9, 26), 4)
    assert (window.start, window.end) == (date(2025, 4, 1), date(2026, 9, 26))
    months = ledger_months(date(2026, 9, 26), 4)
    assert (months[0], months[-1], len(months)) == (date(2025, 4, 1), date(2026, 9, 1), 18)
    assert sync_window(date(2027, 2, 10), 4).start == date(2025, 4, 1)
    assert sync_window(date(2026, 9, 26), 1).start == date(2025, 1, 1)
