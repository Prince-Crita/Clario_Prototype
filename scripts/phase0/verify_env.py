# /// script
# requires-python = ">=3.12"
# dependencies = ["asyncpg>=0.30", "httpx>=0.27"]
# ///
"""Phase 0 environment check. Prints NO secrets.

Run from the repo root:  python -m uv run scripts/phase0/verify_env.py
"""

from __future__ import annotations

import asyncio
import sys
from urllib.parse import urlsplit

import asyncpg
import httpx

from _env import load_env

OK, WARN, FAIL = "ok  ", "warn", "FAIL"
results: list[tuple[str, str, str]] = []


def record(status: str, check: str, detail: str = "") -> None:
    results.append((status, check, detail))


def asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def check_database(name: str, url: str, must_end_with: str | None = None) -> None:
    if not url:
        record(FAIL, name, "not set")
        return
    db = urlsplit(url).path.lstrip("/")
    if must_end_with and not db.endswith(must_end_with):
        record(FAIL, name, f"database '{db}' must end with '{must_end_with}'")
        return
    try:
        conn = await asyncpg.connect(asyncpg_dsn(url), timeout=5)
        try:
            version = await conn.fetchval("show server_version")
            current = await conn.fetchval("select current_database()")
            tables = await conn.fetchval(
                "select count(*) from information_schema.tables "
                "where table_schema not in ('pg_catalog','information_schema')"
            )
        finally:
            await conn.close()
        record(OK, name, f"{current} | PostgreSQL {version} | {tables} user tables")
    except Exception as exc:  # noqa: BLE001
        record(FAIL, name, type(exc).__name__)


async def check_groq(env: dict[str, str]) -> None:
    key = env.get("GROQ_API_KEY", "")
    if not key:
        record(WARN, "Groq API key", "GROQ_API_KEY empty - needed for the model evaluation")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        if resp.status_code != 200:
            record(FAIL, "Groq API key", f"HTTP {resp.status_code}")
            return
        models = sorted(m["id"] for m in resp.json().get("data", []))
        configured = env.get("GROQ_MODEL", "")
        status = OK if configured in models else WARN
        record(status, "Groq API key", f"{len(models)} models visible; GROQ_MODEL "
               f"'{configured}' {'available' if configured in models else 'NOT available'}")
    except httpx.HTTPError as exc:
        record(FAIL, "Groq API key", type(exc).__name__)


def check_zoho(env: dict[str, str]) -> None:
    missing = [n for n in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET") if not env.get(n)]
    if missing:
        record(WARN, "Zoho app credentials", f"empty: {', '.join(missing)} - needed for the Zoho spike")
    else:
        record(OK, "Zoho app credentials", "client id + secret present")
    redirect = env.get("ZOHO_REDIRECT_URI", "")
    parts = urlsplit(redirect)
    if parts.hostname in {"localhost", "127.0.0.1"} and parts.port:
        record(OK, "Zoho redirect URI", redirect)
    else:
        record(WARN, "Zoho redirect URI", f"'{redirect}' - spike needs a localhost URI with a port")


def check_secrets(env: dict[str, str]) -> None:
    for name, min_len in (("SESSION_SECRET", 40), ("ENCRYPTION_KEYS", 40)):
        value = env.get(name, "")
        record(OK if len(value) >= min_len else FAIL, name, "set" if value else "empty")


async def main() -> int:
    env = load_env()
    record(OK if sys.version_info >= (3, 12) else FAIL, "Python", sys.version.split()[0])
    check_secrets(env)
    await check_database("DATABASE_URL", env.get("DATABASE_URL", ""))
    await check_database("TEST_DATABASE_URL", env.get("TEST_DATABASE_URL", ""), must_end_with="_test")
    check_zoho(env)
    await check_groq(env)

    width = max(len(check) for _, check, _ in results)
    for status, check, detail in results:
        print(f"[{status}] {check.ljust(width)}  {detail}")
    return 1 if any(status == FAIL for status, _, _ in results) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
