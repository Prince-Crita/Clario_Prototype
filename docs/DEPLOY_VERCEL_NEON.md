# Deploying Clario: Neon (database) + Vercel (hosting)

Status: the database is migrated to Neon and the app runs against it locally. The Vercel
configuration is in the repository but **has not been deployed or exercised on Vercel yet**; treat
the first deploy as the real test.

## 1. Shape of the deployment

```
Browser ── https://<your-domain> ──▶ Vercel project "clario-web"  (frontend/, Vite static)
                                          │  /api/*  is rewritten (proxied) to…
                                          ▼
                                     Vercel project "clario-api" (backend/, FastAPI function)
                                          │
                                          ▼
                                     Neon PostgreSQL (pooled endpoint)
```

* **Two Vercel projects from this one repository**, using only generally available features
  (Vercel's single-project "Services" mode is Beta and permission-gated, so it is not used).
* The browser only ever talks to the frontend's domain, so session cookies and the CSRF origin
  check stay same-origin, exactly as in development (where Vite proxies `/api`).
* No CORS configuration is needed or present.

## 2. Database (Neon)

| | Local development | Production |
|---|---|---|
| Database | local PostgreSQL 16, `clario_dev` | Neon, database `neondb` (PostgreSQL 18) |
| Where the URL lives | `.env` | `.env.local` (git-ignored) for development against Neon; **Vercel environment variable** in production |
| Test database | local `clario_test` only | never |

* `DATABASE_URL` accepts the connection string exactly as Neon issues it
  (`postgresql://…?sslmode=require&channel_binding=require`); the app adapts it for asyncpg
  (`clario/core/dburl.py`). Use the **pooled** string (host contains `-pooler`) for the app.
* Migrations always run against the **direct** endpoint (the same host without `-pooler`), derived
  automatically; override with `DATABASE_URL_UNPOOLED` if needed. Apply them with
  `cd backend && uv run clario db upgrade` (idempotent). Do **not** run migrations from Vercel.
* On a pooled endpoint the driver's prepared-statement caches are switched off automatically
  (PgBouncer transaction mode). Verified: 12 concurrent dashboard builds, and a 95-second advisory
  lock (used by the sync engine) held through the pooler.
* **Back to the local database:** delete the `DATABASE_URL` line from `.env.local` and restart the
  server. The local `clario_dev` was only read during the migration; it is frozen at the snapshot
  taken then and does **not** receive anything written to Neon afterwards.
* Neon's own `neon_auth` schema (Neon Auth) is unrelated to Clario and is not used or modified.

## 3. Vercel setup

### Backend project (`clario-api`)

1. New Project → import this repository → **Root Directory: `backend`**. Framework preset: FastAPI
   (detected from `index.py`, which exposes `app`). Python 3.12 (from `requires-python`).
2. Add the environment variables in §4 (Production, and Preview if you use it).
3. Deploy. Note the project's URL (e.g. `https://clario-api-xxxx.vercel.app`).
4. `backend/vercel.json` sets `maxDuration` to 300 s (a Zoho import and AI turns run inside a
   request). Your plan must allow it (Hobby and Pro both allow 300 s with Fluid compute).

### Frontend project (`clario-web`)

1. **Before deploying**, edit `frontend/vercel.json`: replace
   `REPLACE-WITH-YOUR-BACKEND-PROJECT.vercel.app` with the backend project's host from above, and
   commit that change.
2. New Project → same repository → **Root Directory: `frontend`**. Framework preset: Vite
   (build `npm run build`, output `dist`). It needs **no environment variables**.
3. Set the production domain; it must equal `APP_BASE_URL` below.

### Zoho API Console (manual)

Register `https://<your-domain>/api/v1/oauth/zoho-books/callback` as an authorised redirect URI
and set the same value in `ZOHO_REDIRECT_URI`.

## 4. Environment variables

All of these are **server-side secrets or settings on the backend project**. The frontend project
has none, and nothing here is ever sent to the browser.

| Variable | Required | Value / note |
|---|---|---|
| `DATABASE_URL` | yes | Neon **pooled** connection string |
| `APP_ENV` | yes | `production` (turns on the production safety checks) |
| `APP_BASE_URL` | yes | `https://<your-domain>` (the frontend); drives the CSRF origin check |
| `SESSION_COOKIE_SECURE` | yes | `true` |
| `SESSION_SECRET` | yes | new random string, 32+ characters (do not reuse the development one) |
| `ENCRYPTION_KEYS` | yes | must **include the key currently in `.env`**, or the copied Zoho credentials cannot be decrypted. To rotate: `<new key>,<old key>` (first encrypts, all decrypt) |
| `SYNC_INLINE` | yes | `true` (see §5) |
| `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET` | yes | as in `.env` |
| `ZOHO_REDIRECT_URI` | yes | see Zoho API Console above |
| `ZOHO_SCOPES`, `ZOHO_DEFAULT_REGION` | yes | as in `.env` |
| `LLM_PROVIDER` + `GROQ_API_KEY`, `GROQ_MODEL` **or** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | for Clario AI | as in `.env` |
| `DATABASE_URL_UNPOOLED` | no | direct endpoint; only if auto-derivation is wrong |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `LOG_LEVEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOOL_ROUNDS`, `ZOHO_REQUESTS_PER_MINUTE`, `ZOHO_MAX_PAGES`, `FINANCE_STALE_AFTER_MINUTES`, `FINANCE_REFRESH_COOLDOWN_SECONDS` | no | defaults are fine |
| `UV_NO_DEV` | no | `1` keeps test/lint tools out of the function bundle |

Never set `FINANCE_FIXTURE_SOURCE=true` (production refuses to start with it) or
`TEST_DATABASE_URL`. The app also refuses to start in production without `SESSION_COOKIE_SECURE`
and an `https` `APP_BASE_URL`.

## 5. How serverless changes behaviour (`SYNC_INLINE=true`)

A serverless function may be frozen once its response is sent, so work that normally continues
*after* the response cannot be relied on. With `SYNC_INLINE=true`:

* the **Sync** button and the first import after connecting Zoho run **inside** the request and
  return when finished (the button shows "Updating…" meanwhile);
* **opening a dashboard page no longer starts an automatic background refresh** of stale data.
  Data refreshes when someone presses Sync (or the CLI, `clario sync`, is run on a schedule).
  Everything else (dashboards, Clario AI, history) is unchanged.

Local development and any always-on server keep `SYNC_INLINE=false` and the original behaviour.

## 6. Known risks and open items

* **Not yet deployed.** Configuration is derived from Vercel's documentation and a local simulation
  of the entrypoint under production settings; the first real deploy may need small adjustments.
* **Long imports.** A first-time import of a large Zoho organisation must finish within
  `maxDuration` (300 s); otherwise the request times out, the run is later marked abandoned, and
  Sync can be pressed again.
* **Client IP.** The sign-in rate limiter and audit log use `request.client.host`, which relies on
  proxy headers; whether Vercel populates it correctly is unverified. The limiter is in-memory per
  instance (weaker on serverless); the per-account lockout is the main control.
* **Public backend URL.** The backend project is also reachable at its own `*.vercel.app` URL;
  writes are still protected by the origin and CSRF checks. Consider Deployment Protection.
* **AI data terms.** In production the assistant sends real Zoho figures to the chosen AI provider.
  Do not enable `LLM_PROVIDER` for real client data until the provider's data terms are confirmed
  (risk R6). The connection copied from development is the Zoho **trial** organisation.
* **PostgreSQL versions differ** (local 16, Neon 18). The migrations and the covered tests pass on
  both; consider a Neon project on 16/17 if exact parity matters.
* **Credentials.** The Neon connection string was shared in plain text during setup. Rotate the
  `neondb_owner` password (Neon console → Roles), update `.env.local` and the Vercel variable, and
  restart the local server. A least-privilege application role would be better than the owner role.
