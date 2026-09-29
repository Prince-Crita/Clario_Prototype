"""Profit and loss (plan §24.2), from the source's own P&L sections (accrual, ex-GST).

Net P&L = Revenue − COGS − Operating expenses, i.e. the source's *operating* profit. Non-operating
income and expenses are reported beside it but not included (pending director question 4).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from clario.core.money import ratio_percent
from clario.domains.finance.schemas import PnlSection

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class PnlSummary:
    revenue: Decimal
    cogs: Decimal
    operating_expenses: Decimal
    other_income: Decimal
    other_expenses: Decimal

    @property
    def gross_profit(self) -> Decimal:
        return self.revenue - self.cogs

    @property
    def total_costs(self) -> Decimal:
        return self.cogs + self.operating_expenses

    @property
    def net_pnl(self) -> Decimal:
        return self.revenue - self.cogs - self.operating_expenses

    @property
    def gross_margin(self) -> Decimal | None:
        """Gross profit ÷ revenue × 100; None when there is no revenue."""
        return ratio_percent(self.gross_profit, self.revenue)

    @property
    def net_margin(self) -> Decimal | None:
        return ratio_percent(self.net_pnl, self.revenue)


def summarise(sections: Mapping[PnlSection, Decimal]) -> PnlSummary:
    return PnlSummary(
        revenue=sections.get(PnlSection.OPERATING_INCOME, ZERO),
        cogs=sections.get(PnlSection.COST_OF_GOODS_SOLD, ZERO),
        operating_expenses=sections.get(PnlSection.OPERATING_EXPENSE, ZERO),
        other_income=sections.get(PnlSection.NON_OPERATING_INCOME, ZERO),
        other_expenses=sections.get(PnlSection.NON_OPERATING_EXPENSE, ZERO),
    )
