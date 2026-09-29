"""GST and Balance Sheet tabs (plan §22.2). Both are **pending the director's definitions**
(questions 5 and 6); they show the ledger-based figures the PDF implies and say so."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from clario.domains.finance import repository as repo
from clario.domains.finance.metrics import gst
from clario.domains.finance.schemas import AccountCategory
from clario.domains.finance.sections.context import FinanceContext
from clario.domains.finance.sections.dto import BalanceGroup, BalanceLineOut, BalanceSheet, GstOut

ZERO = Decimal(0)
CASH_CATEGORIES = frozenset({AccountCategory.CASH.value, AccountCategory.BANK.value})


async def build_gst(ctx: FinanceContext) -> GstOut:
    as_of, balances = await repo.latest_balances(ctx.session, ctx.scope)
    position = gst.position((b.tax_role, b.balance) for b in balances)
    return GstOut(
        meta=ctx.meta,
        as_of=as_of,
        output_tax=position.output_tax if position else None,
        input_tax=position.input_tax if position else None,
        net_payable=position.net_payable if position else None,
    )


async def build_balance_sheet(ctx: FinanceContext) -> BalanceSheet:
    as_of, balances = await repo.latest_balances(ctx.session, ctx.scope)
    grouped: dict[str, list[BalanceLineOut]] = defaultdict(list)
    for line in balances:
        grouped[line.group].append(BalanceLineOut(name=line.account_name, balance=line.balance))
    return BalanceSheet(
        meta=ctx.meta,
        as_of=as_of,
        cash_on_hand=sum((b.balance for b in balances if b.category in CASH_CATEGORIES), ZERO),
        groups=[
            BalanceGroup(name=name, total=sum((x.balance for x in lines), ZERO), lines=lines)
            for name, lines in grouped.items()
        ],
    )
