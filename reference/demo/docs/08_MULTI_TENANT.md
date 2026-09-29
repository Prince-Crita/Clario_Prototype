# Multi-tenant database

Clario uses a **shared-schema multi-tenant** model. Every customer workspace is a `tenant`. Business data and Zoho credentials are isolated by `tenant_id`.

## Tables

| Table | Purpose |
| --- | --- |
| `users` | Login accounts |
| `tenants` | Workspaces / customer orgs |
| `memberships` | user ↔ tenant + role |
| `zoho_connections` | Encrypted Zoho OAuth tokens (1:1 with tenant) |
| `oauth_states` | Short-lived CSRF state for Zoho authorize |
| `conversations` | Chat threads per tenant/user |
| `messages` | Persisted chat turns |
| `audit_events` | Security/product audit trail |
| `api_keys` | Optional machine credentials |

## Isolation rules

1. Every tenant-owned row includes `tenant_id`.
2. Membership is checked before any tenant-scoped API.
3. Zoho tokens **and optional per-workspace OAuth client secret** are Fernet-encrypted; never return the full secret to the frontend (masked only). Client ID is returned for admins to verify.
4. Chat binds a Zoho client for the current tenant only for that request.
5. Prefer each workspace’s own Zoho API Console Client ID/Secret. Platform `ZOHO_CLIENT_*` env is a fallback only.

## Engines

- **Local/dev:** SQLite (`DATABASE_URL` empty → `.data/clario.db`)
- **Production:** PostgreSQL via `postgresql+asyncpg://...`

```bash
alembic upgrade head
```

Startup also calls `init_db()` so local SQLite works without a manual migrate.

## Roles

`owner` · `admin` · `member` · `viewer`

Connecting/disconnecting Zoho requires `owner` or `admin`.

## Request contract

```http
Authorization: Bearer <jwt>
X-Tenant-Id: <tenant uuid>
```

## Future hardening

- PostgreSQL RLS policies on `tenant_id`
- Shared ADK session backend for multi-replica deploys
- Invite links for users who do not have accounts yet
