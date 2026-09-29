"""Google ADK tools. Each tool validates input and returns normalized JSON.

These functions are the only Zoho capabilities the Clario agent may call.
They never expose OAuth tokens and never write to Zoho.
"""

from __future__ import annotations

from typing import Any

from clario.logging import get_logger
from clario.services.analysis import AnalysisService
from clario.zoho.errors import ZohoError

logger = get_logger("clario.tools")

_service: AnalysisService | None = None


def set_analysis_service(service: AnalysisService | None) -> None:
    global _service
    _service = service


def analysis_service() -> AnalysisService:
    return _service or AnalysisService()


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("status") == "insufficient_data":
        return data
    return {"status": "ok", **data}


def _fail(exc: Exception) -> dict[str, Any]:
    logger.warning("Tool failed: %s", exc)
    if isinstance(exc, ValueError):
        return {"status": "error", "error": str(exc), "data": None}
    if isinstance(exc, ZohoError):
        return {"status": "error", "error": str(exc), "data": None}
    return {
        "status": "error",
        "error": "I don't have enough data in Zoho Books to answer that reliably.",
        "data": None,
    }


async def get_sales_summary(start_date: str = "", end_date: str = "") -> dict[str, Any]:
    """Get total sales, invoice count, and average invoice value for a date range.

    Use this for questions about revenue, sales this month, or invoice volume.
    Omit dates to use the current month through today.

    Args:
        start_date: Inclusive start date in YYYY-MM-DD format. Empty for month-to-date.
        end_date: Inclusive end date in YYYY-MM-DD format. Empty for today.
    """
    try:
        return _ok(await analysis_service().get_sales_summary(start_date or None, end_date or None))
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_invoices(
    start_date: str = "",
    end_date: str = "",
    status: str = "",
    customer_id: str = "",
) -> dict[str, Any]:
    """List invoices filtered by date range, status, and/or customer.

    Status values include sent, draft, overdue, paid, void, unpaid, partially_paid.

    Args:
        start_date: Inclusive invoice date start YYYY-MM-DD, or empty.
        end_date: Inclusive invoice date end YYYY-MM-DD, or empty.
        status: Optional Zoho invoice status filter.
        customer_id: Optional Zoho customer/contact ID.
    """
    try:
        return _ok(
            await analysis_service().get_invoices(
                start_date or None,
                end_date or None,
                status or None,
                customer_id or None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_overdue_invoices() -> dict[str, Any]:
    """List overdue invoices with invoice number, customer, due date, days overdue, total and balance.

    Use for questions about overdue invoices, late payments, or aging receivables.
    """
    try:
        return _ok(await analysis_service().get_overdue_invoices())
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_customer_balances() -> dict[str, Any]:
    """Summarize outstanding receivables by customer, ranked highest first.

    Use for questions about who owes the most, outstanding balances, or receivables.
    """
    try:
        return _ok(await analysis_service().get_customer_balances())
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_expense_summary(start_date: str = "", end_date: str = "") -> dict[str, Any]:
    """Summarize expenses by category for a date range.

    Use for biggest expenses, expense trends, or spending by category.
    Omit dates to use the current month through today.

    Args:
        start_date: Inclusive start date YYYY-MM-DD, or empty.
        end_date: Inclusive end date YYYY-MM-DD, or empty.
    """
    try:
        return _ok(await analysis_service().get_expense_summary(start_date or None, end_date or None))
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_top_customers(start_date: str = "", end_date: str = "", limit: int = 10) -> dict[str, Any]:
    """Rank customers by sales for a date range, including each customer's share of total sales.

    Args:
        start_date: Inclusive start date YYYY-MM-DD, or empty for month-to-date.
        end_date: Inclusive end date YYYY-MM-DD, or empty.
        limit: Maximum customers to return (1-25).
    """
    try:
        return _ok(await analysis_service().get_top_customers(start_date or None, end_date or None, limit))
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_top_items(start_date: str = "", end_date: str = "", limit: int = 10) -> dict[str, Any]:
    """Rank items by sales amount using the Zoho Books sales-by-item report when available.

    Args:
        start_date: Inclusive start date YYYY-MM-DD, or empty.
        end_date: Inclusive end date YYYY-MM-DD, or empty.
        limit: Maximum items to return (1-25).
    """
    try:
        return _ok(await analysis_service().get_top_items(start_date or None, end_date or None, limit))
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_financial_report(
    report_name: str,
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    """Retrieve a supported Zoho Books financial report.

    Supported report_name values: profitandloss, balancesheet, cashflow,
    salesbycustomer, salesbyitem, inventorysummary, aging, customerbalances.

    Args:
        report_name: Report identifier.
        start_date: Inclusive start date YYYY-MM-DD, or empty.
        end_date: Inclusive end date YYYY-MM-DD, or empty.
    """
    try:
        return _ok(
            await analysis_service().get_financial_report(
                report_name,
                start_date or None,
                end_date or None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_business_summary(start_date: str = "", end_date: str = "") -> dict[str, Any]:
    """Combined business snapshot: sales vs previous period, expenses, receivables, top customers, and signals.

    Use for business health, what changed, what to watch, or a general monthly summary.

    Args:
        start_date: Inclusive start date YYYY-MM-DD, or empty for month-to-date.
        end_date: Inclusive end date YYYY-MM-DD, or empty.
    """
    try:
        return _ok(await analysis_service().get_business_summary(start_date or None, end_date or None))
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


async def get_customer_payments(
    customer_id: str = "",
    customer_name: str = "",
    start_date: str = "",
    end_date: str = "",
) -> dict[str, Any]:
    """List customer payments / payments received, optionally filtered by customer.

    Use for payment history follow-ups such as 'what about their payment history?'.

    Args:
        customer_id: Zoho customer ID when known from a previous tool result.
        customer_name: Customer name substring when ID is unknown.
        start_date: Inclusive payment date start YYYY-MM-DD, or empty.
        end_date: Inclusive payment date end YYYY-MM-DD, or empty.
    """
    try:
        return _ok(
            await analysis_service().get_customer_payments(
                customer_id or None,
                customer_name or None,
                start_date or None,
                end_date or None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)


ALL_TOOLS = [
    get_sales_summary,
    get_invoices,
    get_overdue_invoices,
    get_customer_balances,
    get_expense_summary,
    get_top_customers,
    get_top_items,
    get_financial_report,
    get_business_summary,
    get_customer_payments,
]
