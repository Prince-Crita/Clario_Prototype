# Clario Chat Flow

```text
User question
  ↓
Clario Agent
  ↓
Understand intent
  ↓
Select Zoho Books tools
  ↓
Fetch current data
  ↓
Normalize data
  ↓
Deterministic calculations
  ↓
Agent analysis
  ↓
Grounded response
```

## Example
User: "Which customers owe us the most?"

The agent should call the customer balance tool, aggregate balances, rank them and explain the period/context.

## Follow-up
User: "What about their payment history?"

The agent should understand that "their" refers to the customers from the previous answer.

## Complex Question
For "How is the business doing this month?", combine appropriate sales, expense and receivables tools, then summarize the result.

## Grounding
Every numeric statement must come from Zoho Books data or a deterministic calculation based on retrieved data.

If data is unavailable, say so. Never fabricate a fallback.
