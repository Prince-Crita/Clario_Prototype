# Local development setup

Everything runs on your machine against a local PostgreSQL 16. No step here drops or resets a database.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 | Managed by `uv`: `python -m pip install --user uv`, then `python -m uv python install 3.12` |
| Node.js | 22 LTS | npm comes with it |
| PostgreSQL | 16 | Local service; pgAdmin is fine for administration |

`uv` is invoked as `python -m uv` if it isn't on your PATH. Running `python -m uv python update-shell` once fixes that.

## 1. Environment file

```bash
cp .env.example .env
```

| Variable | How to set it |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<password>@localhost:5432/clario_dev` |
| `TEST_DATABASE_URL` | Same server, database **`clario_test`**. The test suite refuses any name not ending in `_test`. |
| `SESSION_SECRET` | `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `ENCRYPTION_KEYS` | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
| `ZOHO_*`, `GROQ_API_KEY` | Only needed from Phase 5 / Phase 9 onwards |

Personal overrides go in `.env.local`, which is also git-ignored. Never put real values in `.env.example`.

## 2. Databases (once)

Create them in pgAdmin or with psql. Use `clario_dev`, **not** `clario`, which may hold the old demo's tables.

```sql
CREATE DATABASE clario_dev ENCODING 'UTF8';
CREATE DATABASE clario_test ENCODING 'UTF8';
```

## 3. Backend

```bash
cd backend
uv sync                          # creates backend/.venv from uv.lock
uv run clario db upgrade         # idempotent; safe to run any time
uv run clario serve              # http://127.0.0.1:8000/api/v1/docs (reloads on code changes in development)
```

## 3a. Your development login (once)

There is no public sign-up. Create your own owner account and a dev workspace:

```bash
uv run clario dev seed --owner-email you@crita.in --owner-name "Your Name"
# prompts for a password (min 12 characters); safe to re-run
```

Operators provision real clients with `uv run clario admin …` (see `uv run clario admin --help`).
Coming-soon integration cards are hidden per workspace until enabled, e.g.
`uv run clario admin set-integration-visibility --workspace acme --integration city-threads-inventory --visible`.
`clario dev seed` shows every card in the dev workspace.

## 4. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173; /api is proxied to :8000
```

To point the SPA at a backend on another port: `CLARIO_API_URL=http://127.0.0.1:8010 npm run dev`.
After changing the backend API: `uv run clario openapi export` (backend), then `npm run gen:api` (frontend).

## 5. Connecting Zoho Books (development)

1. `.env` needs `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_SCOPES` and
   `ZOHO_REDIRECT_URI=http://localhost:5173/api/v1/oauth/zoho-books/callback`, which must match the
   redirect URI registered for Crita's server-based app in the Zoho API Console.
2. Run the backend on 8000 and the frontend on 5173 (sections 3 and 4). Open the app at
   **http://localhost:5173**, not 127.0.0.1: the session cookie and the redirect URI must share
   one origin.
3. Sign in as an owner or admin → **Zoho Books** → keep **India (zoho.in)** → **Connect Zoho Books**
   → approve in Zoho → choose the organisation → done.
4. **During development choose only the TEST trial organisation `60089553909`.** Do not connect the
   live organisation until it is approved.

If something fails, the page names the reason (for example "Some permissions weren't granted"),
and the backend log has the detail. Disconnect revokes Clario's access at Zoho and deletes the
stored tokens.

## 6. Imported data (sync)

Choosing the organisation starts the first import; the Zoho Books page then shows **Data in
Clario** with each dataset's records and freshness, and **Refresh now**.

- `uv run clario sync run --workspace <slug>` syncs one workspace now and prints each dataset's
  status, rows and period, which is handy for checking counts against Zoho.
- **Without a Zoho account:** set `FINANCE_FIXTURE_SOURCE=true` in `.env`, run
  `uv run clario dev fixture-connection --workspace <slug>`, then sync. Syncs read the golden
  dataset (the director's PDF figures, clients anonymised) instead of Zoho (development only;
  refused in production).
- Opening **Zoho Books** from the home page then shows the Finance Command Centre (with fixture mode on,
  the director's PDF figures, clients anonymised). The connection and import status are under
  *Connection* in its header.
- Checking figures against Zoho: see [finance-reconciliation.md](finance-reconciliation.md). Disconnect the fixture
  connection before connecting a real Zoho organisation in the same workspace.

## 7. The Finance Assistant

The assistant uses one AI provider, chosen in `.env` (restart the API after changing it):

| Provider | `.env` |
|---|---|
| Groq | `LLM_PROVIDER=groq`, `GROQ_API_KEY`, `GROQ_MODEL` (default `openai/gpt-oss-120b`) |
| OpenRouter | `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `nvidia/nemotron-3-super-120b-a12b:free`) |

Without a key for the chosen provider it says it isn't set up and the rest of Clario works
normally. Groq's limits are per Groq organisation: a new key in the same account does not reset
them. OpenRouter's free models allow about 25 questions a day without credits. Adding a provider:
see plan §20. Open it with
**Ask Finance** in the Command Centre header (owners, admins and members; not viewers). It opens
beside the dashboard on wide screens, over it on narrower ones, and full screen on phones; the
expand button gives it the whole page with your conversation list.

**Every question sends that connection's figures to Groq.** Until Crita has confirmed Groq's data
terms, try it only on synthetic data: set `FINANCE_FIXTURE_SOURCE=true` and
`FINANCE_FIXTURE_DATASET=evaluation` in `.env`, then `uv run clario dev fixture-connection
--workspace <slug>` and sync. (The default fixture, `golden`, holds the director's real amounts; keep
it for dashboard checks and don't ask the assistant about it.)

**AI usage limit.** When Groq refuses a question (429), the panel shows *AI usage limit reached ·
Available again in 4m 12s*, keeps your question in the box, and sends nothing until then. The time
is the latest reset among Groq's exhausted limits: the 429's `retry-after`, and the per-day
requests and per-minute tokens in its headers (the per-day token limit appears only in the 429
message). When the countdown ends the panel says the limit *should* have reset: Groq's time covers
one call, and a question makes several against a rolling daily budget, so only the next real
answer shows **Available**. The state is per server process. The free tier's 200k tokens a day are
shared by the whole Groq organisation: use `EVAL_CASES` subsets and the scripted review provider,
and keep real questions to targeted smoke tests.

**The panel says the assistant "can't be reached"** while the dashboard works: the API server is
probably older than the frontend. `clario serve` now reloads on code changes in development; a
server started before this (or with `--no-reload`) must be restarted.

### The evaluation gate (before a release, or after changing prompts, tools or the model)

```bash
# backend/ — real Groq, the synthetic evaluation dataset, about 10 minutes
uv run pytest -m llm_eval
# a few cases while iterating
EVAL_CASES=revenue_fy,joke uv run pytest -m llm_eval -s
```

It asks 43 questions through the real API and writes
[docs/evaluations/finance-assistant.md](../evaluations/finance-assistant.md). The gate is 100%
figure accuracy and at least 95% correct refusals. The normal `pytest` run skips it.

## Checks (the same ones CI runs)

```bash
# backend/
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest
uv run clario openapi export --check     # run `clario openapi export` after changing the API
# frontend/
npm run lint && npm run typecheck && npm run format:check && npm test && npm run build
```

Optional: `python -m uv tool install pre-commit && pre-commit install` runs the fast checks on each commit.

## Working rules (from the architecture plan)

- **Layering:** cli → main → api → integrations → domains → ai → platform → settings → core. `lint-imports` fails the build on violations.
- **Where code goes:**
  - Routes (`api.py`) only parse and delegate.
  - Services hold the use cases.
  - Repositories hold all SQL, and every repository function takes a scope.
- **Schema changes** go only through Alembic (`uv run clario db revision -m "…" --autogenerate`, then review). Never edit an applied migration.
- **Money** is `Decimal` in Python and decimal strings over the API. The UI only formats; it never calculates.
- **API changes:** regenerate `contracts/openapi.json` in the same PR.

## Troubleshooting

- **`python` fails with "did not find executable …Python3xx\python.exe"**: another project's
  virtualenv is first on your PATH and its base Python was removed. Deactivate it, or call Clario's
  tools directly: `backend\.venv\Scripts\clario.exe`, `…\pytest.exe`, `…\ruff.exe`, `…\mypy.exe`.
- **`uv sync` fails with "failed to remove file …clario.exe"**: a running `clario serve` holds the
  file. Stop the server, then sync again.
