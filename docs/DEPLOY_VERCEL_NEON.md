# Deploying Clario: Neon (database) + Vercel (hosting)

Status: one Vercel project serves the frontend and the API from the repository root; the data is
in Neon. The first Vercel build failed because Vercel auto-detected the whole monorepo as a Python
app; the configuration below replaces that.

## 1. Shape of the deployment

```
Browser ── https://<your-domain> ──▶ ONE Vercel project, Root Directory "."
                                      ├─ static site  frontend/dist   (npm run build --prefix frontend)
                                      └─ /api/*  ──▶  api/index.py (FastAPI, Python 3.12, region sin1)
                                                          │
                                                          ▼
                                                  Neon PostgreSQL (pooled endpoint)
```

* [vercel.json](../vercel.json) sets `"framework": null`. This is the important line: without it
  Vercel's Python preset wins and treats the repository as a single Python app (error "No python
  entrypoint found…"). With it, `api/index.py` is the only function and the frontend is static.
* [api/index.py](../api/index.py) is the single entrypoint. It puts `backend/src` on the path,
  defaults `SYNC_INLINE=true`, and exposes `app`. `reference/demo/` and tests are excluded from the
  function bundle (`excludeFiles`) and never deployed.
* [requirements.txt](../requirements.txt) (runtime only) is **generated** from `backend/uv.lock`:
  `cd backend && uv export --frozen --no-dev --no-hashes --no-emit-project --no-annotate --no-header`.
  Regenerate it whenever the backend's dependencies change. [.python-version](../.python-version) pins 3.12.
* The function runs in `sin1` (Singapore), next to the Neon database (ap-southeast-1). Each dashboard
  request makes several sequential queries, so distance to the database dominates latency. Change
  `regions` if the Neon project moves.
* Same-origin: the browser only talks to one domain, so cookies and the CSRF origin check behave as in
  development. No CORS configuration.

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

1. Project settings → Root Directory `.`; **Framework Preset: Other** (the `framework: null` in
   vercel.json also forces this). Leave Build/Install/Output commands empty: vercel.json supplies them.
2. Add the variables in §4 (Production, and Preview if used). Mark secrets Sensitive.
3. Push to `main`; Vercel builds and deploys. `maxDuration` is 300 s (a Zoho import and AI turns run
   inside a request).
4. The production domain must equal `APP_BASE_URL`.

### Zoho API Console (manual)

Register `https://<your-domain>/api/v1/oauth/zoho-books/callback` as an authorised redirect URI
and set the same value in `ZOHO_REDIRECT_URI`.

## 4. Environment variables

All of these are **server-side** (function) variables. None has a `VITE_` prefix and nothing here is
ever sent to the browser.

| Variable | Required | Value / note |
|---|---|---|
| `DATABASE_URL` | yes | Neon **pooled** connection string |
| `APP_ENV` | yes | `production` (turns on the production safety checks) |
| `APP_BASE_URL` | yes | `https://<your-domain>` (the frontend); drives the CSRF origin check |
| `SESSION_COOKIE_SECURE` | yes | `true` |
| `SESSION_SECRET` | yes | new random string, 32+ characters (do not reuse the development one) |
| `ENCRYPTION_KEYS` | yes | must **include the key currently in `.env`**, or the copied Zoho credentials cannot be decrypted. To rotate: `<new key>,<old key>` (first encrypts, all decrypt) |
| `SYNC_INLINE` | no | defaults to `true` on Vercel via api/index.py (see §5) |
| `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET` | yes | as in `.env` |
| `ZOHO_REDIRECT_URI` | yes | see Zoho API Console above |
| `ZOHO_SCOPES`, `ZOHO_DEFAULT_REGION` | yes | as in `.env` |
| `LLM_PROVIDER` + `GROQ_API_KEY`, `GROQ_MODEL` **or** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | for Clario AI | as in `.env` |
| `DATABASE_URL_UNPOOLED` | no | direct endpoint; only if auto-derivation is wrong |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `LOG_LEVEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOOL_ROUNDS`, `ZOHO_REQUESTS_PER_MINUTE`, `ZOHO_MAX_PAGES`, `FINANCE_STALE_AFTER_MINUTES`, `FINANCE_REFRESH_COOLDOWN_SECONDS` | no | defaults are fine |

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

* **Cold starts.** The first request after idle takes several seconds (Python import + database
  connection); later ones are warm.
* **Long imports.** A first-time import of a large Zoho organisation must finish within
  `maxDuration` (300 s); otherwise the request times out, the run is later marked abandoned, and
  Sync can be pressed again.
* **Client IP.** The sign-in rate limiter and audit log use `request.client.host`, which relies on
  proxy headers; whether Vercel populates it correctly is unverified. The limiter is in-memory per
  instance (weaker on serverless); the per-account lockout is the main control.
* **AI data terms.** In production the assistant sends real Zoho figures to the chosen AI provider.
  Do not enable `LLM_PROVIDER` for real client data until the provider's data terms are confirmed
  (risk R6). The connection copied from development is the Zoho **trial** organisation.
* **PostgreSQL versions differ** (local 16, Neon 18). The migrations and the covered tests pass on
  both; consider a Neon project on 16/17 if exact parity matters.
* **Credentials.** The Neon connection string was shared in plain text during setup. Rotate the
  `neondb_owner` password (Neon console → Roles), update `.env.local` and the Vercel variable, and
  restart the local server. A least-privilege application role would be better than the owner role.
