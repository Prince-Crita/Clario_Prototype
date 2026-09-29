# ruff: noqa: E501  (the tables read best one row per line)
"""The evaluation dataset (plan §32): SYNTHETIC TEST figures for the Finance Assistant evaluation
and for trying the assistant locally (`FINANCE_FIXTURE_DATASET=evaluation`).

Unlike the golden dataset (the director's real amounts), nothing here is real, so it is safe to
send to the AI provider before its data terms are agreed (R6). Every party is prefixed "TEST".

As of **25 Sep 2026** in India, fiscal year April–March. The figures are round on purpose so the
expected answers can be worked out by hand (done below); `tests/db/test_evaluation_dataset.py`
proves the tools return exactly these, so an evaluation failure is the model, never the data.

FY 2026-27 to date (Apr–Sep)
  Revenue 11,40,000 · COGS 2,28,000 · gross profit 9,12,000 (80%) · operating expenses 10,09,500
  · net P&L −97,500 (−9%). Best month July (revenue 2,70,000, net 58,000).
  Q1 (Apr–Jun) revenue 5,35,000, net −83,000 · Q2 to date (Jul–Sep) revenue 6,05,000.
  Billed 13,45,200 · collected 9,70,100 (72%) · expenses paid 10,09,500 (salaries 7,20,000,
  rent 1,80,000) · collected Aug 97,200, Sep 1,00,000, Jul 2,95,000.
Today
  Cash on hand 2,50,000 · receivables 4,16,400 across 8 invoices · overdue 2,04,000 across 5
  (oldest INV-0998, 197 days; largest INV-1011, 53,400 due 4 Sep) · Bluefin owes the most
  (1,50,600) · Northwind owes 1,36,000, has paid 7,13,600 · Bluefin billed 3,48,100 lifetime ·
  GST output 72,000, input 41,400, payable 30,600.
FY 2025-26 (mirrored from Feb): revenue 85,000.
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
    "A": "TEST Northwind Retail",
    "B": "TEST Bluefin Logistics",
    "C": "TEST Kestrel Foods",
    "D": "TEST Kestrel Foods Exports",  # "Kestrel" alone is ambiguous on purpose
}

ACCOUNTS = [
    ("acc-sales", "Sales", AccountCategory.INCOME, None),
    ("acc-purchases", "Cost of Goods Sold", AccountCategory.COST_OF_GOODS_SOLD, None),
    ("acc-salaries", "Salaries and Employee Wages", AccountCategory.EXPENSE, None),
    ("acc-rent", "Rent Expense", AccountCategory.EXPENSE, None),
    ("acc-software", "Software Subscriptions", AccountCategory.EXPENSE, None),
    ("acc-professional", "Professional Fees", AccountCategory.EXPENSE, None),
    ("acc-travel", "Travel Expense", AccountCategory.EXPENSE, None),
    ("acc-bank", "Current Account", AccountCategory.BANK, None),
    ("acc-petty", "Petty Cash", AccountCategory.CASH, None),
    ("acc-ar", "Accounts Receivable", AccountCategory.ACCOUNTS_RECEIVABLE, None),
    ("acc-out-cgst", "Output CGST", AccountCategory.TAX_LIABILITY, TaxRole.OUTPUT_TAX),
    ("acc-out-sgst", "Output SGST", AccountCategory.TAX_LIABILITY, TaxRole.OUTPUT_TAX),
    ("acc-in-cgst", "Input CGST", AccountCategory.OTHER_CURRENT_ASSET, TaxRole.INPUT_TAX),
    ("acc-in-sgst", "Input SGST", AccountCategory.OTHER_CURRENT_ASSET, TaxRole.INPUT_TAX),
]
NAMES = {source_id: name for source_id, name, _, _ in ACCOUNTS}

# number, client, date, billed (incl. 18% GST), balance today; due 30 days after the invoice date.
INVOICES = [
    ("INV-0998", "C", date(2026, 2, 10), 41_300, 41_300),  # due 12 Mar: 197 days overdue
    ("INV-0999", "A", date(2026, 3, 5), 59_000, 0),
    ("INV-1001", "A", date(2026, 4, 6), 118_000, 0),
    ("INV-1002", "B", date(2026, 4, 18), 59_000, 0),
    ("INV-1003", "C", date(2026, 5, 4), 70_800, 0),
    ("INV-1004", "A", date(2026, 5, 20), 141_600, 0),
    ("INV-1005", "B", date(2026, 6, 2), 88_500, 0),
    ("INV-1006", "A", date(2026, 6, 15), 118_000, 0),
    ("INV-1007", "D", date(2026, 6, 25), 35_400, 35_400),  # due 25 Jul: 62 days
    ("INV-1008", "A", date(2026, 7, 1), 177_000, 0),
    ("INV-1009", "B", date(2026, 7, 14), 94_400, 44_400),  # due 13 Aug: 43 days, part paid
    ("INV-1010", "C", date(2026, 7, 28), 47_200, 0),
    ("INV-1011", "A", date(2026, 8, 5), 153_400, 53_400),  # due 4 Sep: 21 days, part paid
    ("INV-1012", "C", date(2026, 8, 19), 29_500, 29_500),  # due 18 Sep: 7 days
    ("INV-1013", "B", date(2026, 9, 3), 106_200, 106_200),  # due 3 Oct
    ("INV-1014", "A", date(2026, 9, 12), 82_600, 82_600),  # due 12 Oct
    ("INV-1015", "D", date(2026, 9, 22), 23_600, 23_600),  # due 22 Oct
]

PAYMENTS = [
    (date(2026, 3, 20), "A", 59_000),  # INV-0999
    (date(2026, 4, 28), "A", 118_000),  # INV-1001
    (date(2026, 5, 12), "B", 59_000),  # INV-1002
    (date(2026, 5, 30), "C", 70_800),  # INV-1003
    (date(2026, 6, 18), "A", 141_600),  # INV-1004
    (date(2026, 6, 30), "B", 88_500),  # INV-1005
    (date(2026, 7, 10), "A", 118_000),  # INV-1006
    (date(2026, 7, 29), "A", 177_000),  # INV-1008
    (date(2026, 8, 20), "B", 50_000),  # INV-1009, part
    (date(2026, 8, 26), "C", 47_200),  # INV-1010
    (date(2026, 9, 8), "A", 100_000),  # INV-1011, part
]

# Expenses paid (cash): salaries, rent and software every month; the rest occasionally.
MONTHS = range(4, 10)
EXPENSES = [
    (date(2026, 3, 3), "acc-rent", 30_000),
    (date(2026, 3, 5), "acc-salaries", 110_000),
    *((date(2026, m, 3), "acc-rent", 30_000) for m in MONTHS),
    *((date(2026, m, 5), "acc-salaries", 120_000) for m in MONTHS),
    *((date(2026, m, 10), "acc-software", 8_000) for m in MONTHS),
    (date(2026, 5, 14), "acc-travel", 12_000),
    (date(2026, 6, 18), "acc-professional", 25_000),
    (date(2026, 8, 21), "acc-travel", 9_500),
    (date(2026, 9, 15), "acc-professional", 15_000),
]

# Accrual ledger by month of 2026 (revenue excludes GST: billed / 1.18).
S = PnlSection
LEDGER = {
    ("acc-sales", S.OPERATING_INCOME): {2: 35_000, 3: 50_000, 4: 150_000, 5: 180_000, 6: 205_000, 7: 270_000, 8: 155_000, 9: 180_000},
    ("acc-purchases", S.COST_OF_GOODS_SOLD): {3: 10_000, 4: 30_000, 5: 36_000, 6: 41_000, 7: 54_000, 8: 31_000, 9: 36_000},
    ("acc-salaries", S.OPERATING_EXPENSE): {3: 110_000, **dict.fromkeys(MONTHS, 120_000)},
    ("acc-rent", S.OPERATING_EXPENSE): {3: 30_000, **dict.fromkeys(MONTHS, 30_000)},
    ("acc-software", S.OPERATING_EXPENSE): dict.fromkeys(MONTHS, 8_000),
    ("acc-professional", S.OPERATING_EXPENSE): {6: 25_000, 9: 15_000},
    ("acc-travel", S.OPERATING_EXPENSE): {5: 12_000, 8: 9_500},
}  # fmt: skip

BALANCES = [
    ("acc-bank", "Bank", D(245_300)),
    ("acc-petty", "Cash", D(4_700)),
    ("acc-ar", "Accounts Receivable", D(416_400)),
    ("acc-out-cgst", "Current Liabilities", D(36_000)),
    ("acc-out-sgst", "Current Liabilities", D(36_000)),
    ("acc-in-cgst", "Other Current Assets", D(20_700)),
    ("acc-in-sgst", "Other Current Assets", D(20_700)),
]


def _invoice(number: str, client: str, day: date, billed: int, balance: int) -> Invoice:
    total, owed = D(billed), D(balance)
    status = (
        InvoiceStatus.PAID
        if owed == 0
        else InvoiceStatus.OPEN
        if owed == total
        else InvoiceStatus.PARTIALLY_PAID
    )
    return Invoice(
        source_id=f"eval-{number}",
        invoice_number=number,
        party_source_id=f"eval-party-{client}",
        party_name=CLIENTS[client],
        invoice_date=day,
        due_date=day + timedelta(days=30),
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
def evaluation_dataset() -> FinanceRecords:
    return FinanceRecords(
        accounts=tuple(
            Account(sid, name, None, category.value, category, role, True, None)
            for sid, name, category, role in ACCOUNTS
        ),
        parties=tuple(
            Party(f"eval-party-{key}", PartyType.CUSTOMER, name, name, None, "INR", None)
            for key, name in CLIENTS.items()
        ),
        invoices=tuple(_invoice(*row) for row in INVOICES),
        payments_received=tuple(
            PaymentReceived(
                f"eval-pay-{i}",
                f"eval-party-{client}",
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
                f"eval-exp-{i}",
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
