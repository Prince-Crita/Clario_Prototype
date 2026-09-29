# Clario MVP — Team Brief

Read this once, then use the demo script at the end when you explain it.

## The one-sentence version

Clario is Crita's business intelligence product. This MVP connects a customer's **Zoho Books** organization and turns that live data into a dashboard and a conversation. The numbers come from Zoho. Python does the math. The AI explains the result in plain language.

The question this MVP is built to answer:

> Can Clario connect to a real business system and turn its data into something a person can actually use?

Zoho Books is the first system. If this pattern works, the same shape can later connect to Crita CRM, inventory, and ERP.

---

## Who it is for

A business that already keeps its books in Zoho Books.

They do not learn a new report builder. They sign in, connect their Zoho organization, look at a month-to-date overview, and ask questions the way they would ask a finance colleague.

Each customer gets their own **workspace**. One Clario service can host many workspaces. A workspace's Zoho login, chat history, and users stay inside that workspace.

---

## What a person actually sees

The app has three moments.

### 1. Sign in and pick a workspace

- Create an account (email, password, full name, workspace name) or sign in.
- A person can belong to more than one workspace and switch between them.
- Roles are **owner**, **admin**, **member**, and **viewer**. Connecting or disconnecting Zoho requires owner or admin.

### 2. Connect Zoho Books

Each workspace brings its own Zoho API Console app:

- Client ID and Client Secret
- Data center (India, US, Europe, Australia, Japan, Canada)
- Organization ID (can be filled after the first successful connection)
- Then either **Connect with Zoho** (OAuth in the browser) or paste a refresh token

Clario stores those tokens encrypted. The chat screen never sees the secret.

Zoho access is **read-only**: invoices, contacts, settings, expenses, customer payments, and accountant reports. Clario cannot create invoices, record payments, or edit books.

### 3. Two screens after connect

**Analytics** is the default screen. It loads a month-to-date snapshot straight from Zoho (no chat, no AI):

| Card | What it shows |
| --- | --- |
| Sales | Total sales, invoice count, change vs the previous period |
| Expenses | Total expenses, expense count, change vs the previous period |
| Outstanding | Money still owed, count of open invoices |
| Overdue | Overdue amount and how many invoices are late |
| Top customers | Up to five customers by sales, with their share of the period |
| Signals | Short observations the rules engine decided are worth a look |

**Chat** is the second screen. The person types a question. Clario answers from that workspace's live Zoho data and keeps the thread so follow-ups work ("what about their payment history?").

Old chats are saved per workspace. A person can start a new chat or delete one.

---

## Questions it is built to answer

These are the questions to demo. They match the tools the agent is allowed to use.

- What were our sales this month?
- Compare this month with last month.
- Which invoices are overdue?
- Which customers owe us the most?
- What were our biggest expenses?
- Who are our top customers?
- What are our top-selling items?
- Give me a business summary.
- What changed significantly this month?
- What should I pay attention to?
- How is the business doing?
- Show me this customer's invoices / payment history (as a follow-up).

Supported financial reports, when the person asks for one: profit and loss, balance sheet, cash flow, sales by customer, sales by item, inventory summary, aging, customer balances.

If Zoho has no data for the period, or the call fails, the answer says there is not enough data in Zoho Books to answer reliably. It does not fill the gap with a guessed number.

---

## How an answer is produced

This is the part worth drawing on a whiteboard.

```text
Person asks a question
        ↓
Clario agent (Google ADK)
  reads the question and picks a tool
        ↓
Tool fetches live data from that workspace's Zoho Books
        ↓
Python calculates totals, averages, rankings, and % change
        ↓
Agent writes the explanation using those results
```

Three jobs stay separate on purpose:

1. **Zoho** is the source of the raw numbers.
2. **Python** does the arithmetic: percent change, average invoice value, days overdue, customer share of sales, outstanding receivables. The model is told to copy those results, not recompute them.
3. **The language model** chooses the tool, then writes the explanation. Default provider is **Groq**. **Gemini** is the other supported option. The provider is a server setting, not something the customer picks in the UI.

A full answer is shaped like this:

- **Finding** — the result in one or two sentences
- **Evidence** — the numbers, dates, currency, and names from the tools
- **Analysis** — what the data indicates ("The data shows…")
- **What to watch** — a risk or change supported by those numbers

Narrow questions (for example "list overdue invoices") stay short. The product describes what the data shows. It does not give financial advice and it does not tell the customer to take an action in Zoho.

---

## What the agent is allowed to look up

These are the only Zoho capabilities the agent can call. Each one is read-only.

| Tool | Used when someone asks about… |
| --- | --- |
| Sales summary | Revenue, sales this month, invoice volume |
| Invoices | A list of invoices, or one customer's invoices |
| Overdue invoices | Late invoices, aging |
| Customer balances | Who owes the most, outstanding receivables |
| Expense summary | Biggest expenses, spending by category |
| Top customers | Who bought the most, and their share of sales |
| Top items | Best-selling products |
| Financial report | P&L, balance sheet, cash flow, and the other reports above |
| Business summary | Health, what changed, what to watch, a monthly overview |
| Customer payments | Payment history, usually as a follow-up |

If the person does not name dates, tools use **the current month through today**. A named period ("last month", "January") is passed as explicit dates. A single query cannot span more than 366 days.

---

## What the Analytics screen flags on its own

The dashboard uses the same business-summary calculation as chat. Signals appear only when a threshold is crossed:

| Signal | When it appears |
| --- | --- |
| Revenue change | Sales moved by 10% or more vs the previous period (marked high at 20% or more) |
| Rising expenses | Expenses rose by 10% or more vs the previous period |
| High overdue receivables | 25% or more of outstanding money is overdue |
| Large outstanding balance | Names the customer with the biggest open balance |
| Customer concentration | One customer is 30% or more of sales in the period |
| Largest expense category | Names the biggest expense category and its total |

Wording is observational: "The data shows…" and "This may be worth reviewing."

---

## How workspaces stay separate

Clario is one service with many customers. Isolation is by workspace (`tenant`):

- Every business row belongs to one workspace.
- Every API call checks that the signed-in user is a member of that workspace.
- Zoho tokens, and the optional per-workspace OAuth client secret, are encrypted at rest. The full secret is never sent back to the browser.
- A chat request uses only that workspace's Zoho connection for that request.

Each workspace is expected to use **its own** Zoho API Console app (Client ID and Secret). A platform-level Zoho app in the server environment is only a fallback.

Local development stores data in SQLite. Production uses PostgreSQL.

---

## What this MVP includes, and what it leaves for later

**In this MVP**

- Accounts, workspaces, and roles
- Per-workspace Zoho Books connection (OAuth or refresh token)
- Read-only access to sales, invoices, customers, expenses, payments, and reports
- Analytics dashboard
- Conversational chat with follow-ups and saved threads
- Deterministic calculations
- Encrypted credentials and an audit trail

**Later, on purpose**

- Writing back to Zoho (creating or editing invoices, payments, bills)
- Autonomous actions ("pay this" or "send this reminder")
- Multiple specialist agents
- Long-term memory beyond the current chat thread
- Invite links for people who do not have an account yet
- Database row-level security policies (isolation today is enforced in the application)

---

## A 5-minute explanation you can give the team

**1. The problem (30 seconds)**  
Business owners already have the numbers in Zoho Books. Getting an answer still means opening reports and doing the comparison by hand. Clario is the layer that sits on top and answers in conversation.

**2. The product (1 minute)**  
Show the two screens. Analytics is the snapshot: sales, expenses, what is owed, what is late, top customers, and a few signals. Chat is for the question they actually have: "who owes us the most?" or "what changed this month?"

**3. Why the numbers are trustworthy (1 minute)**  
Draw the four boxes: question → agent picks a tool → Zoho returns live data → Python calculates → the model explains. Say this sentence out loud:

> Every figure in the answer is copied from Zoho or from a calculation our code already did. If Zoho does not have the data, Clario says so.

**4. Why it can hold more than one customer (1 minute)**  
One workspace per customer. Their Zoho secrets are encrypted and never shared with another workspace. Only an owner or admin can connect Zoho. Everyone else can look at analytics and chat.

**5. What we are proving (30 seconds)**  
This MVP proves the pattern on one real system, Zoho Books, with read-only access. It is the template for connecting Clario to the rest of a customer's business systems.

**6. Live demo (1–2 minutes)**  
Use a connected test organization and ask, in order:

1. "What were our sales this month?"
2. "Compare this month with last month."
3. "Which customers owe us the most?"
4. "What about their payment history?" — this shows that follow-ups remember the previous answer.
5. "What should I pay attention to?"

Point at the Analytics screen afterward and note that those same figures were calculated without the chat model.

---

## Short answers if someone asks

**Does the AI invent the figures?**  
The model writes the sentences. Totals, percentages, rankings, and days overdue are computed in Python from Zoho's response, and the model is instructed to copy them.

**Can it change our books?**  
The Zoho connection requests read scopes only. There is no tool that creates, updates, or deletes anything in Zoho.

**Is this one company or many?**  
Many workspaces on one Clario service. Each workspace has its own users, encrypted Zoho connection, and chats.

**Which model is talking?**  
A single analysis agent built with Google ADK. The default model is Groq (`openai/gpt-oss-120b`). The server can be switched to Gemini.

**Where does the financial data live?**  
The books stay in Zoho. Clario stores accounts, workspace membership, encrypted Zoho credentials, and chat history. It fetches Zoho data when someone opens Analytics or asks a question.

**Is this financial advice?**  
The product states what the data shows and what may be worth reviewing. It does not recommend a financial action.
