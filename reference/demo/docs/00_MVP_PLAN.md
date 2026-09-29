# Clario + Zoho Books — MVP Plan

## Objective
Build one Clario analysis agent connected to one real Zoho Books organization. The agent should answer natural-language business questions using live Zoho Books data.

**MVP flow:** Zoho Books → Clario tools → Google ADK analysis agent → grounded business answer.

## Scope
Include:
- One Google ADK analysis agent
- One Zoho Books organization
- OAuth 2.0
- Read-only Zoho Books APIs
- Sales, invoices, customers, expenses and reports
- Conversational chat
- Deterministic calculations where possible
- Follow-up questions
- Complete setup and testing documentation

Do not include yet:
- Write operations
- Autonomous financial actions
- Multiple agents
- Multi-tenant production infrastructure
- Complex long-term memory

## Architecture

```text
User
  ↓
Clario Chat
  ↓
Google ADK Analysis Agent
  ↓
Zoho Books Tools
  ↓
Zoho Books Client (OAuth + REST)
  ↓
Zoho Books
```

## Success Criteria
A developer can connect a Zoho Books test organization, start the app, ask at least 10 useful business questions, and receive answers grounded in live Zoho data without fabricated numbers.
