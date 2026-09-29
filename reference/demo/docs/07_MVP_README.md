# Clario + Zoho Books MVP

## What This Is
A proof-of-concept for Clario's ability to connect to a real business system and turn its data into conversational intelligence.

One Zoho Books organization connects to one Google ADK analysis agent.

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
Zoho Books Client
 ↓
OAuth 2.0
 ↓
Zoho Books
```

## Required Setup

### Zoho Developer Application
Create a Zoho Books OAuth application and configure:
- Client ID
- Client Secret
- Redirect URI
- Minimum read-only scopes

OAuth documentation:
https://www.zoho.com/books/api/v3/oauth/

### Zoho Organization
Use one test/demo organization and record its organization ID.

### Gemini
Configure a Gemini API key for ADK.

### Environment

```bash
cp .env.example .env
```

Example:

```env
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_REDIRECT_URI=http://localhost:8000/oauth/zoho/callback

ZOHO_ACCOUNTS_URL=https://accounts.zoho.in
ZOHO_API_BASE_URL=https://www.zohoapis.in/books/v3
ZOHO_ORGANIZATION_ID=
ZOHO_REFRESH_TOKEN=

GOOGLE_API_KEY=
GEMINI_MODEL=
```

Confirm the correct Zoho data center before using these defaults.

## Development Order

1. Make OAuth work.
2. Call Zoho Books directly.
3. Normalize responses.
4. Build Zoho client.
5. Build ADK tools.
6. Build one analysis agent.
7. Connect chat.
8. Run integration tests.
9. Run agent evaluation questions.

## First MVP Questions

```text
What were our sales this month?
Compare this month with last month.
Which invoices are overdue?
Which customers owe us the most?
What were our biggest expenses?
Who are our top customers?
Give me a business summary.
What changed significantly this month?
What should I pay attention to?
Explain the biggest change in our business this month.
```

## Definition of Done

- Zoho OAuth works.
- Organization can be connected.
- Access tokens refresh correctly.
- Live Zoho data can be retrieved.
- Responses are normalized.
- ADK tools retrieve the data.
- One analysis agent selects tools.
- Chat works.
- Follow-ups work.
- Answers are grounded.
- No financial numbers are hallucinated.
- Integration test plan passes.

## Product Direction

This MVP is intentionally narrow. The goal is to prove:

> **Can Clario connect to an existing business system and turn its real business data into a useful conversational intelligence experience?**

If this works with Zoho Books, the same architecture can later connect to Crita CRM, inventory, ERP and other systems.
