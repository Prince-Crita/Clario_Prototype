"""GST position (plan §22.2, §24.2) from the ledger: output tax collected − input tax credit.

Computed from balance-sheet balances of accounts the source marks as output/input tax, as of the
latest snapshot. The period (FY, month, since last filing) and the source (ledger or documents)
are pending director question 5, and the account types need a GST-enabled organisation to verify
(plan risk R2).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from clario.domains.finance.schemas import TaxRole

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class GstPosition:
    output_tax: Decimal
    input_tax: Decimal

    @property
    def net_payable(self) -> Decimal:
        return self.output_tax - self.input_tax


def position(balances: Iterable[tuple[str | None, Decimal]]) -> GstPosition | None:
    """`(tax_role, balance)` pairs → the position, or None when no tax accounts exist."""
    output = inputs = ZERO
    found = False
    for role, balance in balances:
        if role == TaxRole.OUTPUT_TAX.value:
            output += balance
            found = True
        elif role == TaxRole.INPUT_TAX.value:
            inputs += balance
            found = True
    return GstPosition(output, inputs) if found else None
