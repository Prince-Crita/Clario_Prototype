# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Phase 0: compare Zoho's responses for the TEST dataset against hand-calculated figures.

Reads .spike/raw/*.json (from zoho_spike.py run against the trial org after seed_test_data.py) and checks:
  A. Zoho's own reports (P&L accrual/cash, monthly P&L, balance sheet) against hand calculations.
  B. Clario-side calculations from raw records (the planned Finance-domain rules) against hand calculations.
  C. Cross-checks between A and B (dashboard and assistant must agree with Zoho's ledger).

TEST data only — these numbers say nothing about the director's real figures.
Output: docs/phase0/test-data-verification.md
Run from the repo root:  python -m uv run scripts/phase0/verify_test_figures.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from _env import REPO_ROOT

RAW = REPO_ROOT / ".spike" / "raw"
REPORT = REPO_ROOT / "docs" / "phase0" / "test-data-verification.md"
AS_OF = date(2026, 9, 26)          # "today" in Asia/Kolkata when the spike ran
FY_START = date(2026, 4, 1)
EXCLUDED_STATUSES = {"draft", "void"}
D = Decimal

# ---------------------------------------------------------------- hand-calculated expectations
# Derived by hand from the seeded dataset (scripts/phase0/seed_test_data.py); no GST.
EXPECTED: dict[str, Any] = {
    # Zoho reports
    "pnl_fytd.Operating Income": D(108000), "pnl_fytd.Cost of Goods Sold": D(9000),
    "pnl_fytd.Gross Profit": D(99000), "pnl_fytd.Operating Expense": D(60500),
    "pnl_fytd.Operating Profit": D(38500), "pnl_fytd.Net Profit/Loss": D(38500),
    "pnl_cash.Operating Income": D(75000), "pnl_cash.Operating Profit": D(5500),
    "pnl_prev_fy.Operating Income": D(10000),
    "pnl_2026_03.Operating Income": D(10000), "pnl_2026_04.Operating Income": D(0),
    "pnl_2026_07.Operating Income": D(50000), "pnl_2026_07.Operating Expense": D(40000),
    "pnl_2026_08.Operating Income": D(50000), "pnl_2026_08.Operating Expense": D(18000),
    "pnl_2026_09.Operating Income": D(8000), "pnl_2026_09.Cost of Goods Sold": D(9000),
    "pnl_2026_09.Operating Expense": D(2500),
    "bs.Assets": D(48500), "bs.Bank": D(8000), "bs.Cash": D(-2500), "bs.Accounts Receivable": D(43000),
    "bs.Current Year Earnings": D(38500), "bs.Retained Earnings": D(10000),
    # Clario-side, from records
    "billed_all_data": D(118000), "billed_fytd": D(108000),
    "billed_by_month": {"2026-03": D(10000), "2026-07": D(50000), "2026-08": D(50000), "2026-09": D(8000)},
    "collected_all_data": D(75000),
    "collected_by_month": {"2026-04": D(10000), "2026-08": D(15000), "2026-09": D(50000)},
    "collection_ratio_pct_all_data": D("63.6"),
    "receivables": D(43000), "overdue": D(35000), "overdue_count": 2,
    "days_overdue": {"INV-000003": 37, "INV-000004": 14},
    "derived_status": {"INV-000001": "paid", "INV-000002": "paid", "INV-000003": "partially_paid",
                       "INV-000004": "open", "INV-000005": "open", "INV-000006": "draft", "INV-000007": "void"},
    "customer.TEST Customer Alpha": (D(60000), D(60000), D(0), D(0)),
    "customer.TEST Customer Beta": (D(38000), D(15000), D(23000), D(15000)),
    "customer.TEST Customer Gamma": (D(20000), D(0), D(20000), D(20000)),
    "expenses_by_month": {"2026-07": D(40000), "2026-08": D(12000), "2026-09": D(11500)},
    "vendor_payments_by_month": {"2026-09": D(6000)},
    "net_cash_by_month_expenses_only": {"2026-04": D(10000), "2026-07": D(-40000), "2026-08": D(3000),
                                        "2026-09": D(38500)},
    "weekly_last_10": {"2026-08-10": (D(0), D(12000)), "2026-08-24": (D(15000), D(0)),
                       "2026-08-31": (D(0), D(9000)), "2026-09-07": (D(50000), D(0)),
                       "2026-09-14": (D(0), D(2500))},
    "daily_last_30_net": {"2026-09-05": D(-9000), "2026-09-10": D(50000), "2026-09-18": D(-2500)},
    "cash_on_hand": D(5500),
}


def load(name: str) -> Any:
    # Zoho sends amounts as JSON floats: parse them straight to Decimal, never binary float.
    return json.loads((RAW / f"{name}.json").read_text(encoding="utf-8"), parse_float=Decimal)


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def section_totals(node: Any, out: dict[str, Decimal] | None = None) -> dict[str, Decimal]:
    """Flatten a Zoho report tree to {section/account name: total} (first occurrence wins)."""
    out = {} if out is None else out
    if isinstance(node, dict):
        if "name" in node and "total" in node:
            out.setdefault(str(node["name"]), money(node["total"]))
        for key, value in node.items():
            if key not in {"previous_values", "previous_total", "page_context"}:
                section_totals(value, out)
    elif isinstance(node, list):
        for item in node:
            section_totals(item, out)
    return out


def month_key(value: str) -> str:
    return value[:7]


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def main() -> None:
    results: list[tuple[str, str, str, str, bool]] = []  # group, check, expected, actual, ok

    def check(group: str, name: str, expected: Any, actual: Any) -> None:
        results.append((group, name, str(expected), str(actual), expected == actual))

    # ---------------- A. Zoho reports
    reports = {
        "pnl_fytd": section_totals(load("report_pnl_fytd")["profit_and_loss"]),
        "pnl_cash": section_totals(load("report_pnl_fytd_cash")["profit_and_loss"]),
        "pnl_prev_fy": section_totals(load("report_pnl_prev_fy")["profit_and_loss"]),
        "bs": section_totals(load("report_balancesheet")["balance_sheet"]),
    }
    for month in ("2026_03", "2026_04", "2026_07", "2026_08", "2026_09"):
        reports[f"pnl_{month}"] = section_totals(load(f"report_pnl_{month}")["profit_and_loss"])
    for key, expected in EXPECTED.items():
        prefix, _, label = key.partition(".")
        if prefix in reports:
            check("A. Zoho report", key, expected, reports[prefix].get(label, Decimal(0)))
    check("A. Zoho report", "pnl_cash report_basis", "Cash",
          load("report_pnl_fytd_cash")["page_context"].get("report_basis"))
    grouped = load("report_pnl_fytd_groupby_month")
    check("A. Zoho report", "group_by=month changes P&L output", False,
          grouped["profit_and_loss"] != load("report_pnl_fytd")["profit_and_loss"])

    # ---------------- B. Clario-side calculations from records
    invoices = load("invoices")
    payments = load("customerpayments")
    expenses = load("expenses")
    vendor_payments = load("vendorpayments")["vendorpayments"]
    banks = load("bankaccounts")["bankaccounts"]
    billable = [i for i in invoices if i["status"] not in EXCLUDED_STATUSES]

    billed_by_month: dict[str, Decimal] = defaultdict(Decimal)
    for inv in billable:
        billed_by_month[month_key(inv["date"])] += money(inv["total"])
    check("B. Clario calc", "billed_all_data", EXPECTED["billed_all_data"], sum(billed_by_month.values()))
    check("B. Clario calc", "billed_fytd", EXPECTED["billed_fytd"],
          sum(money(i["total"]) for i in billable if date.fromisoformat(i["date"]) >= FY_START))
    check("B. Clario calc", "billed_by_month", EXPECTED["billed_by_month"], dict(billed_by_month))

    collected_by_month: dict[str, Decimal] = defaultdict(Decimal)
    for pay in payments:
        collected_by_month[month_key(pay["date"])] += money(pay["bcy_amount"])
    collected = sum(collected_by_month.values())
    check("B. Clario calc", "collected_all_data", EXPECTED["collected_all_data"], collected)
    check("B. Clario calc", "collected_by_month", EXPECTED["collected_by_month"], dict(collected_by_month))
    check("B. Clario calc", "collection_ratio_pct_all_data", EXPECTED["collection_ratio_pct_all_data"],
          (collected / sum(billed_by_month.values()) * 100).quantize(Decimal("0.1")))

    open_invoices = [i for i in billable if money(i["balance"]) > 0]
    overdue = [i for i in open_invoices if date.fromisoformat(i["due_date"]) < AS_OF]
    check("B. Clario calc", "receivables (draft/void excluded)", EXPECTED["receivables"],
          sum(money(i["balance"]) for i in open_invoices))
    check("B. Clario calc", "receivables if draft/void NOT excluded (must differ)", Decimal(51000),
          sum(money(i["balance"]) for i in invoices if money(i["balance"]) > 0))
    check("B. Clario calc", "overdue (derived)", EXPECTED["overdue"], sum(money(i["balance"]) for i in overdue))
    check("B. Clario calc", "overdue_count", EXPECTED["overdue_count"], len(overdue))
    check("B. Clario calc", "days_overdue", EXPECTED["days_overdue"],
          {i["invoice_number"]: (AS_OF - date.fromisoformat(i["due_date"])).days for i in overdue})

    def derived_status(inv: dict) -> str:
        if inv["status"] in EXCLUDED_STATUSES:
            return inv["status"]
        balance, total = money(inv["balance"]), money(inv["total"])
        if balance == 0:
            return "paid"
        return "partially_paid" if balance < total else "open"

    check("B. Clario calc", "derived_status", EXPECTED["derived_status"],
          {i["invoice_number"]: derived_status(i) for i in sorted(invoices, key=lambda i: i["invoice_number"])})
    check("B. Clario calc", "Zoho status of partially-paid overdue INV-000003 (not trusted)", "overdue",
          next(i["status"] for i in invoices if i["invoice_number"] == "INV-000003"))

    for customer in ("TEST Customer Alpha", "TEST Customer Beta", "TEST Customer Gamma"):
        rows = [i for i in billable if i["customer_name"] == customer]
        actual = (sum((money(i["total"]) for i in rows), Decimal(0)),
                  sum((money(p["bcy_amount"]) for p in payments if p["customer_name"] == customer), Decimal(0)),
                  sum((money(i["balance"]) for i in rows), Decimal(0)),
                  sum((money(i["balance"]) for i in rows if i in overdue), Decimal(0)))
        check("B. Clario calc", f"customer {customer} (billed, collected, outstanding, overdue)",
              EXPECTED[f"customer.{customer}"], actual)

    expenses_by_month: dict[str, Decimal] = defaultdict(Decimal)
    for exp in expenses:
        expenses_by_month[month_key(exp["date"])] += money(exp["bcy_total"])
    check("B. Clario calc", "expenses_by_month", EXPECTED["expenses_by_month"], dict(expenses_by_month))
    vp_by_month: dict[str, Decimal] = defaultdict(Decimal)
    for vp in vendor_payments:
        vp_by_month[month_key(vp["date"])] += money(vp["bcy_amount"])
    check("B. Clario calc", "vendor_payments_by_month", EXPECTED["vendor_payments_by_month"], dict(vp_by_month))
    months = sorted(set(collected_by_month) | set(expenses_by_month))
    check("B. Clario calc", "net_cash_by_month (expenses only)", EXPECTED["net_cash_by_month_expenses_only"],
          {m: collected_by_month.get(m, Decimal(0)) - expenses_by_month.get(m, Decimal(0)) for m in months})

    first_week = week_start(AS_OF) - timedelta(weeks=9)
    weekly: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for pay in payments:
        day = date.fromisoformat(pay["date"])
        if day >= first_week:
            weekly[week_start(day).isoformat()][0] += money(pay["bcy_amount"])
    for exp in expenses:
        day = date.fromisoformat(exp["date"])
        if day >= first_week:
            weekly[week_start(day).isoformat()][1] += money(exp["bcy_total"])
    check("B. Clario calc", "weekly_last_10 (in, out; expenses only)", EXPECTED["weekly_last_10"],
          {k: tuple(v) for k, v in sorted(weekly.items())})
    daily: dict[str, Decimal] = defaultdict(Decimal)
    first_day = AS_OF - timedelta(days=29)
    for pay in payments:
        if date.fromisoformat(pay["date"]) >= first_day:
            daily[pay["date"]] += money(pay["bcy_amount"])
    for exp in expenses:
        if date.fromisoformat(exp["date"]) >= first_day:
            daily[exp["date"]] -= money(exp["bcy_total"])
    check("B. Clario calc", "daily_last_30_net (expenses only)", EXPECTED["daily_last_30_net"], dict(sorted(daily.items())))
    cash_on_hand = sum(money(b["bcy_balance"]) for b in banks if b["account_type"] in {"bank", "cash"})
    check("B. Clario calc", "cash_on_hand (bank + cash accounts)", EXPECTED["cash_on_hand"], cash_on_hand)

    # ---------------- C. Cross-checks (records vs Zoho ledger)
    pnl = reports["pnl_fytd"]
    check("C. Cross-check", "P&L Operating Income == billed FYTD (no GST)", pnl["Operating Income"],
          sum(money(i["total"]) for i in billable if date.fromisoformat(i["date"]) >= FY_START))
    check("C. Cross-check", "Cash-basis Operating Income == collected in FY", reports["pnl_cash"]["Operating Income"],
          sum(money(p["bcy_amount"]) for p in payments if date.fromisoformat(p["date"]) >= FY_START))
    check("C. Cross-check", "Balance sheet AR == derived receivables", reports["bs"]["Accounts Receivable"],
          sum(money(i["balance"]) for i in open_invoices))
    check("C. Cross-check", "Balance sheet Cash + Bank == bank-accounts API", reports["bs"]["Cash"] + reports["bs"]["Bank"],
          cash_on_hand)
    check("C. Cross-check", "COGS + Opex (accrual) == expenses + bills in FY", pnl["Cost of Goods Sold"] +
          pnl["Operating Expense"], sum(money(e["bcy_total"]) for e in expenses) + Decimal(6000))

    write_report(results)
    passed = sum(ok for *_, ok in results)
    print(f"{passed}/{len(results)} checks passed. Report: {REPORT.relative_to(REPO_ROOT)}")


def write_report(results: list[tuple[str, str, str, str, bool]]) -> None:
    passed = sum(ok for *_, ok in results)
    lines = [
        "# Phase 0 — TEST dataset figure verification",
        "",
        "Trial organisation `60089553909` (created 2026-09-26, GST disabled) seeded with 21 clearly-labelled "
        "TEST records by `scripts/phase0/seed_test_data.py`. Figures were **hand-calculated** from that "
        "dataset, then compared with (A) Zoho's own reports, (B) Clario-side calculations from raw Zoho "
        "records using the planned Finance rules, and (C) cross-checks between the two.",
        "",
        "> These are **TEST figures only**. They validate the API, field mapping and calculation rules — "
        "they are not representative of the director's real financial figures.",
        "",
        f"**Result: {passed}/{len(results)} checks passed.** As of {AS_OF.isoformat()} (Asia/Kolkata).",
        "",
        "| Group | Check | Expected (hand-calculated) | Actual | Result |",
        "|---|---|---|---|---|",
    ]
    for group, name, expected, actual, ok in results:
        lines.append(f"| {group} | {name} | `{expected}` | `{actual}` | {'✅' if ok else '❌'} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
