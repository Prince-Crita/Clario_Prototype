"""Deterministic analytics from normalized Zoho data.

The LLM explains these results. It must not compute them.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from clario.analytics.dates import DateRange, days_between, in_range, today
from clario.zoho.models import (
    BusinessSignal,
    BusinessSummary,
    CustomerBalance,
    CustomerSales,
    Expense,
    ExpenseCategoryTotal,
    ExpenseSummary,
    Invoice,
    ItemSales,
    Organization,
    OverdueInvoice,
    PeriodComparison,
    ReceivableSummary,
    SalesSummary,
)
from clario.zoho.normalize import overdue_from_invoice

ZERO = Decimal("0")
HUNDRED = Decimal("100")
MONEY = Decimal("0.01")
PCT = Decimal("0.1")

REVENUE_CHANGE_THRESHOLD = Decimal("10")
EXPENSE_CHANGE_THRESHOLD = Decimal("10")
CONCENTRATION_THRESHOLD = Decimal("30")
OVERDUE_SHARE_THRESHOLD = Decimal("25")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def percent(value: Decimal) -> Decimal:
    return value.quantize(PCT, rounding=ROUND_HALF_UP)


def percent_change(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        if current == 0:
            return Decimal("0")
        return None
    return percent(((current - previous) / previous) * HUNDRED)


def average_invoice_value(total_sales: Decimal, invoice_count: int) -> Decimal:
    if invoice_count <= 0:
        return ZERO
    return money(total_sales / Decimal(invoice_count))


def customer_share(customer_sales: Decimal, total_sales: Decimal) -> Decimal | None:
    if total_sales == 0:
        return None
    return percent((customer_sales / total_sales) * HUNDRED)


def outstanding_receivables(invoices: Iterable[Invoice]) -> Decimal:
    open_invoices = [
        inv
        for inv in invoices
        if inv.balance > 0 and (inv.status or "").lower() not in {"draft", "void", "paid"}
    ]
    return money(sum((inv.balance for inv in open_invoices), ZERO))


def days_overdue(due: date | None, as_of: date | None = None) -> int:
    if due is None:
        return 0
    as_of = as_of or today()
    return max(days_between(due, as_of), 0)


def sales_invoices(invoices: Iterable[Invoice]) -> list[Invoice]:
    excluded = {"draft", "void"}
    return [inv for inv in invoices if (inv.status or "").lower() not in excluded]


def sales_summary(
    invoices: Iterable[Invoice],
    rng: DateRange,
    currency: str = "",
) -> SalesSummary:
    in_period = [
        inv
        for inv in sales_invoices(invoices)
        if in_range(inv.invoice_date, rng)
    ]
    total = sum((inv.total for inv in in_period), ZERO)
    unpaid = sum((inv.balance for inv in in_period), ZERO)
    paid_count = sum(1 for inv in in_period if (inv.status or "").lower() == "paid")
    return SalesSummary(
        start_date=rng.start,
        end_date=rng.end,
        total_sales=money(total),
        invoice_count=len(in_period),
        average_invoice_value=average_invoice_value(total, len(in_period)),
        currency=currency or _currency(in_period),
        paid_count=paid_count,
        unpaid_balance=money(unpaid),
    )


def compare_metric(
    metric: str,
    current: Decimal,
    previous: Decimal,
    current_range: DateRange,
    previous_range: DateRange,
    currency: str = "",
) -> PeriodComparison:
    change = money(current - previous)
    pct = percent_change(current, previous)
    note = ""
    if previous == 0 and current != 0:
        note = "Previous period was zero, so a percentage change is not defined."
    return PeriodComparison(
        metric=metric,
        current_period=money(current),
        previous_period=money(previous),
        change_amount=change,
        change_percent=pct,
        current_start=current_range.start,
        current_end=current_range.end,
        previous_start=previous_range.start,
        previous_end=previous_range.end,
        currency=currency,
        note=note,
    )


def expense_summary(
    expenses: Iterable[Expense],
    rng: DateRange,
    currency: str = "",
) -> ExpenseSummary:
    in_period = [exp for exp in expenses if in_range(exp.expense_date, rng)]
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    counts: dict[str, int] = defaultdict(int)
    for exp in in_period:
        category = exp.category or exp.account_name or "Uncategorized"
        totals[category] += exp.total
        counts[category] += 1
    by_category = [
        ExpenseCategoryTotal(category=name, total=money(amount), count=counts[name])
        for name, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]
    total = sum((exp.total for exp in in_period), ZERO)
    return ExpenseSummary(
        start_date=rng.start,
        end_date=rng.end,
        total_expenses=money(total),
        expense_count=len(in_period),
        by_category=by_category,
        currency=currency or _currency(in_period, attr="currency"),
    )


def overdue_invoices(invoices: Iterable[Invoice], as_of: date | None = None) -> list[OverdueInvoice]:
    as_of = as_of or today()
    result: list[OverdueInvoice] = []
    for inv in invoices:
        status = (inv.status or "").lower()
        if status in {"draft", "void", "paid"}:
            continue
        if inv.balance <= 0:
            continue
        if status == "overdue" or (inv.due_date and inv.due_date < as_of):
            result.append(overdue_from_invoice(inv, as_of))
    result.sort(key=lambda item: (item.days_overdue, item.balance), reverse=True)
    return result


def receivable_summary(invoices: Iterable[Invoice], as_of: date | None = None) -> ReceivableSummary:
    as_of = as_of or today()
    open_invoices = [
        inv
        for inv in invoices
        if inv.balance > 0 and (inv.status or "").lower() not in {"draft", "void", "paid"}
    ]
    overdue = overdue_invoices(open_invoices, as_of)
    overdue_ids = {inv.invoice_id for inv in overdue}
    by_customer: dict[str, CustomerBalance] = {}
    for inv in open_invoices:
        key = inv.customer_id or inv.customer or "unknown"
        current = by_customer.get(key)
        overdue_amount = inv.balance if inv.invoice_id in overdue_ids else ZERO
        if current is None:
            by_customer[key] = CustomerBalance(
                customer_id=inv.customer_id,
                customer=inv.customer or "Unknown customer",
                outstanding=inv.balance,
                overdue=overdue_amount,
                invoice_count=1,
                currency=inv.currency,
            )
        else:
            current.outstanding += inv.balance
            current.overdue += overdue_amount
            current.invoice_count += 1
    ranked = sorted(by_customer.values(), key=lambda item: item.outstanding, reverse=True)
    for item in ranked:
        item.outstanding = money(item.outstanding)
        item.overdue = money(item.overdue)
    return ReceivableSummary(
        as_of=as_of,
        outstanding=outstanding_receivables(open_invoices),
        overdue=money(sum((inv.balance for inv in overdue), ZERO)),
        invoice_count=len(open_invoices),
        overdue_count=len(overdue),
        by_customer=ranked,
        currency=_currency(open_invoices),
    )


def top_customers(
    invoices: Iterable[Invoice],
    rng: DateRange,
    *,
    limit: int = 10,
) -> list[CustomerSales]:
    in_period = [inv for inv in sales_invoices(invoices) if in_range(inv.invoice_date, rng)]
    totals: dict[str, CustomerSales] = {}
    grand = ZERO
    for inv in in_period:
        key = inv.customer_id or inv.customer or "unknown"
        grand += inv.total
        current = totals.get(key)
        if current is None:
            totals[key] = CustomerSales(
                customer_id=inv.customer_id,
                customer=inv.customer or "Unknown customer",
                sales=inv.total,
                invoice_count=1,
                currency=inv.currency,
            )
        else:
            current.sales += inv.total
            current.invoice_count += 1
    ranked = sorted(totals.values(), key=lambda item: item.sales, reverse=True)
    for item in ranked:
        item.sales = money(item.sales)
        item.share_percent = customer_share(item.sales, grand)
    return ranked[:limit]


def top_items_from_report_rows(
    rows: list[dict],
    *,
    limit: int = 10,
    currency: str = "",
) -> list[ItemSales]:
    items: list[ItemSales] = []
    for row in rows:
        name = (
            row.get("item_name")
            or row.get("name")
            or row.get("item")
            or ""
        )
        if not name:
            continue
        sales = Decimal(str(row.get("amount") or row.get("sales") or row.get("total") or 0))
        quantity = Decimal(str(row.get("quantity") or row.get("qty") or 0))
        items.append(
            ItemSales(
                item_id=str(row.get("item_id") or ""),
                item=str(name),
                quantity=quantity,
                sales=money(sales),
                currency=currency,
            )
        )
    items.sort(key=lambda item: item.sales, reverse=True)
    return items[:limit]


def business_signals(
    *,
    sales_change: PeriodComparison | None,
    expense_change: PeriodComparison | None,
    receivables: ReceivableSummary,
    top: list[CustomerSales],
    expenses: ExpenseSummary,
) -> list[BusinessSignal]:
    signals: list[BusinessSignal] = []
    if sales_change and sales_change.change_percent is not None:
        pct = sales_change.change_percent
        if abs(pct) >= REVENUE_CHANGE_THRESHOLD:
            direction = "increased" if pct > 0 else "decreased"
            signals.append(
                BusinessSignal(
                    name="revenue_change",
                    severity="high" if abs(pct) >= 20 else "medium",
                    observation=(
                        f"The data shows revenue {direction} {pct}% compared with the previous period."
                    ),
                    evidence=sales_change.model_dump(mode="json"),
                )
            )
    if expense_change and expense_change.change_percent is not None:
        pct = expense_change.change_percent
        if pct >= EXPENSE_CHANGE_THRESHOLD:
            signals.append(
                BusinessSignal(
                    name="rising_expenses",
                    severity="medium",
                    observation=(
                        f"The data shows expenses increased {pct}% compared with the previous period."
                    ),
                    evidence=expense_change.model_dump(mode="json"),
                )
            )
    if receivables.outstanding > 0:
        overdue_share = percent((receivables.overdue / receivables.outstanding) * HUNDRED)
        if overdue_share >= OVERDUE_SHARE_THRESHOLD:
            signals.append(
                BusinessSignal(
                    name="high_overdue_receivables",
                    severity="high",
                    observation=(
                        f"The data shows {overdue_share}% of outstanding receivables are overdue."
                    ),
                    evidence={
                        "outstanding": str(receivables.outstanding),
                        "overdue": str(receivables.overdue),
                        "overdue_count": receivables.overdue_count,
                    },
                )
            )
        if receivables.by_customer:
            largest = receivables.by_customer[0]
            signals.append(
                BusinessSignal(
                    name="large_outstanding_balance",
                    severity="medium",
                    observation=(
                        f"{largest.customer} currently has the largest outstanding balance "
                        f"({largest.outstanding} {largest.currency})."
                    ),
                    evidence=largest.model_dump(mode="json"),
                )
            )
    if top:
        leader = top[0]
        if leader.share_percent is not None and leader.share_percent >= CONCENTRATION_THRESHOLD:
            signals.append(
                BusinessSignal(
                    name="customer_concentration",
                    severity="medium",
                    observation=(
                        f"The data shows {leader.customer} accounts for {leader.share_percent}% of sales "
                        "in the current period. This may be worth reviewing."
                    ),
                    evidence=leader.model_dump(mode="json"),
                )
            )
    if expenses.by_category:
        biggest = expenses.by_category[0]
        signals.append(
            BusinessSignal(
                name="largest_expense_category",
                severity="info",
                observation=(
                    f"The largest expense category in the period is {biggest.category} "
                    f"({biggest.total})."
                ),
                evidence=biggest.model_dump(mode="json"),
            )
        )
    return signals


def business_summary(
    *,
    organization: Organization,
    current_sales: SalesSummary,
    previous_sales: SalesSummary,
    current_expenses: ExpenseSummary,
    previous_expenses: ExpenseSummary,
    receivables: ReceivableSummary,
    top: list[CustomerSales],
    current_range: DateRange,
    previous_range: DateRange,
) -> BusinessSummary:
    sales_change = compare_metric(
        "revenue",
        current_sales.total_sales,
        previous_sales.total_sales,
        current_range,
        previous_range,
        current_sales.currency,
    )
    expense_change = compare_metric(
        "expenses",
        current_expenses.total_expenses,
        previous_expenses.total_expenses,
        current_range,
        previous_range,
        current_expenses.currency,
    )
    signals = business_signals(
        sales_change=sales_change,
        expense_change=expense_change,
        receivables=receivables,
        top=top,
        expenses=current_expenses,
    )
    return BusinessSummary(
        generated_at=datetime.now(timezone.utc),
        organization_name=organization.name,
        organization_id=organization.organization_id,
        currency=organization.currency_code or current_sales.currency,
        current_period_start=current_range.start,
        current_period_end=current_range.end,
        sales=current_sales,
        previous_sales=previous_sales,
        sales_change=sales_change,
        expenses=current_expenses,
        previous_expenses=previous_expenses,
        expense_change=expense_change,
        receivables=receivables,
        top_customers=top,
        signals=signals,
    )


def _currency(rows: list, attr: str = "currency") -> str:
    for row in rows:
        value = getattr(row, attr, "")
        if value:
            return value
    return ""
