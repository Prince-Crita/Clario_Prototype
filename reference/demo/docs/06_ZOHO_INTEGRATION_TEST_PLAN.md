# Zoho Books Integration Test Plan

## Objective
First prove:

**OAuth → Zoho API → normalized data**

Then prove:

**Zoho API → ADK tools → Clario agent**

## Phase 1 — OAuth
Test:
- Authorization URL
- Consent
- Callback
- Access token generation
- Refresh token generation
- Access token refresh
- Expired token
- Revoked refresh token

## Phase 2 — Organization
Verify:
- Organization is returned
- Correct organization ID
- Organization name
- Currency
- Correct data-center domain

## Phase 3 — Basic APIs
Test:
- Organizations
- Invoices
- Contacts
- Customer payments
- Expenses
- Items/settings

Verify status, schema, pagination, dates, currency, balances and statuses.

## Phase 4 — Reports
Validate:
- Profit and Loss
- Cash Flow Statement
- Balance Sheet
- Sales by Customer
- Sales by Item
- Inventory Summary if relevant
- Receivables Aging
- Invoice Details

## Phase 5 — Normalization
For every endpoint:

```text
Zoho response
  ↓
Pydantic model
  ↓
Clario business model
```

Test missing fields, empty responses and pagination.

## Phase 6 — ADK Tools
Run every tool independently and compare its output with direct Zoho API results.

## Phase 7 — Agent
Test:
1. What were sales this month?
2. Compare this month with last month.
3. Which invoices are overdue?
4. Which customers owe us the most?
5. What were our biggest expenses?
6. Give me a business summary.
7. What changed significantly this month?
8. What should I pay attention to?
9. Show top customers.
10. Explain the biggest change.

## Phase 8 — Grounding
For known questions, verify:

```text
Question
↓
Raw Zoho response
↓
Normalized data
↓
Tool call
↓
Final answer
```

Check for fabricated numbers, wrong dates, wrong currency, wrong organization and calculation errors.

## Phase 9 — Failure Testing
Test:
- Expired token
- Revoked token
- Wrong organization ID
- Zoho unavailable
- Rate limiting
- Invalid date
- Empty period
- Missing customer
- Pagination
- Malformed response

The agent must fail gracefully.
