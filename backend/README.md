# Clario backend

FastAPI service for Clario. Architecture: [`docs/FINAL_ARCHITECTURE_PLAN.md`](../docs/FINAL_ARCHITECTURE_PLAN.md) (§7, §8, §10, §40).

```
src/clario/
  core/          framework-free building blocks (db base, errors, logs, crypto, money, dates, ids)
  settings.py    typed settings (.env → .env.local → environment)
  platform/      Clario Core modules (identity, workspaces, access, integrations, connections, sync, …)
  ai/            provider interface, agent runtime, tool framework, policy, guards
  domains/       business domains (finance)
  integrations/  connectors (zoho_books)
  api/           composition root: /api/v1 router, deps, middleware, problem+json errors
  main.py        application factory
  cli/           `clario` command
migrations/      Alembic (version table: core.alembic_version)
tests/           unit · api · db (db tests need TEST_DATABASE_URL ending in _test)
```

Layering is enforced by import-linter (`lint-imports`): cli → main → api → integrations → domains → ai → platform → settings → core.

## Commands (from `backend/`)

```bash
uv sync                          # create .venv from uv.lock
uv run clario db upgrade         # apply migrations to DATABASE_URL (idempotent)
uv run clario serve --reload     # http://127.0.0.1:8000/api/v1/docs
uv run pytest                    # all tests (db tests skip without TEST_DATABASE_URL)
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run clario openapi export     # regenerate contracts/openapi.json after API changes
```
