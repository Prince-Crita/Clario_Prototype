# Clario + Zoho Books

Clario is Crita's business intelligence layer. It is a **multi-tenant service**: each customer workspace has its own users, encrypted Zoho credentials, conversations, and audit trail. One Google ADK analysis agent answers questions using that tenant's live Zoho Books data.

The agent never invents financial numbers. See `docs/08_MULTI_TENANT.md` for the database design.

## Architecture

```text
User (JWT + X-Tenant-Id)
  ↓
Chat UI
  ↓
FastAPI (auth + tenancy)
  ↓
Clario Analysis Agent (Google ADK + Gemini)
  ↓
ADK tools → analytics → Zoho client (per-tenant OAuth)
  ↓
That tenant's Zoho Books organization
```

## Prerequisites

- Python 3.11+ (3.12 recommended)
- SQLite locally, or PostgreSQL for production
- Zoho OAuth app + Gemini API key

## Setup

**First time after clone:** follow [`docs/12_LOCAL_SETUP.md`](docs/12_LOCAL_SETUP.md) (venv, `.env`, Postgres, Alembic, Zoho URLs, Windows notes).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# fill ZOHO_*, GROQ_API_KEY (or GOOGLE_API_KEY), CLARIO_JWT_SECRET, CLARIO_ENCRYPTION_KEY
python -m clario serve
```

After changing `.env` (e.g. Zoho client id/secret), restart so settings reload:

```bash
./scripts/restart.sh
# or: .venv/bin/python -m clario restart
```

Postgres:

```env
DATABASE_URL=postgresql+asyncpg://clario:clario@localhost:5432/clario
```

```bash
alembic upgrade head
```

## Multi-tenant flow

1. Open http://localhost:8000 and create an account / workspace
2. Open **Zoho Books** and paste that org’s Zoho API Console **Client ID + Client Secret**
3. Register Clario’s redirect URI on their Zoho app (shown in the modal / `ZOHO_REDIRECT_URI`)
4. Connect with Zoho (tokens encrypted per workspace)
5. Use Analytics + Chat

Platform `ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET` in `.env` are only a **fallback**. Prefer per-workspace credentials so each customer uses their own Zoho app.

APIs: `/api/auth/register`, `/api/auth/login`, `/api/tenants`, `/api/tenants/current/zoho/settings`, `/api/oauth/zoho/start`, `/api/chat` (Bearer + `X-Tenant-Id`).

## Tests

```bash
pytest -m "not integration and not agent"
```

## Production notes

Full VPS runbook (Ubuntu + PostgreSQL + systemd + Caddy): [`docs/09_VPS_DEPLOY.md`](docs/09_VPS_DEPLOY.md).

Templates: [`deploy/clario.service`](deploy/clario.service), [`deploy/Caddyfile`](deploy/Caddyfile), [`deploy/env.production.example`](deploy/env.production.example).

- Use PostgreSQL + Alembic
- Strong `CLARIO_JWT_SECRET` and `CLARIO_ENCRYPTION_KEY`
- Bind the app to `127.0.0.1`; terminate TLS at Caddy
- Run a **single** Uvicorn worker (ADK in-memory chat sessions)
- Set `ZOHO_REDIRECT_URI` to `https://<your-host>/oauth/zoho/callback` and register the same URI in Zoho API Console
- Isolation is via `tenant_id` today; add Postgres RLS later
- Keep Zoho read-only unless product explicitly adds confirmed writes
