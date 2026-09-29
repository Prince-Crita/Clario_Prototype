# ruff: noqa: E501  (the golden tables read best one row per line)
"""The golden dataset (plan §22.3, §24.4): canonical records that reproduce every figure shown in
the director's Command Centre PDFs (`reference/director-pdfs/`, kept out of git), as of
**25 Sep 2026** in India, fiscal year April–March.

* Every figure the PDFs print is reproduced exactly: KPIs, the P&L statement, the monthly table
  (billed, collected, expenses, net cash), the invoice register and its totals, revenue by client,
  the nine overdue items with their days overdue, the GST position and the accrual-loss item.
* Details the PDFs do NOT print are synthetic but constrained to those figures: the split of
  expenses by category within each month, payment and expense dates, the monthly ledger split,
  and account balances behind the totals.
* Client names are anonymised (Client A-D); amounts, invoice numbers and dates are the PDFs'.

`tests/db/test_golden.py` is the finance module's acceptance test against this data.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from functools import cache

from clario.domains.finance.schemas import (
    Account,
    AccountCategory,
    BalanceAmount,
    Expense,
    Invoice,
    InvoiceStatus,
    LedgerAmount,
    Party,
    PartyType,
    PaymentReceived,
    PnlSection,
    TaxRole,
)
from clario.domains.finance.testing.fixture_source import FinanceRecords

AS_OF = date(2026, 9, 25)
D = Decimal

CLIENTS = {
    "A": "Client A Enviro Pvt Ltd",
    "B": "Client B Threads",
    "C": "Client C Coffee Pvt Ltd",
    "D": "Client D",
}

# (source id, name, category, tax role)
ACCOUNTS = [
    ("acc-sales", "Sales", AccountCategory.INCOME, None),
    ("acc-construction", "Construction expense", AccountCategory.COST_OF_GOODS_SOLD, None),
    ("acc-salaries", "Salaries and Employee Wages", AccountCategory.EXPENSE, None),
    ("acc-director", "Director Remuneration", AccountCategory.EXPENSE, None),
    ("acc-software", "Software subscription A/C", AccountCategory.EXPENSE, None),
    ("acc-professional", "Proffessional expense", AccountCategory.EXPENSE, None),  # sic
    ("acc-welfare", "Staff Welfare", AccountCategory.EXPENSE, None),
    ("acc-consultant", "Consultant Expense", AccountCategory.EXPENSE, None),
    ("acc-office", "Office Supplies", AccountCategory.EXPENSE, None),
    ("acc-bank", "Current Account", AccountCategory.BANK, None),
    ("acc-petty", "Petty Cash", AccountCategory.CASH, None),
    ("acc-ar", "Accounts Receivable", AccountCategory.ACCOUNTS_RECEIVABLE, None),
    ("acc-out-cgst", "Output CGST", AccountCategory.TAX_LIABILITY, TaxRole.OUTPUT_TAX),
    ("acc-out-sgst", "Output SGST", AccountCategory.TAX_LIABILITY, TaxRole.OUTPUT_TAX),
    ("acc-in-cgst", "Input CGST", AccountCategory.OTHER_CURRENT_ASSET, TaxRole.INPUT_TAX),
    ("acc-in-sgst", "Input SGST", AccountCategory.OTHER_CURRENT_ASSET, TaxRole.INPUT_TAX),
]
NAMES = {source_id: name for source_id, name, _, _ in ACCOUNTS}

# The invoice register (PDF page 3-4): number, client, date, billed, balance, due date if overdue.
INVOICES = [
    ("INV-00024", "A", date(2026, 9, 16), 8_700, 8_700, date(2026, 9, 16)),
    ("INV-00023", "A", date(2026, 9, 11), 2_064, 2_064, date(2026, 9, 11)),
    ("INV-00022", "C", date(2026, 9, 9), 2_064, 2_064, date(2026, 9, 9)),
    ("INV-00021", "A", date(2026, 9, 7), 1_770, 1_770, date(2026, 9, 14)),
    ("INV-00020", "A", date(2026, 9, 4), 139_712, 0, None),
    ("INV-00017", "B", date(2026, 8, 10), 41_300, 0, None),
    ("INV-00016", "A", date(2026, 8, 11), 17_700, 7_412, date(2026, 8, 18)),
    ("INV-00014", "A", date(2026, 8, 3), 134_520, 0, None),
    ("INV-00013", "A", date(2026, 7, 21), 2_065, 0, None),
    ("INV-00012", "C", date(2026, 7, 21), 2_065, 2_065, date(2026, 7, 28)),
    ("INV-00010", "A", date(2026, 7, 3), 134_520, 4_019, date(2026, 7, 10)),
    ("INV-00008", "A", date(2026, 6, 5), 134_520, 0, None),
    ("INV-00007", "B", date(2026, 5, 30), 118_000, 0, None),
    ("INV-00006", "A", date(2026, 5, 5), 120_675, 0, None),
    ("INV-000002", "D", date(2026, 3, 24), 13_000, 13_000, date(2026, 3, 24)),
    ("INV-000001", "C", date(2026, 3, 24), 23_000, 17_000, date(2026, 3, 24)),
]

# Collections (each settles the register above; monthly totals are the PDF's "Collected").
PAYMENTS = [
    (date(2026, 5, 12), "A", 120_675),  # INV-00006
    (date(2026, 6, 12), "A", 134_520),  # INV-00008
    (date(2026, 6, 20), "C", 6_000),  # INV-000001, part
    (date(2026, 7, 8), "B", 118_000),  # INV-00007
    (date(2026, 7, 15), "A", 130_501),  # INV-00010, part
    (date(2026, 8, 5), "A", 134_520),  # INV-00014
    (date(2026, 8, 12), "B", 41_300),  # INV-00017
    (date(2026, 8, 24), "A", 2_065),  # INV-00013
    (date(2026, 9, 8), "A", 139_712),  # INV-00020
    (date(2026, 9, 8), "A", 10_288),  # INV-00016, part
]

# Cash expense records; monthly totals are the PDF's "Expenses" (category split synthetic).
EXPENSES = [
    (date(2026, 3, 15), "acc-professional", 22_000),
    (date(2026, 3, 20), "acc-software", 4_900),
    (date(2026, 4, 10), "acc-software", 4_956),
    (date(2026, 4, 22), "acc-welfare", 4_700),
    (date(2026, 5, 10), "acc-software", 7_020),
    (date(2026, 5, 20), "acc-welfare", 10_000),
    (date(2026, 5, 31), "acc-salaries", 138_000),
    (date(2026, 6, 5), "acc-office", 8_000),
    (date(2026, 6, 10), "acc-software", 5_721),
    (date(2026, 6, 18), "acc-professional", 36_000),
    (date(2026, 6, 30), "acc-salaries", 152_000),
    (date(2026, 7, 10), "acc-software", 4_126),
    (date(2026, 7, 20), "acc-consultant", 5_000),
    (date(2026, 7, 31), "acc-salaries", 168_000),
    (date(2026, 7, 31), "acc-director", 50_000),
    (date(2026, 8, 10), "acc-salaries", 155_000),
    (date(2026, 8, 10), "acc-director", 50_000),
    (date(2026, 8, 11), "acc-software", 30_000),
    (date(2026, 8, 11), "acc-professional", 13_715),
    (date(2026, 8, 20), "acc-construction", 10_000),
    (date(2026, 9, 2), "acc-office", 18_000),
    (date(2026, 9, 10), "acc-salaries", 145_800),
    (date(2026, 9, 10), "acc-software", 35_749),
    (date(2026, 9, 10), "acc-construction", 22_000),
    (date(2026, 9, 10), "acc-director", 20_000),
]

# Accrual ledger by month; FY-to-date totals are the PDF's revenue, COGS and operating expenses.
S = PnlSection
LEDGER = {
    ("acc-sales", S.OPERATING_INCOME): {3: 30_508, 5: 202_267, 6: 114_000, 7: 117_500, 8: 164_000, 9: 130_773},
    ("acc-construction", S.COST_OF_GOODS_SOLD): {5: 80_000, 6: 60_000, 7: 70_000, 8: 60_000, 9: 66_078},
    ("acc-salaries", S.OPERATING_EXPENSE): {5: 138_000, 6: 152_000, 7: 168_000, 8: 155_000, 9: 145_800},
    ("acc-director", S.OPERATING_EXPENSE): {7: 50_000, 8: 50_000, 9: 20_000},
    ("acc-software", S.OPERATING_EXPENSE): {3: 4_900, 4: 12_000, 5: 12_000, 6: 12_000, 7: 12_000, 8: 12_000, 9: 12_000},
    ("acc-professional", S.OPERATING_EXPENSE): {3: 22_000, 6: 30_000, 8: 15_000},
    ("acc-welfare", S.OPERATING_EXPENSE): {5: 7_000, 8: 7_000, 9: 7_000},
    ("acc-consultant", S.OPERATING_EXPENSE): {7: 15_000},
    ("acc-office", S.OPERATING_EXPENSE): {6: 8_690},
}  # fmt: skip

# Balances on the as-of date: cash on hand 72,739; receivables 58,094; GST 1,31,137 − 1,25,472.
BALANCES = [
    ("acc-bank", "Bank", D(70_239)),
    ("acc-petty", "Cash", D(2_500)),
    ("acc-ar", "Accounts Receivable", D(58_094)),
    ("acc-out-cgst", "Current Liabilities", D("65568.50")),
    ("acc-out-sgst", "Current Liabilities", D("65568.50")),
    ("acc-in-cgst", "Other Current Assets", D(62_736)),
    ("acc-in-sgst", "Other Current Assets", D(62_736)),
]


def _invoice(
    number: str, client: str, day: date, billed: int, balance: int, due: date | None
) -> Invoice:
    total, owed = D(billed), D(balance)
    status = (
        InvoiceStatus.PAID
        if owed == 0
        else InvoiceStatus.OPEN
        if owed == total
        else InvoiceStatus.PARTIALLY_PAID
    )
    return Invoice(
        source_id=f"inv-{number}",
        invoice_number=number,
        party_source_id=f"party-{client}",
        party_name=CLIENTS[client],
        invoice_date=day,
        due_date=due or day + timedelta(days=7),
        source_status=status.value,
        status=status,
        currency="INR",
        exchange_rate=D(1),
        subtotal=None,
        tax_total=None,
        total=total,
        balance=owed,
        total_base=total,
        balance_base=owed,
        source_updated_at=None,
    )


@cache
def golden_dataset() -> FinanceRecords:
    return FinanceRecords(
        accounts=tuple(
            Account(sid, name, None, category.value, category, role, True, None)
            for sid, name, category, role in ACCOUNTS
        ),
        parties=tuple(
            Party(f"party-{key}", PartyType.CUSTOMER, name, name, None, "INR", None)
            for key, name in CLIENTS.items()
        ),
        invoices=tuple(_invoice(*row) for row in INVOICES),
        payments_received=tuple(
            PaymentReceived(
                f"pay-{i}",
                f"party-{client}",
                CLIENTS[client],
                day,
                D(amount),
                D(amount),
                "INR",
                "banktransfer",
                None,
                None,
            )
            for i, (day, client, amount) in enumerate(PAYMENTS, start=1)
        ),
        expenses=tuple(
            Expense(
                f"exp-{i}",
                day,
                NAMES[account],
                None,
                D(amount),
                D(0),
                D(amount),
                D(amount),
                "INR",
                "Current Account",
                None,
            )
            for i, (day, account, amount) in enumerate(EXPENSES, start=1)
        ),
        payments_made=(),
        ledger=tuple(
            LedgerAmount(account, NAMES[account], section, date(2026, month, 1), D(amount))
            for (account, section), months in LEDGER.items()
            for month, amount in months.items()
        ),
        balances=tuple(
            BalanceAmount(account, NAMES[account], group, AS_OF, balance)
            for account, group, balance in BALANCES
        ),
    )
