from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from clario.services.analysis import AnalysisService
from clario.tools import zoho_tools
from clario.zoho.models import CustomerBalance, Invoice, Organization, ReceivableSummary


@pytest.fixture
def org() -> Organization:
    return Organization(organization_id="org-1", name="Demo Co", currency_code="INR")


@pytest.mark.asyncio
async def test_get_sales_summary_tool_uses_normalized_invoices(sample_invoices, org, monkeypatch):
    client = SimpleNamespace(
        list_invoices=AsyncMock(return_value=sample_invoices),
        get_current_organization=AsyncMock(return_value=org),
    )
    service = AnalysisService(client=client)  # type: ignore[arg-type]
    monkeypatch.setattr(zoho_tools, "analysis_service", lambda: service)
    result = await zoho_tools.get_sales_summary("2026-09-01", "2026-09-22")
    assert result["status"] == "ok"
    assert result["summary"]["total_sales"] == "1400.00"
    assert result["summary"]["invoice_count"] == 2
    assert result["summary"]["average_invoice_value"] == "700.00"
    assert result["summary"]["currency"] == "INR"


@pytest.mark.asyncio
async def test_get_customer_balances_tool(org, monkeypatch):
    invoices = [
        Invoice(
            invoice_id="2",
            invoice_number="INV-002",
            customer_id="c2",
            customer="Globex",
            invoice_date=date(2026, 9, 5),
            due_date=date(2026, 9, 12),
            status="overdue",
            total=Decimal("400"),
            balance=Decimal("400"),
            currency="INR",
        )
    ]
    client = SimpleNamespace(
        list_invoices=AsyncMock(return_value=invoices),
        get_current_organization=AsyncMock(return_value=org),
    )
    service = AnalysisService(client=client)  # type: ignore[arg-type]
    monkeypatch.setattr(zoho_tools, "analysis_service", lambda: service)
    result = await zoho_tools.get_customer_balances()
    assert result["status"] == "ok"
    assert result["by_customer"][0]["customer"] == "Globex"
    assert result["outstanding"] == "400.00"


@pytest.mark.asyncio
async def test_get_overdue_and_expenses_and_top_customers(sample_invoices, sample_expenses, org, monkeypatch):
    client = SimpleNamespace(
        list_invoices=AsyncMock(return_value=sample_invoices),
        list_expenses=AsyncMock(return_value=sample_expenses),
        get_current_organization=AsyncMock(return_value=org),
    )
    service = AnalysisService(client=client)  # type: ignore[arg-type]
    monkeypatch.setattr(zoho_tools, "analysis_service", lambda: service)
    overdue = await zoho_tools.get_overdue_invoices()
    expenses = await zoho_tools.get_expense_summary("2026-09-01", "2026-09-22")
    top = await zoho_tools.get_top_customers("2026-09-01", "2026-09-22", 5)
    assert overdue["status"] == "ok"
    numbers = [inv["invoice_number"] for inv in overdue["invoices"]]
    assert "INV-002" in numbers
    assert "INV-003" in numbers
    assert expenses["total_expenses"] == "200.00"
    assert top["customers"][0]["customer"] == "Acme"


@pytest.mark.asyncio
async def test_invalid_date_returns_tool_error(monkeypatch):
    service = AnalysisService(client=SimpleNamespace())  # type: ignore[arg-type]
    monkeypatch.setattr(zoho_tools, "analysis_service", lambda: service)
    result = await zoho_tools.get_sales_summary("22-09-2026", "2026-09-22")
    assert result["status"] == "error"
    assert "Invalid start_date" in result["error"]


@pytest.mark.asyncio
async def test_empty_period_is_valid_zero_summary(org, monkeypatch):
    client = SimpleNamespace(
        list_invoices=AsyncMock(return_value=[]),
        get_current_organization=AsyncMock(return_value=org),
    )
    service = AnalysisService(client=client)  # type: ignore[arg-type]
    monkeypatch.setattr(zoho_tools, "analysis_service", lambda: service)
    result = await zoho_tools.get_sales_summary("2026-09-01", "2026-09-22")
    assert result["status"] == "ok"
    assert result["summary"]["invoice_count"] == 0
    assert result["summary"]["total_sales"] == "0.00"


@pytest.mark.asyncio
async def test_financial_report_and_business_summary_tools(sample_invoices, sample_expenses, org, monkeypatch):
    client = SimpleNamespace(
        list_invoices=AsyncMock(return_value=sample_invoices),
        list_expenses=AsyncMock(return_value=sample_expenses),
        get_current_organization=AsyncMock(return_value=org),
        get_report=AsyncMock(return_value={"code": 0, "total": 12, "sales": []}),
    )
    service = AnalysisService(client=client)  # type: ignore[arg-type]
    monkeypatch.setattr(zoho_tools, "analysis_service", lambda: service)
    report = await zoho_tools.get_financial_report("profitandloss", "2026-09-01", "2026-09-22")
    summary = await zoho_tools.get_business_summary("2026-09-01", "2026-09-22")
    assert report["status"] == "ok"
    assert report["report_name"] == "profitandloss"
    assert summary["status"] == "ok"
    assert summary["sales"]["total_sales"] == "1400.00"
    assert summary["sales_change"]["change_percent"] is not None


def test_all_documented_tools_are_exported():
    names = {fn.__name__ for fn in zoho_tools.ALL_TOOLS}
    assert names >= {
        "get_sales_summary",
        "get_invoices",
        "get_overdue_invoices",
        "get_customer_balances",
        "get_expense_summary",
        "get_top_customers",
        "get_top_items",
        "get_financial_report",
        "get_business_summary",
    }
