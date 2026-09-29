# Reconciling Clario's finance figures with Zoho Books

Use this when checking a connected organisation's Command Centre against Zoho Books: the live
check for the trial organisation, and later the director's acceptance session on live data.
Every figure below is calculated by `backend/src/clario/domains/finance` from the mirror, and the
golden test (`backend/tests/db/test_golden.py`) proves the formulas reproduce the director's PDFs.

**Before you start:** refresh the data (Zoho Books page → *Refresh now*, or
`uv run clario sync run --workspace <slug>`) and note the "data as of" time. Zoho figures entered
after that time will differ.

| Clario figure | Basis · window | Where to check in Zoho Books |
|---|---|---|
| Revenue | Accrual, FY to date, excl. GST | Reports → **Profit and Loss**, this fiscal year → *Operating Income* total |
| Cost of goods sold / Operating expenses | Accrual, FY to date | Same report → *Cost of Goods Sold* / *Operating Expense* totals |
| Net P&L | Accrual, FY to date | Same report → **Operating Profit** (not *Net Profit/Loss*, which adds non-operating items: director Q4) |
| Gross margin, net margin | Derived | (Operating Income − COGS) ÷ Operating Income; Operating Profit ÷ Operating Income |
| Billed | Invoice totals incl. GST, draft/void excluded, current + previous FY | Sales → Invoices, filter by date, exclude Draft and Void, sum *Amount* |
| Cash collected | Customer payments, current + previous FY | Sales → Payments Received, same dates, sum *Amount* (base currency) |
| Total costs' month-on-month change | Cash expense records, this month vs last | Purchases → Expenses, filter each month, sum *Amount* |
| Cash on hand | Balance, today | Banking → sum of bank and cash accounts; or Balance Sheet → *Cash* + *Bank* |
| Receivables | Balance, today | Reports → **Balance Sheet** → *Accounts Receivable*; or Invoices with a balance, excluding Draft and Void |
| Overdue (count, days) | Derived from due dates, org time zone | Invoices with a balance and a due date before today. Zoho's own "Overdue" label is not used, because it hides partly paid invoices. |
| Monthly table (billed, collected, expenses, net cash) | Cash | The three lists above, per calendar month; net cash = collected − expenses |
| Expense trend / top categories | Cash expense records by account | Purchases → Expenses, grouped by *Account* |
| Expense mix ("where the money goes") | Accrual, FY to date | Profit and Loss → *Operating Expense* accounts |
| Revenue by client | Billed, lifetime | Reports → Sales by Customer (all dates), excluding Draft and Void |
| GST payable (pending director Q5) | Ledger balances, today | Balance Sheet → output tax accounts − input tax accounts. **Unverified until a GST-enabled organisation is connected** (plan risk R2). |

**Known intended differences** (definitions pending the director's answers, plan §22.4):
- Billed and collected include the previous fiscal year (Q1), as the PDFs do.
- Total costs' MoM compares **cash** expenses, while the KPI value is accrual (Q2).
- The "latest month spend" run-rate is the current month's cash expenses, not payroll (Q3).
- Vendor bill payments are not in cash expenses (Q7).

Record each check (figure, Clario value, Zoho value, difference, reason) and keep it with the
phase notes. A difference outside the list above is a defect.
