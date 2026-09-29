"""Application services that compose Zoho client + analytics.

ADK tools call this layer. They do not talk to the Zoho REST API directly.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

from clario.analytics.dates import (
    DateRange,
    equivalent_previous_period,
    month_to_date,
    parse_iso_date,
    previous_month,
    today,
    validate_range,
)
from clario.analytics.rules import (
    business_summary as build_business_summary,
    expense_summary as build_expense_summary,
    overdue_invoices as build_overdue,
    receivable_summary as build_receivables,
    sales_summary as build_sales_summary,
    top_customers as build_top_customers,
    top_items_from_report_rows,
)
from clario.config import get_settings
from clario.zoho.client import ZohoBooksClient, get_client
from clario.zoho.errors import ZohoError, ZohoValidationError
from clario.zoho.models import FinancialReport, Payment


class DateRangeArgs(BaseModel):
    start_date: str | None = Field(default=None, description="Inclusive start date YYYY-MM-DD")
    end_date: str | None = Field(default=None, description="Inclusive end date YYYY-MM-DD")

    @field_validator("start_date", "end_date")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value


def resolve_range(start_date: str | None, end_date: str | None, max_days: int | None = None) -> DateRange:
    settings = get_settings()
    limit = max_days or settings.date_range_max_days
    start = parse_iso_date(start_date, "start_date")
    end = parse_iso_date(end_date, "end_date")
    if start is None and end is None:
        return month_to_date()
    if start is None or end is None:
        raise ValueError("Provide both start_date and end_date, or omit both to use month-to-date.")
    return validate_range(start, end, max_days=limit)


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


class AnalysisService:
    def __init__(self, client: ZohoBooksClient | None = None) -> None:
        self.client = client or get_client()

    async def organization_snapshot(self) -> dict[str, Any]:
        org = await self.client.get_current_organization()
        return dump(org)

    async def get_sales_summary(self, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        rng = resolve_range(start_date, end_date)
        invoices = await self.client.list_invoices(start_date=rng.start, end_date=rng.end)
        org = await self.client.get_current_organization()
        summary = build_sales_summary(invoices, rng, org.currency_code)
        return {
            "organization": org.name,
            "summary": dump(summary),
        }

    async def get_invoices(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        status: str | None = None,
        customer_id: str | None = None,
    ) -> dict[str, Any]:
        rng = resolve_range(start_date, end_date) if (start_date or end_date) else None
        invoices = await self.client.list_invoices(
            start_date=rng.start if rng else None,
            end_date=rng.end if rng else None,
            status=status or None,
            customer_id=customer_id or None,
        )
        if rng and not status and not customer_id:
            invoices = [inv for inv in invoices if inv.invoice_date and rng.start <= inv.invoice_date <= rng.end]
        return {
            "count": len(invoices),
            "period": {"start": rng.start.isoformat(), "end": rng.end.isoformat()} if rng else None,
            "invoices": [dump(inv) for inv in invoices[:200]],
            "truncated": len(invoices) > 200,
        }

    async def get_overdue_invoices(self) -> dict[str, Any]:
        invoices = await self.client.list_invoices(status="overdue")
        if not invoices:
            invoices = await self.client.list_invoices(status="unpaid")
        overdue = build_overdue(invoices)
        org = await self.client.get_current_organization()
        return {
            "as_of": today().isoformat(),
            "currency": org.currency_code,
            "count": len(overdue),
            "invoices": [dump(inv) for inv in overdue[:100]],
        }

    async def get_customer_balances(self) -> dict[str, Any]:
        invoices = await self.client.list_invoices(status="unpaid")
        if not invoices:
            invoices = await self.client.list_invoices()
        summary = build_receivables(invoices)
        return dump(summary)

    async def get_expense_summary(self, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        rng = resolve_range(start_date, end_date)
        expenses = await self.client.list_expenses(start_date=rng.start, end_date=rng.end)
        org = await self.client.get_current_organization()
        return dump(build_expense_summary(expenses, rng, org.currency_code))

    async def get_top_customers(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        rng = resolve_range(start_date, end_date)
        invoices = await self.client.list_invoices(start_date=rng.start, end_date=rng.end)
        ranked = build_top_customers(invoices, rng, limit=max(1, min(limit, 25)))
        org = await self.client.get_current_organization()
        return {
            "start_date": rng.start.isoformat(),
            "end_date": rng.end.isoformat(),
            "currency": org.currency_code,
            "customers": [dump(item) for item in ranked],
        }

    async def get_top_items(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        rng = resolve_range(start_date, end_date)
        org = await self.client.get_current_organization()
        try:
            report = await self.client.get_report(
                "salesbyitem",
                start_date=rng.start,
                end_date=rng.end,
            )
            rows = _extract_report_rows(report)
            items = top_items_from_report_rows(rows, limit=max(1, min(limit, 25)), currency=org.currency_code)
            return {
                "start_date": rng.start.isoformat(),
                "end_date": rng.end.isoformat(),
                "currency": org.currency_code,
                "source": "zoho_report_salesbyitem",
                "items": [dump(item) for item in items],
            }
        except ZohoError as exc:
            return {
                "status": "insufficient_data",
                "start_date": rng.start.isoformat(),
                "end_date": rng.end.isoformat(),
                "error": (
                    "I don't have enough item-level sales data in Zoho Books to rank top items. "
                    f"Zoho reported: {exc}"
                ),
                "items": [],
            }

    async def get_financial_report(
        self,
        report_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if not report_name:
            raise ValueError("report_name is required.")
        rng = resolve_range(start_date, end_date)
        org = await self.client.get_current_organization()
        payload = await self.client.get_report(report_name, start_date=rng.start, end_date=rng.end)
        report = FinancialReport(
            report_name=report_name,
            start_date=rng.start,
            end_date=rng.end,
            currency=org.currency_code,
            totals=_extract_report_totals(payload),
            rows=_extract_report_rows(payload)[:100],
            source="zoho_report",
        )
        return dump(report)

    async def get_business_summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        current = resolve_range(start_date, end_date)
        previous = equivalent_previous_period(current) if start_date or end_date else previous_month()
        org = await self.client.get_current_organization()
        current_invoices = await self.client.list_invoices(
            start_date=min(previous.start, current.start),
            end_date=current.end,
        )
        current_expenses = await self.client.list_expenses(
            start_date=min(previous.start, current.start),
            end_date=current.end,
        )
        unpaid = await self.client.list_invoices(status="unpaid")
        sales = build_sales_summary(current_invoices, current, org.currency_code)
        prev_sales = build_sales_summary(current_invoices, previous, org.currency_code)
        expenses = build_expense_summary(current_expenses, current, org.currency_code)
        prev_expenses = build_expense_summary(current_expenses, previous, org.currency_code)
        receivables = build_receivables(unpaid or current_invoices)
        top = build_top_customers(current_invoices, current, limit=5)
        summary = build_business_summary(
            organization=org,
            current_sales=sales,
            previous_sales=prev_sales,
            current_expenses=expenses,
            previous_expenses=prev_expenses,
            receivables=receivables,
            top=top,
            current_range=current,
            previous_range=previous,
        )
        return dump(summary)

    async def get_customer_payments(
        self,
        customer_id: str | None = None,
        customer_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        rng = resolve_range(start_date, end_date) if (start_date or end_date) else None
        payments: list[Payment] = await self.client.list_payments(
            start_date=rng.start if rng else None,
            end_date=rng.end if rng else None,
            customer_id=customer_id or None,
        )
        if customer_name and not customer_id:
            needle = customer_name.lower()
            payments = [p for p in payments if needle in (p.customer or "").lower()]
        return {
            "count": len(payments),
            "payments": [dump(item) for item in payments[:100]],
        }


def _extract_report_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in (
        "sales",
        "salesbyitem",
        "sales_by_item",
        "salesbycustomer",
        "inventorysummary",
        "line_items",
        "rows",
        "data",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _extract_report_totals(payload: dict[str, Any]) -> dict[str, Any]:
    totals = {}
    for key in ("total", "totals", "net_profit", "income", "expense", "gross_profit"):
        if key in payload:
            totals[key] = payload[key]
    return totals
