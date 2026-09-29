# Clario request flows — chat and analytics

Use this when you need to explain what happens after someone types in Chat or opens Analytics.

---

## Shared pieces every request uses

Before either flow starts, the browser already has:

| Stored in the browser | Key / source | Purpose |
| --- | --- | --- |
| JWT | `localStorage` → `clario.token` | Proves who the user is |
| Workspace id | `localStorage` → `clario.tenantId` | Which customer workspace this call is for |
| Chat session id | `localStorage` → `clario.sessionId` | ADK in-memory session (chat only) |
| Conversation id | `localStorage` → `clario.conversationId` | Database chat thread (chat only) |

Every API call from the UI adds these headers:

```http
Authorization: Bearer <jwt>
X-Tenant-Id: <tenant uuid>
Content-Type: application/json   # only when a JSON body is sent
```

On the server, `require_tenant` then:

1. Decodes the JWT → loads the `users` row  
2. Checks `memberships` for that user + `X-Tenant-Id`  
3. Loads the `tenants` row and its `zoho_connections` row  

If Zoho is not connected for that workspace, both Chat and Analytics return **503**.

---

## Flow A — User hits Send in Chat

### 1. Frontend (`frontend/app.js`)

1. User types in `#message` and submits `#composer`.
2. UI shows the user bubble immediately.
3. UI posts to **`POST /api/chat`** with this JSON body:

```json
{
  "message": "What were our sales this month?",
  "session_id": "<uuid or null>",
  "conversation_id": "<uuid or null>"
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `message` | Yes | The question text (1–8000 chars) |
| `session_id` | No | ADK session id from the last reply; `null` on a brand-new chat |
| `conversation_id` | No | Database conversation id; `null` starts a new thread |

### 2. API gate (`src/clario/api/main.py` → `chat`)

```text
Headers + body
      ↓
require_tenant (JWT + X-Tenant-Id)
      ↓
Check LLM key is configured (Groq or Gemini)
      ↓
Check this workspace’s Zoho connection is connected
      ↓
ensure_conversation(...)
      ↓
Save user message in `messages`
      ↓
bind_tenant_client(tenant)   ← Zoho client for THIS workspace only
      ↓
ClarioRunner.ask(message, session_id, user_id)
      ↓
Save assistant message + tool_calls
      ↓
Write audit_events row
      ↓
Return ChatResponse
```

`user_id` passed into the agent is `"<tenant_id>:<user_id>"` so ADK sessions stay isolated per workspace user.

### 3. Conversation persistence

`ensure_conversation`:

- If `conversation_id` exists and belongs to this tenant + user → reuse it  
- Else if `session_id` matches an existing thread → reuse it  
- Else create a new `conversations` row with a new `adk_session_id`

First user message also sets `conversations.title` (first 80 characters).

### 4. Agent run (`src/clario/agent/runner.py`)

```text
ensure ADK session (InMemorySessionService)
      ↓
Google ADK Runner.run_async(new_message)
      ↓
Model reads AGENT_INSTRUCTION + tools
      ↓
May call one or more Zoho tools
      ↓
Each tool → AnalysisService → ZohoBooksClient → Zoho Books API
      ↓
Python analytics compute totals / % / rankings
      ↓
Model writes the final answer from tool results
      ↓
Return { session_id, answer, tool_calls }
```

Important split of jobs:

| Layer | Does |
| --- | --- |
| Zoho Books | Source of raw invoices, expenses, reports |
| `AnalysisService` + `analytics/rules.py` | Deterministic math |
| LLM (Groq / Gemini via ADK) | Chooses tools and writes the explanation |

The model is instructed **not** to invent numbers. If a tool errors or has no data, the answer should say there is not enough data in Zoho Books.

### 5. What tools the agent can call

| Tool | Typical question |
| --- | --- |
| `get_sales_summary` | Sales / revenue this month |
| `get_invoices` | Invoice list / filter by status or customer |
| `get_overdue_invoices` | Late invoices |
| `get_customer_balances` | Who owes the most |
| `get_expense_summary` | Biggest expenses |
| `get_top_customers` | Top buyers |
| `get_top_items` | Top products |
| `get_financial_report` | P&L, balance sheet, cash flow, etc. |
| `get_business_summary` | Health / what changed / what to watch |
| `get_customer_payments` | Payment history follow-ups |

Default date window when the user does not name dates: **month-to-date**.

### 6. Response back to the browser

```json
{
  "session_id": "...",
  "conversation_id": "...",
  "answer": "### Finding\n...",
  "tool_calls": [
    { "tool": "get_sales_summary", "args": { "start_date": "", "end_date": "" } }
  ]
}
```

Frontend then:

1. Saves `session_id` and `conversation_id` to `localStorage`  
2. Renders `answer` as markdown in the transcript  
3. Reloads the History list (`GET /api/conversations`)  

### Chat path diagram

```text
Browser Chat UI
   │  POST /api/chat
   │  Authorization + X-Tenant-Id
   │  { message, session_id?, conversation_id? }
   ▼
FastAPI chat()
   │  auth + Zoho ready + LLM ready
   │  DB: conversation + user message
   ▼
bind_tenant_client(workspace Zoho tokens)
   ▼
Google ADK agent
   │  picks tool(s)
   ▼
zoho_tools.*  →  AnalysisService  →  ZohoBooksClient
   │                                      │
   │                                      ▼
   │                               Zoho Books REST (read-only)
   │                                      │
   ▼                                      ▼
analytics/rules.py  ←── normalized invoices / expenses / reports
   ▼
Agent final text answer
   ▼
DB: assistant message + audit
   ▼
Browser shows answer + refreshes History
```

---

## Flow B — Analytics overview loads

Analytics does **not** use the LLM. Same Zoho data, same Python math, no chat agent.

### 1. When the UI fetches it

`loadAnalytics()` runs when:

- User opens the **Analytics** view  
- User clicks **Refresh analytics**  
- Workspace switch / Zoho connect succeeds while Analytics is open  

### 2. Frontend request

```http
GET /api/analytics/overview
Authorization: Bearer <jwt>
X-Tenant-Id: <tenant uuid>
```

Optional query params (UI does not send them today):

| Param | Meaning |
| --- | --- |
| `start_date` | Inclusive `YYYY-MM-DD` |
| `end_date` | Inclusive `YYYY-MM-DD` |

If both are omitted, the server uses **month-to-date**.

### 3. API (`analytics_overview`)

```text
require_tenant
      ↓
Zoho connected?
      ↓
bind_tenant_client(tenant)
      ↓
AnalysisService.get_business_summary(start_date, end_date)
      ↓
clear_tenant_client()
      ↓
JSON overview → renderAnalytics()
```

### 4. What `get_business_summary` fetches and computes

```text
Resolve current period (default: month-to-date)
Resolve previous comparable period
      ↓
Zoho: current organization (name, currency)
Zoho: invoices spanning previous+current window
Zoho: expenses spanning previous+current window
Zoho: unpaid invoices (for receivables)
      ↓
Python:
  sales summary (current + previous)
  expense summary (current + previous)
  receivables + overdue
  top 5 customers
  % change vs previous period
  business signals (thresholds)
      ↓
Return one BusinessSummary JSON object
```

### 5. Fields the UI reads

| UI area | JSON path |
| --- | --- |
| Title | `organization_name` |
| Period line | `current_period_start`, `current_period_end`, `currency` |
| Sales card | `sales.total_sales`, `sales.invoice_count`, `sales_change` |
| Expenses card | `expenses.total_expenses`, `expenses.expense_count`, `expense_change` |
| Outstanding | `receivables.outstanding`, `receivables.invoice_count` |
| Overdue | `receivables.overdue`, `receivables.overdue_count` |
| Top customers | `top_customers[]` → `customer`, `sales`, `share_percent`, `invoice_count` |
| Signals | `signals[]` → `name`, `severity`, `observation` |

### Signal thresholds (same engine chat uses for “what to watch”)

| Signal | Rule of thumb |
| --- | --- |
| Revenue change | \|% change\| ≥ 10% (high if ≥ 20%) |
| Rising expenses | Expense increase ≥ 10% |
| High overdue receivables | Overdue share of outstanding ≥ 25% |
| Large outstanding balance | Names the biggest open customer balance |
| Customer concentration | Top customer ≥ 30% of period sales |
| Largest expense category | Names the biggest category |

### Analytics path diagram

```text
Browser Analytics view
   │  GET /api/analytics/overview
   │  Authorization + X-Tenant-Id
   ▼
FastAPI analytics_overview()
   │  auth + Zoho ready
   ▼
bind_tenant_client(workspace)
   ▼
AnalysisService.get_business_summary()
   │
   ├─ Zoho org / invoices / expenses / unpaid
   └─ analytics/rules.py (totals, deltas, signals)
   ▼
JSON BusinessSummary
   ▼
renderAnalytics() paints cards + lists
```

---

## How Chat and Analytics differ

| | Chat | Analytics |
| --- | --- | --- |
| Trigger | User question | Open / refresh Analytics |
| Endpoint | `POST /api/chat` | `GET /api/analytics/overview` |
| Uses LLM? | Yes (ADK + Groq/Gemini) | No |
| Uses Zoho? | Yes, via whichever tools the agent picks | Yes, fixed business-summary fetch |
| Uses Python math? | Yes, inside tools | Yes, same summary builder |
| Writes to DB? | `conversations`, `messages`, `audit_events` | No (read-only for this call) |
| Follow-ups? | Yes, via `session_id` / `conversation_id` | N/A |

Same grounding rule for both: **numbers come from Zoho or from Python calculations on Zoho data.**

---

## Tenant binding (why workspaces stay separate)

For both flows, `bind_tenant_client(tenant)`:

1. Reads that workspace’s encrypted Zoho tokens / org id / data center  
2. Builds a `ZohoBooksClient` for that connection only  
3. Hands that client to `AnalysisService` and to ADK tools for the request  
4. `clear_tenant_client()` runs in `finally` so the next request cannot reuse another workspace’s client  

---

## Quick “say this out loud” version

**Chat:**  
The browser sends the question plus optional conversation ids with the user’s JWT and workspace id. FastAPI checks membership and Zoho. It saves the question, binds that workspace’s Zoho client, lets the ADK agent pick tools, tools fetch live Zoho data, Python does the math, the model writes the answer, FastAPI saves the answer and returns it.

**Analytics:**  
The browser asks for an overview with the same auth headers. FastAPI binds that workspace’s Zoho client, pulls invoices and expenses for month-to-date vs the previous period, Python builds the dashboard numbers and signals, and the UI paints the cards. No language model is involved.
