# ruff: noqa: E501  (model-facing descriptions and result shapes read best one per line)
"""Finance Assistant tools (plan §19.4). Each calls the same repository, metrics and sections as
the dashboard, so the assistant and the Command Centre can never disagree.

Every result carries `display` strings formatted in Python (Indian grouping, true minus), which
the model copies, plus `basis`, `period`, `as_of` and `sources` for the "Based on …" line.
Arguments never carry identity: the ConnectionScope comes from the server-built AgentContext.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from clario.ai.context import AgentContext
from clario.ai.tools.base import Tool, ToolArgs, ToolResult, error, no_data
from clario.core.dates import DateRange
from clario.core.money import format_inr, format_percent, percent_change
from clario.domains.finance import repository as repo
from clario.domains.finance.metrics import cash, pnl
from clario.domains.finance.metrics.receivables import days_overdue, display_status, is_overdue
from clario.domains.finance.periods import PeriodError, resolve_period, sync_window
from clario.domains.finance.sections import ledger, overview
from clario.domains.finance.sections.common import month_rows
from clario.domains.finance.sections.context import FinanceContext, load_context
from clario.platform.access.permissions import Permission
from clario.platform.sync import repository as sync_repo

ZERO = Decimal(0)
Preset = Literal[
    "this_month", "last_month", "this_quarter", "last_quarter", "fy_to_date", "last_fy",
    "last_n_days", "custom",
]  # fmt: skip


def inr(value: Decimal | str) -> str:
    return format_inr(Decimal(value))


def pct(value: Decimal | None, decimals: int = 0) -> str:
    return format_percent(value, decimals=decimals) if value is not None else "n/a"


def s(value: Decimal) -> str:
    """Exact decimal string for `data` (the model reads `display`; `data` keeps precision)."""
    return format(value.normalize(), "f") if value == value.to_integral() else str(value)


class PeriodArgs(ToolArgs):
    period: Preset = Field("fy_to_date", description="Which period; resolved by the server")
    days: int | None = Field(None, ge=1, le=400, description="Only for last_n_days")
    start_date: date | None = Field(None, description="Only for custom (YYYY-MM-DD)")
    end_date: date | None = Field(None, description="Only for custom (YYYY-MM-DD)")


async def _fin(ctx: AgentContext) -> FinanceContext:
    return await load_context(ctx.session, ctx.scope, ctx.clock)


def _period(fin: FinanceContext, args: PeriodArgs) -> tuple[DateRange, str]:
    return resolve_period(
        args.period,
        fin.today,
        fin.fiscal_year_start_month,
        days=args.days,
        start=args.start_date,
        end=args.end_date,
    )


def _meta(
    fin: FinanceContext,
    sources: tuple[str, ...],
    basis: str | None,
    period: tuple[DateRange, str] | None,
) -> dict[str, Any]:
    as_of = fin.meta.freshness.as_of
    return {
        "as_of": as_of.isoformat() if as_of else None,
        "currency": fin.meta.currency,
        "sources": sources,
        "basis": basis,
        "period": (
            {
                "start": period[0].start.isoformat(),
                "end": period[0].end.isoformat(),
                "label": period[1],
            }
            if period
            else None
        ),
    }


def _coverage(fin: FinanceContext, window: DateRange) -> ToolResult | None:
    """Ledger and cash documents are mirrored from the start of the previous fiscal year."""
    first = sync_window(fin.today, fin.fiscal_year_start_month).start
    if window.end < first:
        return no_data(
            "finance.before_synced_period",
            f"Clario holds figures from {first.day} {first:%b %Y} onwards; earlier periods aren't synced.",
        )
    return None


def _period_or_error(fin: FinanceContext, args: PeriodArgs) -> tuple[DateRange, str] | ToolResult:
    try:
        period = _period(fin, args)
    except PeriodError as exc:
        return error("finance.invalid_period", str(exc))
    return _coverage(fin, period[0]) or period


# ---------------------------------------------------------------- overview & P&L


class NoArgs(ToolArgs):
    pass


async def get_financial_overview(ctx: AgentContext, _: NoArgs) -> ToolResult:
    fin = await _fin(ctx)
    o = await overview.build(fin)
    data: dict[str, Any] = {}
    display: dict[str, str] = {}
    for kpi in o.kpis:
        data[kpi.key] = {"value": s(kpi.value), "basis": kpi.basis, "window": kpi.window.label}
        # The window sits beside the figure: cash collected covers every synced month, not the
        # fiscal year, and the evaluation showed the model mislabelling it when it was apart.
        display[kpi.key] = f"{inr(kpi.value)} ({kpi.basis}, {kpi.window.label})"
        if kpi.ratio is not None:
            data[kpi.key]["ratio_percent"] = s(kpi.ratio)
            display[f"{kpi.key}_ratio"] = pct(kpi.ratio)
        if kpi.related is not None:
            display[f"{kpi.key}_{kpi.related.name}"] = inr(kpi.related.amount)
        if kpi.count is not None:
            data[kpi.key]["count"] = kpi.count
        if kpi.change and kpi.change.percent is not None:
            display[f"{kpi.key}_change"] = (
                f"{pct(kpi.change.percent)} ({kpi.change.compared_to.lower()})"
            )
    display["gross_margin"] = pct(o.pnl.gross_margin)
    return ToolResult(
        status="ok",
        data=data,
        display=display,
        **_meta(fin, ("Overview",), None, None),
    )


class PnlArgs(PeriodArgs):
    by_month: bool = Field(False, description="Also return each month's figures")


def _pnl_display(summary: pnl.PnlSummary) -> dict[str, str]:
    return {
        "revenue": inr(summary.revenue),
        "cogs": inr(summary.cogs),
        "gross_profit": inr(summary.gross_profit),
        "gross_margin": pct(summary.gross_margin),
        "operating_expenses": inr(summary.operating_expenses),
        "total_costs": inr(summary.total_costs),
        "net_pnl": inr(summary.net_pnl),
        "net_margin": pct(summary.net_margin),
    }


async def get_profit_and_loss(ctx: AgentContext, args: PnlArgs) -> ToolResult:
    fin = await _fin(ctx)
    period = _period_or_error(fin, args)
    if isinstance(period, ToolResult):
        return period
    window, _ = period
    summary = pnl.summarise(await repo.section_totals(fin.session, fin.scope, window))
    display = _pnl_display(summary)
    data: dict[str, Any] = {
        k: s(getattr(summary, k))
        for k in ("revenue", "cogs", "operating_expenses", "gross_profit", "net_pnl")
    }
    if args.by_month:
        months = await repo.section_totals_by_month(fin.session, fin.scope, window)
        data["months"] = [
            {
                "month": month.isoformat(),
                **{
                    k: v
                    for k, v in _pnl_display(pnl.summarise(values)).items()
                    if k in ("revenue", "total_costs", "net_pnl")
                },
            }
            for month, values in sorted(months.items())
        ]
    display["note"] = (
        "Net P&L = revenue − cost of goods sold − operating expenses (excludes non-operating items)."
    )
    return ToolResult(
        status="ok", data=data, display=display, **_meta(fin, ("Profit & loss",), "accrual", period)
    )


# ---------------------------------------------------------------- cash


class CashArgs(PeriodArgs):
    granularity: Literal["month", "week", "day"] = Field("month", description="Bucket size")


async def get_cash_movement(ctx: AgentContext, args: CashArgs) -> ToolResult:
    fin = await _fin(ctx)
    period = _period_or_error(fin, args)
    if isinstance(period, ToolResult):
        return period
    window, _ = period
    if args.granularity == "day" and window.days > 62:
        return error(
            "finance.too_many_days", "Daily figures are limited to 62 days; use week or month."
        )
    cash_in = await repo.collected_by_day(fin.session, fin.scope, window)
    cash_out = await repo.expenses_by_day(fin.session, fin.scope, window)
    if args.granularity == "month":
        rows = await month_rows(fin, window)
        buckets = [cash.CashBucket(r.month, r.collected, r.expenses) for r in rows]
    else:
        size = 7 if args.granularity == "week" else 1
        start = window.start - timedelta(days=window.start.weekday()) if size == 7 else window.start
        starts = []
        while start <= window.end:
            starts.append(start)
            start += timedelta(days=size)
        buckets = cash.buckets(starts, size, cash_in, cash_out)
    total_in = sum(cash_in.values(), ZERO)
    total_out = sum(cash_out.values(), ZERO)
    return ToolResult(
        status="ok",
        data={
            "buckets": [
                {"start": b.start.isoformat(), "in": inr(b.cash_in), "out": inr(b.cash_out), "net": inr(b.net)}
                for b in buckets
            ]
        },
        display={"collected": inr(total_in), "spent": inr(total_out), "net": inr(total_in - total_out),
                 "note": "Cash in = customer payments; cash out = expense records (vendor bill payments not included)."},
        **_meta(fin, ("Cash movement",), "cash", period),
    )  # fmt: skip


# ---------------------------------------------------------------- receivables & customers


class ReceivablesArgs(ToolArgs):
    filter: Literal["all", "overdue"] = Field(
        "all", description="All open invoices or only overdue ones"
    )
    party: str | None = Field(None, max_length=100, description="Client name (or part of it)")


async def get_receivables(ctx: AgentContext, args: ReceivablesArgs) -> ToolResult:
    fin = await _fin(ctx)
    items = await repo.receivable_invoices(fin.session, fin.scope)
    if args.party:
        needle = args.party.casefold()
        items = [i for i in items if needle in i.party_name.casefold()]
    if args.filter == "overdue":
        items = [i for i in items if is_overdue(i.status, i.balance, i.due_date, fin.today)]
    items.sort(key=lambda i: (-days_overdue(i.due_date, fin.today), i.invoice_number))
    overdue = [i for i in items if is_overdue(i.status, i.balance, i.due_date, fin.today)]
    by_client: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for item in items:
        by_client[item.party_name] += item.balance
    return ToolResult(
        status="ok",
        data={
            "invoices": [
                {
                    "number": i.invoice_number,
                    "client": i.party_name,
                    "balance": inr(i.balance),
                    "due": i.due_date.isoformat() if i.due_date else None,
                    "days_overdue": days_overdue(i.due_date, fin.today),
                }
                for i in items[:50]
            ],
            "by_client": [
                {"client": name, "outstanding": inr(amount)}
                for name, amount in sorted(by_client.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
        },
        display={
            "outstanding": inr(sum((i.balance for i in items), ZERO)),
            "overdue": inr(sum((i.balance for i in overdue), ZERO)),
            "open_count": str(len(items)),
            "overdue_count": str(len(overdue)),
        },
        **_meta(fin, ("Receivables",), "balance", None),
    )


class CustomerArgs(ToolArgs):
    party: str = Field(
        min_length=1, max_length=100, description="The client's name (or part of it)"
    )


async def get_customer_summary(ctx: AgentContext, args: CustomerArgs) -> ToolResult:
    fin = await _fin(ctx)
    names = await repo.party_names(fin.session, fin.scope)
    needle = args.party.casefold().strip()
    exact = [n for n in names if n.casefold() == needle]
    matches = exact or [n for n in names if needle in n.casefold()]
    if not matches:
        return no_data("finance.unknown_client", f"No client matching {args.party!r} was found.")
    if len(matches) > 1:
        return no_data(
            "finance.ambiguous_client",
            "Several clients match; ask which one.",
            data={"candidates": matches[:10]},
        )
    name = matches[0]
    billed = next(
        (
            p
            for p in await repo.billed_by_party(fin.session, fin.scope, fin.today)
            if p.party_name == name
        ),
        None,
    )
    collected, payments = await repo.payments_from(fin.session, fin.scope, name, 5)
    recent = await repo.invoice_page(
        fin.session,
        fin.scope,
        today=fin.today,
        status=None,
        party=name,
        after=None,
        limit=5,
        party_exact=True,
    )
    return ToolResult(
        status="ok",
        data={
            "client": name,
            "recent_invoices": [
                {"number": r.invoice_number, "date": r.invoice_date.isoformat(), "billed": inr(r.total_base),
                 "balance": inr(max(r.balance_base, ZERO)), "status": display_status(r.status, r.balance_base, r.due_date, fin.today)}
                for r in recent
            ],
            "recent_payments": [
                {"date": p.payment_date.isoformat(), "amount": inr(p.amount), "reference": p.reference}
                for p in payments
            ],
        },
        display={
            "client": name,
            "billed_lifetime": inr(billed.billed if billed else ZERO),
            "outstanding": inr(billed.outstanding if billed else ZERO),
            "overdue": inr(billed.overdue if billed else ZERO),
            "collected": inr(collected),
            "note": "Billed is all invoices ever (excluding drafts and voids); collected covers mirrored payments.",
        },
        **_meta(fin, ("Customer summary",), "billed", None),
    )  # fmt: skip


class FindInvoicesArgs(ToolArgs):
    status: (
        Literal["overdue", "unpaid", "paid", "partially_paid", "open", "draft", "void"] | None
    ) = None
    party: str | None = Field(None, max_length=100, description="Client name (or part of it)")
    number: str | None = Field(
        None, max_length=64, description="An exact invoice number, e.g. INV-00016"
    )
    period: Preset | None = Field(None, description="Only invoices dated in this period")
    days: int | None = Field(None, ge=1, le=400)
    start_date: date | None = None
    end_date: date | None = None


async def find_invoices(ctx: AgentContext, args: FindInvoicesArgs) -> ToolResult:
    fin = await _fin(ctx)
    window = None
    period = None
    if args.period:
        try:
            period = resolve_period(
                args.period,
                fin.today,
                fin.fiscal_year_start_month,
                days=args.days,
                start=args.start_date,
                end=args.end_date,
            )
        except PeriodError as exc:
            return error("finance.invalid_period", str(exc))
        window = period[0]
    rows = await repo.invoice_page(
        fin.session, fin.scope, today=fin.today, status=args.status, party=args.party, after=None,
        limit=50, number=args.number, window=window,
    )  # fmt: skip
    if not rows:
        return no_data(
            "finance.no_invoices",
            "No invoices match.",
            **_meta(fin, ("Invoices",), "billed", period),
        )
    return ToolResult(
        status="ok",
        data={
            "invoices": [
                {"number": r.invoice_number, "client": r.party_name, "date": r.invoice_date.isoformat(),
                 "due": r.due_date.isoformat() if r.due_date else None, "billed": inr(r.total_base),
                 "balance": inr(max(r.balance_base, ZERO)),
                 "status": display_status(r.status, r.balance_base, r.due_date, fin.today),
                 "days_overdue": days_overdue(r.due_date, fin.today) if r.balance_base > 0 else 0}
                for r in rows
            ],
            "truncated": len(rows) == 50,
        },
        display={"count": str(len(rows))},
        **_meta(fin, ("Invoices",), "billed", period),
    )  # fmt: skip


# ---------------------------------------------------------------- expenses, GST, actions


class ExpenseArgs(PeriodArgs):
    group: Literal["category", "month"] = Field(
        "category", description="Break down by category or by month"
    )


async def get_expense_breakdown(ctx: AgentContext, args: ExpenseArgs) -> ToolResult:
    fin = await _fin(ctx)
    period = _period_or_error(fin, args)
    if isinstance(period, ToolResult):
        return period
    rows = await repo.expenses_by_category_month(fin.session, fin.scope, period[0])
    groups: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for month, name, amount in rows:
        groups[name if args.group == "category" else month.strftime("%b %Y")] += amount
    ordered = (
        sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))
        if args.group == "category"
        else list(groups.items())
    )
    total = sum(groups.values(), ZERO)
    return ToolResult(
        status="ok" if rows else "no_data",
        code=None if rows else "finance.no_expenses",
        message=None if rows else "No expenses were recorded in this period.",
        data={"items": [{"name": n, "amount": inr(a), "share": pct(a / total * 100 if total else None)} for n, a in ordered[:15]]},
        display={"total": inr(total), "note": "Expense records by date paid (cash basis); vendor bill payments not included."},
        **_meta(fin, ("Expenses",), "cash", period),
    )  # fmt: skip


async def get_gst_position(ctx: AgentContext, _: NoArgs) -> ToolResult:
    fin = await _fin(ctx)
    g = await ledger.build_gst(fin)
    meta = _meta(fin, ("GST",), "ledger", None)
    if g.net_payable is None:
        return no_data(
            "finance.no_gst", "No GST accounts were found in the connected books.", **meta
        )
    return ToolResult(
        status="ok",
        data={"as_of": g.as_of.isoformat() if g.as_of else None},
        display={
            "output_gst": inr(g.output_tax or ZERO),
            "input_credit": inr(g.input_tax or ZERO),
            "net_payable": inr(g.net_payable),
            "note": "Ledger position as of the latest balance sheet; the GST period and method are still being agreed.",
        },
        **meta,
    )


async def get_action_items(ctx: AgentContext, _: NoArgs) -> ToolResult:
    fin = await _fin(ctx)
    o = await overview.build(fin)
    return ToolResult(
        status="ok",
        data={"items": [{"kind": a.kind, "severity": a.severity, "title": a.title, "detail": a.detail} for a in o.actions]},
        display={"count": str(len(o.actions))},
        **_meta(fin, ("Action items",), None, None),
    )  # fmt: skip


# ---------------------------------------------------------------- comparisons & freshness

Metric = Literal[
    "revenue", "cogs", "operating_expenses", "total_costs", "net_pnl",
    "billed", "collected", "cash_expenses", "net_cash",
]  # fmt: skip
ACCRUAL = {"revenue", "cogs", "operating_expenses", "total_costs", "net_pnl"}


class CompareArgs(ToolArgs):
    metric: Metric
    period_a: Preset = Field(description="The period to report")
    period_b: Preset = Field(description="The period to compare it with")
    days: int | None = Field(None, ge=1, le=400, description="For last_n_days")


async def _metric(fin: FinanceContext, metric: str, window: DateRange) -> Decimal:
    if metric in ACCRUAL:
        summary = pnl.summarise(await repo.section_totals(fin.session, fin.scope, window))
        return Decimal(getattr(summary, metric))
    rows = await month_rows(fin, window)
    t = cash.totals(rows)
    return {
        "billed": t.billed,
        "collected": t.collected,
        "cash_expenses": t.expenses,
        "net_cash": t.net_cash,
    }[metric]


async def compare_periods(ctx: AgentContext, args: CompareArgs) -> ToolResult:
    fin = await _fin(ctx)
    try:
        a = resolve_period(args.period_a, fin.today, fin.fiscal_year_start_month, days=args.days)
        b = resolve_period(args.period_b, fin.today, fin.fiscal_year_start_month, days=args.days)
    except PeriodError as exc:
        return error("finance.invalid_period", str(exc))
    for window, _ in (a, b):
        gap = _coverage(fin, window)
        if gap:
            return gap
    value_a, value_b = await _metric(fin, args.metric, a[0]), await _metric(fin, args.metric, b[0])
    change = percent_change(value_a, value_b)
    return ToolResult(
        status="ok",
        data={"metric": args.metric, "a": {"period": a[1], "value": s(value_a)}, "b": {"period": b[1], "value": s(value_b)}},
        display={
            "a": f"{inr(value_a)} ({a[1]})",
            "b": f"{inr(value_b)} ({b[1]})",
            "difference": inr(value_a - value_b),
            "change": pct(change, 1) if change is not None else "n/a (the earlier value is zero)",
        },
        **_meta(fin, ("Comparison",), "accrual" if args.metric in ACCRUAL else "cash", None),
    )  # fmt: skip


async def get_data_freshness(ctx: AgentContext, _: NoArgs) -> ToolResult:
    fin = await _fin(ctx)
    rows = await sync_repo.datasets(fin.session, fin.scope)
    return ToolResult(
        status="ok",
        data={
            "datasets": [
                {"dataset": key, "status": row.status, "rows": row.row_count,
                 "last_refreshed": row.last_success_at.isoformat() if row.last_success_at else None}
                for key, row in sorted(rows.items())
            ],
            "sync_state": fin.meta.freshness.sync_state,
        },
        display={"as_of": fin.meta.freshness.as_of.isoformat() if fin.meta.freshness.as_of else "not fully imported yet"},
        **_meta(fin, ("Data freshness",), None, None),
    )  # fmt: skip


V = Permission.FINANCE_VIEW
TOOLS: tuple[Tool, ...] = (
    Tool("get_financial_overview", "Headline figures: revenue, cash collected vs billed, total costs, net P&L and margin, cash on hand, receivables and overdue count, each with its basis and window.", NoArgs, V, get_financial_overview, "Overview"),
    Tool("get_profit_and_loss", "Accrual profit and loss for a period: revenue, cost of goods sold, gross profit and margin, operating expenses, net P&L and margin; optionally month by month.", PnlArgs, V, get_profit_and_loss, "Profit & loss"),
    Tool("get_cash_movement", "Cash collected from customers vs expenses paid, by month, week or day, for a period.", CashArgs, V, get_cash_movement, "Cash movement"),
    Tool("get_receivables", "What customers owe as of today: outstanding and overdue totals, open invoices with days overdue, and totals by client. Filter to overdue or one client.", ReceivablesArgs, V, get_receivables, "Receivables"),
    Tool("get_customer_summary", "One client: lifetime billed, collected, outstanding and overdue, plus recent invoices and payments.", CustomerArgs, V, get_customer_summary, "Customer summary"),
    Tool("find_invoices", "Find invoices by status, client, exact number or date period (up to 50, newest first).", FindInvoicesArgs, V, find_invoices, "Invoices"),
    Tool("get_expense_breakdown", "Expenses paid in a period, by category or by month.", ExpenseArgs, V, get_expense_breakdown, "Expenses"),
    Tool("get_gst_position", "GST collected on sales, input credit on purchases, and the net payable, from the ledger.", NoArgs, V, get_gst_position, "GST"),
    Tool("get_action_items", "What needs attention today: overdue invoices, GST payable, an accrual loss.", NoArgs, V, get_action_items, "Action items"),
    Tool("compare_periods", "Compare one metric between two periods, with the difference and percentage change.", CompareArgs, V, compare_periods, "Comparison"),
    Tool("get_data_freshness", "When the data was last refreshed from the accounting system, per dataset.", NoArgs, V, get_data_freshness, "Data freshness"),
)  # fmt: skip
