# Phase 0 — TEST dataset figure verification

Trial organisation `60089553909` (created 2026-09-26, GST disabled) seeded with 21 clearly-labelled TEST records by `scripts/phase0/seed_test_data.py`. Figures were **hand-calculated** from that dataset, then compared with (A) Zoho's own reports, (B) Clario-side calculations from raw Zoho records using the planned Finance rules, and (C) cross-checks between the two.

> These are **TEST figures only**. They validate the API, field mapping and calculation rules — they are not representative of the director's real financial figures.

**Result: 53/53 checks passed.** As of 2026-09-26 (Asia/Kolkata).

| Group | Check | Expected (hand-calculated) | Actual | Result |
|---|---|---|---|---|
| A. Zoho report | pnl_fytd.Operating Income | `108000` | `108000.0` | ✅ |
| A. Zoho report | pnl_fytd.Cost of Goods Sold | `9000` | `9000.0` | ✅ |
| A. Zoho report | pnl_fytd.Gross Profit | `99000` | `99000.0` | ✅ |
| A. Zoho report | pnl_fytd.Operating Expense | `60500` | `60500.0` | ✅ |
| A. Zoho report | pnl_fytd.Operating Profit | `38500` | `38500.0` | ✅ |
| A. Zoho report | pnl_fytd.Net Profit/Loss | `38500` | `38500.0` | ✅ |
| A. Zoho report | pnl_cash.Operating Income | `75000` | `75000.0` | ✅ |
| A. Zoho report | pnl_cash.Operating Profit | `5500` | `5500.0` | ✅ |
| A. Zoho report | pnl_prev_fy.Operating Income | `10000` | `10000.0` | ✅ |
| A. Zoho report | pnl_2026_03.Operating Income | `10000` | `10000.0` | ✅ |
| A. Zoho report | pnl_2026_04.Operating Income | `0` | `0` | ✅ |
| A. Zoho report | pnl_2026_07.Operating Income | `50000` | `50000.0` | ✅ |
| A. Zoho report | pnl_2026_07.Operating Expense | `40000` | `40000.0` | ✅ |
| A. Zoho report | pnl_2026_08.Operating Income | `50000` | `50000.0` | ✅ |
| A. Zoho report | pnl_2026_08.Operating Expense | `18000` | `18000.0` | ✅ |
| A. Zoho report | pnl_2026_09.Operating Income | `8000` | `8000.0` | ✅ |
| A. Zoho report | pnl_2026_09.Cost of Goods Sold | `9000` | `9000.0` | ✅ |
| A. Zoho report | pnl_2026_09.Operating Expense | `2500` | `2500.0` | ✅ |
| A. Zoho report | bs.Assets | `48500` | `48500.0` | ✅ |
| A. Zoho report | bs.Bank | `8000` | `8000.0` | ✅ |
| A. Zoho report | bs.Cash | `-2500` | `-2500.0` | ✅ |
| A. Zoho report | bs.Accounts Receivable | `43000` | `43000.0` | ✅ |
| A. Zoho report | bs.Current Year Earnings | `38500` | `38500.0` | ✅ |
| A. Zoho report | bs.Retained Earnings | `10000` | `10000.0` | ✅ |
| A. Zoho report | pnl_cash report_basis | `Cash` | `Cash` | ✅ |
| A. Zoho report | group_by=month changes P&L output | `False` | `False` | ✅ |
| B. Clario calc | billed_all_data | `118000` | `118000.0` | ✅ |
| B. Clario calc | billed_fytd | `108000` | `108000.0` | ✅ |
| B. Clario calc | billed_by_month | `{'2026-03': Decimal('10000'), '2026-07': Decimal('50000'), '2026-08': Decimal('50000'), '2026-09': Decimal('8000')}` | `{'2026-09': Decimal('8000.0'), '2026-08': Decimal('50000.0'), '2026-07': Decimal('50000.0'), '2026-03': Decimal('10000.0')}` | ✅ |
| B. Clario calc | collected_all_data | `75000` | `75000.0` | ✅ |
| B. Clario calc | collected_by_month | `{'2026-04': Decimal('10000'), '2026-08': Decimal('15000'), '2026-09': Decimal('50000')}` | `{'2026-09': Decimal('50000.0'), '2026-08': Decimal('15000.0'), '2026-04': Decimal('10000.0')}` | ✅ |
| B. Clario calc | collection_ratio_pct_all_data | `63.6` | `63.6` | ✅ |
| B. Clario calc | receivables (draft/void excluded) | `43000` | `43000.0` | ✅ |
| B. Clario calc | receivables if draft/void NOT excluded (must differ) | `51000` | `51000.0` | ✅ |
| B. Clario calc | overdue (derived) | `35000` | `35000.0` | ✅ |
| B. Clario calc | overdue_count | `2` | `2` | ✅ |
| B. Clario calc | days_overdue | `{'INV-000003': 37, 'INV-000004': 14}` | `{'INV-000004': 14, 'INV-000003': 37}` | ✅ |
| B. Clario calc | derived_status | `{'INV-000001': 'paid', 'INV-000002': 'paid', 'INV-000003': 'partially_paid', 'INV-000004': 'open', 'INV-000005': 'open', 'INV-000006': 'draft', 'INV-000007': 'void'}` | `{'INV-000001': 'paid', 'INV-000002': 'paid', 'INV-000003': 'partially_paid', 'INV-000004': 'open', 'INV-000005': 'open', 'INV-000006': 'draft', 'INV-000007': 'void'}` | ✅ |
| B. Clario calc | Zoho status of partially-paid overdue INV-000003 (not trusted) | `overdue` | `overdue` | ✅ |
| B. Clario calc | customer TEST Customer Alpha (billed, collected, outstanding, overdue) | `(Decimal('60000'), Decimal('60000'), Decimal('0'), Decimal('0'))` | `(Decimal('60000.0'), Decimal('60000.0'), Decimal('0'), Decimal('0'))` | ✅ |
| B. Clario calc | customer TEST Customer Beta (billed, collected, outstanding, overdue) | `(Decimal('38000'), Decimal('15000'), Decimal('23000'), Decimal('15000'))` | `(Decimal('38000.0'), Decimal('15000.0'), Decimal('23000.0'), Decimal('15000.0'))` | ✅ |
| B. Clario calc | customer TEST Customer Gamma (billed, collected, outstanding, overdue) | `(Decimal('20000'), Decimal('0'), Decimal('20000'), Decimal('20000'))` | `(Decimal('20000.0'), Decimal('0'), Decimal('20000.0'), Decimal('20000.0'))` | ✅ |
| B. Clario calc | expenses_by_month | `{'2026-07': Decimal('40000'), '2026-08': Decimal('12000'), '2026-09': Decimal('11500')}` | `{'2026-09': Decimal('11500.0'), '2026-08': Decimal('12000.0'), '2026-07': Decimal('40000.0')}` | ✅ |
| B. Clario calc | vendor_payments_by_month | `{'2026-09': Decimal('6000')}` | `{'2026-09': Decimal('6000.0')}` | ✅ |
| B. Clario calc | net_cash_by_month (expenses only) | `{'2026-04': Decimal('10000'), '2026-07': Decimal('-40000'), '2026-08': Decimal('3000'), '2026-09': Decimal('38500')}` | `{'2026-04': Decimal('10000.0'), '2026-07': Decimal('-40000.0'), '2026-08': Decimal('3000.0'), '2026-09': Decimal('38500.0')}` | ✅ |
| B. Clario calc | weekly_last_10 (in, out; expenses only) | `{'2026-08-10': (Decimal('0'), Decimal('12000')), '2026-08-24': (Decimal('15000'), Decimal('0')), '2026-08-31': (Decimal('0'), Decimal('9000')), '2026-09-07': (Decimal('50000'), Decimal('0')), '2026-09-14': (Decimal('0'), Decimal('2500'))}` | `{'2026-08-10': (Decimal('0'), Decimal('12000.0')), '2026-08-24': (Decimal('15000.0'), Decimal('0')), '2026-08-31': (Decimal('0'), Decimal('9000.0')), '2026-09-07': (Decimal('50000.0'), Decimal('0')), '2026-09-14': (Decimal('0'), Decimal('2500.0'))}` | ✅ |
| B. Clario calc | daily_last_30_net (expenses only) | `{'2026-09-05': Decimal('-9000'), '2026-09-10': Decimal('50000'), '2026-09-18': Decimal('-2500')}` | `{'2026-09-05': Decimal('-9000.0'), '2026-09-10': Decimal('50000.0'), '2026-09-18': Decimal('-2500.0')}` | ✅ |
| B. Clario calc | cash_on_hand (bank + cash accounts) | `5500` | `5500.0` | ✅ |
| C. Cross-check | P&L Operating Income == billed FYTD (no GST) | `108000.0` | `108000.0` | ✅ |
| C. Cross-check | Cash-basis Operating Income == collected in FY | `75000.0` | `75000.0` | ✅ |
| C. Cross-check | Balance sheet AR == derived receivables | `43000.0` | `43000.0` | ✅ |
| C. Cross-check | Balance sheet Cash + Bank == bank-accounts API | `5500.0` | `5500.0` | ✅ |
| C. Cross-check | COGS + Opex (accrual) == expenses + bills in FY | `69500.0` | `69500.0` | ✅ |
