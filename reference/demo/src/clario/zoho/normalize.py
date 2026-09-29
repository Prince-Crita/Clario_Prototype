"""Convert Zoho Books JSON into Clario business models. Never pass raw JSON to Gemini."""

from __future__ import annotations

from datetime import date
from typing import Any

from clario.analytics.dates import days_between
from clario.zoho.models import (
    Customer,
    Expense,
    Invoice,
    Item,
    Organization,
    OverdueInvoice,
    Payment,
)


def organization_from_zoho(payload: dict[str, Any]) -> Organization:
    return Organization.model_validate(
        {
            "organization_id": payload.get("organization_id"),
            "name": payload.get("name") or "",
            "currency_code": payload.get("currency_code") or "",
            "currency_symbol": payload.get("currency_symbol") or "",
            "time_zone": payload.get("time_zone") or "",
            "is_org_active": payload.get("is_org_active", True),
            "is_default_org": payload.get("is_default_org", False),
        }
    )


def invoice_from_zoho(payload: dict[str, Any]) -> Invoice:
    return Invoice.model_validate(
        {
            "invoice_id": payload.get("invoice_id"),
            "invoice_number": payload.get("invoice_number") or "",
            "customer_id": payload.get("customer_id") or "",
            "customer": payload.get("customer_name") or payload.get("customer") or "",
            "invoice_date": payload.get("date") or payload.get("invoice_date"),
            "due_date": payload.get("due_date"),
            "status": payload.get("status") or "",
            "total": payload.get("total"),
            "balance": payload.get("balance"),
            "currency": payload.get("currency_code") or payload.get("currency") or "",
        }
    )


def overdue_from_invoice(invoice: Invoice, today: date) -> OverdueInvoice:
    days = 0
    if invoice.due_date:
        days = max(days_between(invoice.due_date, today), 0)
    return OverdueInvoice(**invoice.model_dump(), days_overdue=days)


def customer_from_zoho(payload: dict[str, Any]) -> Customer:
    return Customer.model_validate(
        {
            "customer_id": payload.get("contact_id") or payload.get("customer_id"),
            "name": payload.get("contact_name") or payload.get("customer_name") or payload.get("name") or "",
            "company_name": payload.get("company_name") or "",
            "email": payload.get("email") or "",
            "status": payload.get("status") or payload.get("contact_status") or "",
            "outstanding": payload.get("outstanding_receivable_amount")
            or payload.get("outstanding")
            or 0,
            "unused_credits": payload.get("unused_credits_receivable_amount") or 0,
            "currency": payload.get("currency_code") or "",
            "contact_type": payload.get("contact_type") or "customer",
        }
    )


def payment_from_zoho(payload: dict[str, Any]) -> Payment:
    return Payment.model_validate(
        {
            "payment_id": payload.get("payment_id"),
            "customer_id": payload.get("customer_id") or payload.get("contact_id") or "",
            "customer": payload.get("customer_name") or payload.get("contact_name") or "",
            "payment_date": payload.get("date") or payload.get("payment_date"),
            "amount": payload.get("amount"),
            "unused_amount": payload.get("unused_amount"),
            "payment_mode": payload.get("payment_mode") or "",
            "invoice_numbers": payload.get("invoice_numbers") or "",
            "currency": payload.get("currency_code") or "",
        }
    )


def expense_from_zoho(payload: dict[str, Any]) -> Expense:
    account = payload.get("account_name") or payload.get("category_name") or ""
    return Expense.model_validate(
        {
            "expense_id": payload.get("expense_id"),
            "expense_date": payload.get("date"),
            "account_name": account,
            "category": account,
            "vendor": payload.get("vendor_name") or payload.get("paid_through_account_name") or "",
            "total": payload.get("total") or payload.get("amount"),
            "currency": payload.get("currency_code") or "",
            "description": payload.get("description") or "",
            "status": payload.get("status") or "",
        }
    )


def item_from_zoho(payload: dict[str, Any]) -> Item:
    return Item.model_validate(
        {
            "item_id": payload.get("item_id"),
            "name": payload.get("name") or "",
            "sku": payload.get("sku") or "",
            "rate": payload.get("rate"),
            "status": payload.get("status") or "",
            "description": payload.get("description") or "",
        }
    )
