# ADK Tool Design

Expose narrow, safe Zoho Books capabilities to the Clario agent.

## Initial Tools

### get_sales_summary
Inputs: start_date, end_date
Returns: total sales, invoice count, average invoice value, currency and period.

### get_invoices
Inputs: start_date, end_date, status, customer_id.

### get_overdue_invoices
Returns invoice number, customer, due date, days overdue, total and balance.

### get_customer_balances
Summarizes outstanding receivables by customer.

### get_expense_summary
Summarizes expenses by category and date range.

### get_top_customers
Ranks customers by sales for a date range.

### get_top_items
Ranks items by sales amount/quantity where supported by the API.

### get_financial_report
Retrieves a supported Zoho Books financial report.

### get_business_summary
Combines the most useful read-only metrics into one normalized summary.

## Tool Rules
- Validate inputs.
- Enforce date limits.
- Use the authenticated organization.
- Return Pydantic models.
- Handle pagination.
- Return explicit errors.
- Never expose OAuth tokens.
- Never perform writes.

## Complex Question
For "What should I pay attention to?", the agent can combine revenue trend, overdue receivables, expenses and other available signals, then explain the findings. Do not turn this into an absolute financial recommendation.
