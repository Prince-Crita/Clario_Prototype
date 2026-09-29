"""Overview tab (plan §22.2): the KPI band, the P&L statement, billed vs collected vs spent, action
items, revenue by client, where the money goes, and the invoice register totals.

Definitions reproduce the director's PDF (§22.3, §24.2) and each figure carries its basis:
  * Revenue, costs, net P&L, margins — accrual, fiscal year to date (the source's P&L).
  * Cash collected and billed — the trend window (current + previous FY; director Q1).
  * Total costs' month-on-month change — cash expenses this month vs last month (director Q2).
  * Cash on hand and receivables — balances as of today.
"""

from __future__ import annotations

from decimal import Decimal

from clario.core.money import percent_change, ratio_percent
from clario.domains.finance import repository as repo
from clario.domains.finance.metrics import actions, cash, gst, pnl
from clario.domains.finance.metrics.receivables import is_overdue
from clario.domains.finance.periods import fy_to_date, previous_month, this_month, trend_window
from clario.domains.finance.schemas import AccountCategory, PnlSection
from clario.domains.finance.sections.common import action_out, client_out, month_out, month_rows
from clario.domains.finance.sections.context import FinanceContext, window
from clario.domains.finance.sections.dto import (
    Change,
    ExpenseShare,
    Kpi,
    NamedAmount,
    Overview,
    PnlStatement,
    RegisterTotalsOut,
)

ZERO = Decimal(0)
CASH_CATEGORIES = frozenset({AccountCategory.CASH.value, AccountCategory.BANK.value})


async def pnl_summary(ctx: FinanceContext) -> tuple[pnl.PnlSummary, NamedAmount | None]:
    fytd = fy_to_date(ctx.today, ctx.fiscal_year_start_month)
    summary = pnl.summarise(await repo.section_totals(ctx.session, ctx.scope, fytd))
    costs = await repo.ledger_by_account(
        ctx.session, ctx.scope, fytd, [PnlSection.COST_OF_GOODS_SOLD, PnlSection.OPERATING_EXPENSE]
    )
    largest = NamedAmount(name=costs[0][0], amount=costs[0][1]) if costs else None
    return summary, largest


async def build(ctx: FinanceContext) -> Overview:
    today, fy_month = ctx.today, ctx.fiscal_year_start_month
    fytd = fy_to_date(today, fy_month)
    fy_window = window(fytd.start, fytd.end, f"{ctx.meta.fiscal_year} to date")
    trend = trend_window(today, fy_month)
    summary, largest = await pnl_summary(ctx)

    rows = await month_rows(ctx, trend)
    total = cash.totals(rows)
    trend_label = window(rows[0].month if rows else trend.start, today)
    this, last = this_month(today), previous_month(today)
    spent_now = sum((await repo.expenses_by_day(ctx.session, ctx.scope, this)).values(), ZERO)
    spent_before = sum((await repo.expenses_by_day(ctx.session, ctx.scope, last)).values(), ZERO)

    as_of, balances = await repo.latest_balances(ctx.session, ctx.scope)
    cash_on_hand = sum((b.balance for b in balances if b.category in CASH_CATEGORIES), ZERO)
    receivable = await repo.receivable_invoices(ctx.session, ctx.scope)
    overdue = [i for i in receivable if is_overdue(i.status, i.balance, i.due_date, today)]
    position = gst.position((b.tax_role, b.balance) for b in balances)
    today_window = window(today, today, f"As of {today.day} {today:%b %Y}")

    kpis = [
        Kpi(
            key="revenue",
            label="Revenue",
            value=summary.revenue,
            basis="accrual",
            window=fy_window,
            note="Income from the ledger, excluding GST",
        ),
        Kpi(
            key="cash_collected",
            label="Cash collected",
            value=total.collected,
            basis="cash",
            window=trend_label,
            related=NamedAmount(name="billed", amount=total.billed),
            ratio=cash.collection_ratio(total.collected, total.billed),
        ),
        Kpi(
            key="total_costs",
            label="Total costs",
            value=summary.total_costs,
            basis="accrual",
            window=fy_window,
            note="Cost of goods sold + operating expenses",
            change=Change(
                percent=percent_change(spent_now, spent_before),
                compared_to="Cash expenses, this month vs last month",
            ),
        ),
        Kpi(
            key="net_pnl",
            label="Net P&L",
            value=summary.net_pnl,
            basis="accrual",
            window=fy_window,
            note="Revenue − cost of goods sold − operating expenses",
            ratio=summary.net_margin,
        ),
        Kpi(
            key="cash_on_hand",
            label="Cash on hand",
            value=cash_on_hand,
            basis="balance",
            window=today_window,
            note="Bank + cash",
        ),
        Kpi(
            key="receivables",
            label="Receivables",
            value=sum((i.balance for i in receivable), ZERO),
            basis="balance",
            window=today_window,
            count=len(overdue),
            note="overdue",
        ),
    ]

    items = [
        *actions.overdue_invoices(receivable, today),
        *actions.gst_payable(position, as_of or today),
        *actions.accrual_loss(summary, (largest.name, largest.amount) if largest else None),
    ]
    mix = await repo.ledger_by_account(ctx.session, ctx.scope, fytd, [PnlSection.OPERATING_EXPENSE])
    mix_total = sum((amount for _, amount in mix), ZERO)
    register = await repo.register_totals(ctx.session, ctx.scope)

    return Overview(
        meta=ctx.meta,
        kpis=kpis,
        pnl=PnlStatement(
            window=fy_window,
            revenue=summary.revenue,
            cogs=summary.cogs,
            operating_expenses=summary.operating_expenses,
            total_costs=summary.total_costs,
            gross_profit=summary.gross_profit,
            gross_margin=summary.gross_margin,
            net_pnl=summary.net_pnl,
            net_margin=summary.net_margin,
            other_income=summary.other_income,
            other_expenses=summary.other_expenses,
            largest_cost=largest,
            latest_month_spend=spent_now,
        ),
        months=[month_out(r) for r in rows],
        actions=[action_out(i) for i in items],
        revenue_by_client=[
            client_out(r) for r in await repo.billed_by_party(ctx.session, ctx.scope, today)
        ],
        expense_mix=[
            ExpenseShare(name=name, amount=amount, share=ratio_percent(amount, mix_total))
            for name, amount in mix
        ],
        expense_mix_window=fy_window,
        register_totals=RegisterTotalsOut(
            count=register.count, billed=register.billed, balance=register.balance
        ),
    )
