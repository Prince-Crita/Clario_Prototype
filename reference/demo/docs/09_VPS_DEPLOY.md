# Clario VPS deployment runbook

Single-box production: **Ubuntu + PostgreSQL + systemd + Caddy (HTTPS)**.

Default hostname in examples: `clario.crita.in` — replace everywhere if you use another subdomain.

```text
Browser → Caddy (:443) → Uvicorn 127.0.0.1:8000 → Postgres
                              ↓
                         Zoho + Groq
```

**Important:** run **one** Uvicorn process/worker. Chat uses ADK `InMemorySessionService`; multiple workers would split sessions across processes.

Templates live under [`deploy/`](../deploy/).

---

## 1. DNS

Create an **A** (and optional **AAAA**) record:

| Host | Value |
| --- | --- |
| `clario.crita.in` | VPS public IPv4 |

Wait until `dig +short clario.crita.in` returns the VPS IP before requesting TLS.

---

## 2. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Do **not** expose Postgres (`5432`) or Uvicorn (`8000`) to the public internet.

---

## 3. System packages

Ubuntu 22.04 / 24.04:

```bash
sudo apt update
sudo apt install -y git curl ufw postgresql postgresql-contrib

# Python 3.12 (use deadsnakes on 22.04 if needed)
sudo apt install -y python3.12 python3.12-venv python3.12-dev build-essential

# Caddy (official repo) — see https://caddyserver.com/docs/install#debian-ubuntu-raspbian
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

---

## 4. OS user and app directory

```bash
sudo useradd --system --home /opt/clario --shell /usr/sbin/nologin clario || true
sudo mkdir -p /opt/clario /var/backups/clario /var/log/caddy
sudo chown clario:clario /opt/clario /var/backups/clario
```

Clone (or rsync) the repo as root, then hand off ownership:

```bash
sudo git clone <YOUR_CLARIO_GIT_URL> /opt/clario
# or: upload release tarball into /opt/clario
sudo chown -R clario:clario /opt/clario
```

---

## 5. PostgreSQL

```bash
sudo -u postgres psql <<'SQL'
CREATE USER clario WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
CREATE DATABASE clario OWNER clario;
GRANT ALL PRIVILEGES ON DATABASE clario TO clario;
SQL
```

On PostgreSQL 15+, also grant schema rights:

```bash
sudo -u postgres psql -d clario -c "GRANT ALL ON SCHEMA public TO clario;"
```

Confirm local auth works (password in URL later):

```bash
psql "postgresql://clario:CHANGE_ME_STRONG_PASSWORD@127.0.0.1:5432/clario" -c 'select 1'
```

---

## 6. Python venv and install

```bash
sudo -u clario -H bash -lc '
  cd /opt/clario
  python3.12 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -e .
'
```

---

## 7. Production `.env`

```bash
sudo -u clario cp /opt/clario/deploy/env.production.example /opt/clario/.env
sudo -u clario chmod 600 /opt/clario/.env
```

Generate secrets on the box:

```bash
/opt/clario/.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
openssl rand -hex 32
```

Edit `/opt/clario/.env` and set at least:

- `DATABASE_URL=postgresql+asyncpg://clario:<password>@127.0.0.1:5432/clario`
- `CLARIO_ENCRYPTION_KEY` / `CLARIO_JWT_SECRET` (from generators above)
- `ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET`
- `ZOHO_REDIRECT_URI=https://clario.crita.in/oauth/zoho/callback`
- `GROQ_API_KEY` / `GROQ_MODEL`
- `CLARIO_HOST=127.0.0.1` / `CLARIO_PORT=8000`
- `CLARIO_DATA_DIR=/opt/clario/.data`

Create data dir:

```bash
sudo -u clario mkdir -p /opt/clario/.data
```

---

## 8. Migrations

```bash
sudo -u clario -H bash -lc 'cd /opt/clario && .venv/bin/alembic upgrade head'
```

---

## 9. systemd

```bash
sudo cp /opt/clario/deploy/clario.service /etc/systemd/system/clario.service
sudo systemctl daemon-reload
sudo systemctl enable --now clario
sudo systemctl status clario --no-pager
sudo journalctl -u clario -n 50 --no-pager
```

App should listen only on localhost:

```bash
ss -lntp | grep 8000
# expect 127.0.0.1:8000
```

---

## 10. Caddy (HTTPS)

```bash
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy
sudo cp /opt/clario/deploy/Caddyfile /etc/caddy/Caddyfile
# Edit hostname in /etc/caddy/Caddyfile if not clario.crita.in
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

Caddy obtains a Let’s Encrypt certificate automatically once DNS points at the VPS.

---

## 11. Zoho API Console

In [Zoho API Console](https://api-console.zoho.in/) (use `.com` / `.eu` if that is your DC):

1. Open the **Server-based** application used by Clario.
2. Add authorized redirect URI **exactly**:
   ```text
   https://clario.crita.in/oauth/zoho/callback
   ```
3. Keep `http://localhost:8000/oauth/zoho/callback` for local development if needed.
4. Ensure scopes include at least the Clario read scopes (invoices, contacts, settings, expenses, customerpayments, accountants).

`ZOHO_REDIRECT_URI` in `/opt/clario/.env` must match the console entry character-for-character, then:

```bash
sudo systemctl restart clario
```

---

## 12. Smoke checklist

Run these after DNS + TLS are live.

### 12.1 Health

```bash
curl -fsS https://clario.crita.in/health
```

Expect JSON with `"status":"ok"`, `"multi_tenant":true`, and LLM/Zoho app flags.

### 12.2 UI load

Open `https://clario.crita.in/` — Crita-branded sign-in should load over HTTPS (no mixed-content warnings).

### 12.3 Auth

1. **Create account** (register) with a real email you control.
2. Confirm redirect into the app shell (sidebar: Analytics / Chat).
3. Log out and **sign in** again.

### 12.4 Zoho OAuth

1. Sidebar → **Zoho Books** (or Connect Zoho).
2. Confirm data center matches the org (e.g. India → `zoho.in`).
3. Leave refresh token blank; click **Connect with Zoho**.
4. Approve in Zoho; land on success / back to Clario.
5. Status pill should show org name / currency (not “Zoho not connected”).

If you see **Invalid Redirect Uri**, fix Zoho console + `.env` URI and restart `clario`.

### 12.5 Analytics

1. Sidebar → **Analytics**.
2. Click **Refresh analytics** if needed.
3. Expect sales / expenses / outstanding / overdue (or an empty-period message), not a 503.

### 12.6 Chat

1. Sidebar → **Chat**.
2. Ask something grounded, e.g. “Give me a business summary for this month.”
3. Expect a tool-backed answer (not `model_not_found` / `reasoning_content` errors).

### 12.7 Isolation sanity (optional)

Register a second user/workspace; confirm Zoho status and analytics do not leak the first org’s data.

---

## Deploying updates

```bash
sudo -u clario -H bash -lc '
  cd /opt/clario
  git pull
  .venv/bin/pip install -e .
  .venv/bin/alembic upgrade head
'
sudo systemctl restart clario
sudo systemctl status clario --no-pager
```

Re-run smoke §12.1, §12.5, and §12.6 after releases that touch OAuth, analytics, or the agent.

---

## Backups

Daily dump example:

```bash
sudo tee /etc/cron.d/clario-pgdump >/dev/null <<'EOF'
15 3 * * * postgres pg_dump -Fc clario > /var/backups/clario/clario-$(date +\%F).dump
EOF
sudo chmod 644 /etc/cron.d/clario-pgdump
```

Retain 7–14 days; test a restore on a staging DB before you need it.

**Fernet key:** losing `CLARIO_ENCRYPTION_KEY` makes stored Zoho tokens unreadable — back up `.env` securely (not in git).

---

## Security checklist

- [ ] Uvicorn bound to `127.0.0.1` only; Caddy owns `:443`
- [ ] `/opt/clario/.env` mode `600`, owned by `clario`
- [ ] Strong `CLARIO_JWT_SECRET` and `CLARIO_ENCRYPTION_KEY` (not defaults)
- [ ] Postgres not publicly reachable
- [ ] SSH key-only; Fail2ban recommended
- [ ] Zoho scopes remain read-only unless product explicitly adds writes
- [ ] `pg_dump` cron in place

---

## Known limits (v1)

- Single process/worker until ADK sessions leave in-memory storage
- Tenant isolation is application-level `tenant_id` (Postgres RLS is future work — see [`08_MULTI_TENANT.md`](08_MULTI_TENANT.md))
- Restarting `clario` clears in-memory ADK session state (conversation rows in Postgres remain)

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Caddy TLS fails | DNS A record, ports 80/443, `journalctl -u caddy` |
| `clario` crash loop | `journalctl -u clario`, Postgres URL, missing env secrets |
| Invalid Redirect Uri | Zoho console URI vs `ZOHO_REDIRECT_URI` exact match |
| Analytics 503 | Workspace Zoho not connected |
| Chat model errors | `GROQ_MODEL` still available for your key; restart after `.env` change |
