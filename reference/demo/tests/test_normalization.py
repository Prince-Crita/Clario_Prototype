from __future__ import annotations

from datetime import date
from decimal import Decimal

from clario.zoho.normalize import (
    customer_from_zoho,
    expense_from_zoho,
    invoice_from_zoho,
    organization_from_zoho,
    payment_from_zoho,
)


def test_invoice_normalization_coerces_ids_and_money():
    invoice = invoice_from_zoho(
        {
            "invoice_id": 982000000567114,
            "invoice_number": "INV-00003",
            "customer_name": "Bowman & Co",
            "customer_id": 982000000567001,
            "status": "overdue",
            "date": "2013-11-17",
            "due_date": "2013-12-03",
            "total": 10000,
            "balance": 40.6,
            "currency_code": "USD",
        }
    )
    assert invoice.invoice_id == "982000000567114"
    assert invoice.customer == "Bowman & Co"
    assert invoice.invoice_date == date(2013, 11, 17)
    assert invoice.total == Decimal("10000")
    assert invoice.balance == Decimal("40.6")
    assert invoice.currency == "USD"


def test_invoice_missing_fields_use_defaults():
    invoice = invoice_from_zoho({"invoice_id": "x"})
    assert invoice.invoice_number == ""
    assert invoice.total == Decimal("0")
    assert invoice.invoice_date is None


def test_organization_customer_payment_expense_normalization():
    org = organization_from_zoho(
        {
            "organization_id": "10234695",
            "name": "Zillum",
            "currency_code": "USD",
            "currency_symbol": "$",
            "time_zone": "PST",
            "is_org_active": True,
        }
    )
    assert org.name == "Zillum"
    customer = customer_from_zoho(
        {
            "contact_id": "c1",
            "contact_name": "Acme",
            "outstanding_receivable_amount": "12.50",
            "currency_code": "INR",
        }
    )
    assert customer.outstanding == Decimal("12.50")
    payment = payment_from_zoho(
        {"payment_id": "p1", "customer_name": "Acme", "amount": 5, "date": "2026-09-01"}
    )
    assert payment.amount == Decimal("5")
    expense = expense_from_zoho(
        {"expense_id": "e1", "account_name": "Travel", "total": 9, "date": "2026-09-01"}
    )
    assert expense.category == "Travel"
