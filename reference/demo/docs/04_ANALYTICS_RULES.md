# Clario Analytics Rules

Use deterministic code for calculations and let the LLM explain the results.

## Revenue Change
```text
change_percent =
((current_period - previous_period) / previous_period) * 100
```
Handle a zero previous period safely.

## Outstanding Receivables
```text
outstanding = sum(invoice.balance)
```

## Days Overdue
```text
days_overdue = today - due_date
```

## Average Invoice Value
```text
average_invoice_value = total_sales / invoice_count
```

## Customer Concentration
```text
customer_share = customer_sales / total_sales
```

## Expense Change
Compare the requested period with an equivalent previous period.

## Business Signals
The MVP may identify:
- Revenue increase/decrease
- Rising expenses
- High overdue receivables
- Large outstanding balances
- Customer concentration
- Significant sales changes
- Significant expense categories

Phrase findings as data-supported observations, e.g. "The data shows..." or "This may be worth reviewing..." rather than absolute financial instructions.
