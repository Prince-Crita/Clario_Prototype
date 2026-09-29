# Local setup (do this first after cloning)

Step-by-step for a fresh clone. Goal: Postgres + Alembic + `.env` + app on `http://localhost:8000`.

## Prerequisites

- Python **3.11+** (3.12 recommended; 3.13 works)
- PostgreSQL running locally (this guide uses the default `postgres` / `postgres` user)
- A [Groq](https://console.groq.com/keys) API key (or Gemini key if you switch provider)
- Zoho Books OAuth app (Client ID + Secret) — see [Zoho URLs](#zoho-api-console-urls) below

## 1. Clone and enter the repo

```bash
git clone <repo-url> Clario
cd Clario
```

## 2. Create a virtualenv and install

**macOS / Linux**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

You should end up with a `.venv` folder at the repo root. Always activate it (or call `.venv\Scripts\python.exe` / `.venv/bin/python`) before running Clario commands.

## 3. Copy env and fill required values

```bash
cp .env.example .env
```

**Windows**

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at least:

```env
# Postgres (username/password = postgres / postgres in this local guide)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/clario

# Generate once:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CLARIO_ENCRYPTION_KEY=<fernet-key>

CLARIO_JWT_SECRET=<long-random-string>

# LLM (default provider is Groq)
GROQ_API_KEY=<your-key>

# Optional platform Zoho fallback (prefer per-workspace credentials in the UI)
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_REDIRECT_URI=http://localhost:8000/oauth/zoho/callback
```

Leave `DATABASE_URL` empty only if you want local SQLite under `.data/clario.db` instead of Postgres.

## 4. Create the Postgres database

SQLAlchemy/Alembic create **tables**, not the database itself. Create `clario` once:

```bash
psql -U postgres -h localhost -c "CREATE DATABASE clario;"
```

**Windows** (if `psql` is on PATH, or use the full path under `C:\Program Files\PostgreSQL\<version>\bin\`):

```powershell
$env:PGPASSWORD = "postgres"
psql -U postgres -h localhost -c "CREATE DATABASE clario;"
```

Skip this if `clario` already exists.

## 5. Run Alembic migrations

With the venv active and `.env` pointing at Postgres:

```bash
alembic upgrade head
```

This creates the multi-tenant tables (`users`, `tenants`, `conversations`, `zoho_connections`, …).

On app start, `init_db()` also calls `create_all` for local/dev convenience, but **always run Alembic** when using Postgres so migration history stays correct.

## 6. Start the app

```bash
python -m clario serve
```

Open: **http://localhost:8000** (or **http://127.0.0.1:8000**)

## 7. After changing `.env` — restart

Settings are loaded at process start. Restart after any `.env` edit.

**macOS / Linux**

```bash
./scripts/restart.sh
# or
python -m clario restart
```

**Windows** — `restart.sh` / `clario restart` use `lsof` and do **not** work. Use:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
.\.venv\Scripts\python.exe -m clario serve
```

## Zoho API Console URLs

Create a **Server-based Application** in the Zoho API Console for your data center (this project defaults to India: `accounts.zoho.in`).

| Field | Local value |
|--------|-------------|
| Homepage URL | `http://localhost:8000` |
| Authorized Redirect URI | `http://localhost:8000/oauth/zoho/callback` |

Then either:

1. Paste Client ID + Secret in the Clario UI under the workspace **Zoho Books** settings (preferred), or
2. Put them in `.env` as `ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET` and restart

Connect OAuth from the UI, or print an auth URL with:

```bash
python -m clario oauth-url
# or
python scripts/zoho_oauth_url.py
```

## Quick checklist

- [ ] `.venv` created and activated
- [ ] `pip install -e ".[dev]"`
- [ ] `.env` copied from `.env.example`
- [ ] `DATABASE_URL` set to Postgres (`postgres` / `postgres` → database `clario`)
- [ ] `CLARIO_ENCRYPTION_KEY` and `CLARIO_JWT_SECRET` set
- [ ] `GROQ_API_KEY` (or Gemini) set
- [ ] Database `clario` created
- [ ] `alembic upgrade head`
- [ ] `python -m clario serve`
- [ ] Zoho app registered with the redirect URI above

## First use in the UI

1. Register / log in at http://localhost:8000
2. Create or open a workspace
3. Add Zoho Client ID + Secret for that workspace
4. Connect Zoho → use Analytics + Chat

## Related docs

- [README.md](../README.md) — overview
- [08_MULTI_TENANT.md](08_MULTI_TENANT.md) — DB design
- [09_VPS_DEPLOY.md](09_VPS_DEPLOY.md) — production (Ubuntu + Postgres + systemd)
- [02_ZOHO_BOOKS_INTEGRATION.md](02_ZOHO_BOOKS_INTEGRATION.md) — Zoho details
