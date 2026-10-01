"""Database URL handling for managed PostgreSQL (Neon) and the asyncpg driver.

Operators paste the connection string their provider issues, e.g.
``postgresql://user:pw@ep-x-pooler.region.aws.neon.tech/db?sslmode=require&channel_binding=require``.
asyncpg understands neither libpq's ``sslmode`` nor ``channel_binding``, so a URL is normalised
once, here: the scheme becomes ``postgresql+asyncpg``, ``sslmode`` becomes asyncpg's ``ssl`` (TLS is
still required), and the libpq-only ``channel_binding`` is dropped.

Two kinds of endpoint exist on Neon, told apart by the ``-pooler`` suffix on the host:
  * pooled (PgBouncer, transaction mode): right for the web app and serverless functions, which
    open many short connections. Server-side prepared statements do not survive transaction
    pooling, so the driver's statement caches are switched off for these (`engine_options`).
  * direct: right for migrations and anything that holds session state (advisory locks, DDL).

Nothing here logs or returns a password except the normalised URL itself; use `describe` for any
text that may be printed.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.engine import URL, make_url

DRIVER = "postgresql+asyncpg"
_ACCEPTED_DRIVERS = {"postgres", "postgresql", "postgresql+asyncpg"}
_SSL_MODES = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
_LIBPQ_ONLY = {"channel_binding"}  # not understood by asyncpg; TLS itself is unaffected
_POOLER_MARK = "-pooler"


def _parse(url: str) -> URL:
    try:
        parsed = make_url(url.strip())
    except Exception:
        # Never echo the value: it contains the password.
        raise ValueError("is not a valid database URL") from None
    if parsed.drivername not in _ACCEPTED_DRIVERS or not parsed.host:
        raise ValueError("must be a PostgreSQL URL (postgresql://user:password@host/database)")
    return parsed


def normalize_database_url(url: str) -> str:
    """The asyncpg form of any accepted PostgreSQL URL. Idempotent."""
    parsed = _parse(url)
    query: dict[str, Any] = {k: v for k, v in parsed.query.items() if k not in _LIBPQ_ONLY}
    sslmode = query.pop("sslmode", None)
    if sslmode is not None and "ssl" not in query:
        if isinstance(sslmode, tuple) or sslmode not in _SSL_MODES:
            raise ValueError("has an unsupported sslmode")
        query["ssl"] = sslmode
    return parsed.set(drivername=DRIVER, query=query).render_as_string(hide_password=False)


def is_pooled(url: str) -> bool:
    """True for a PgBouncer-pooled endpoint (Neon's ``-pooler`` host)."""
    host = _parse(url).host or ""
    return _POOLER_MARK in host.split(".")[0]


def direct_database_url(url: str) -> str:
    """The same database through its direct (unpooled) endpoint; unchanged if already direct."""
    parsed = _parse(url)
    host = parsed.host or ""
    first, _, rest = host.partition(".")
    if _POOLER_MARK not in first:
        return normalize_database_url(url)
    direct = first.replace(_POOLER_MARK, "", 1) + ("." + rest if rest else "")
    return normalize_database_url(parsed.set(host=direct).render_as_string(hide_password=False))


def engine_options(url: str) -> dict[str, Any]:
    """Extra `create_async_engine` arguments the endpoint needs (none for a direct connection)."""
    if not is_pooled(url):
        return {}
    return {
        "connect_args": {
            # PgBouncer in transaction mode hands each transaction a different server connection,
            # so a prepared statement made on one is missing on the next. SQLAlchemy's documented
            # recipe: no statement caches, and a unique name for any statement that is prepared.
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        }
    }


def describe(url: str) -> str:
    """A printable summary with no credentials: ``host/database (pooled|direct)``."""
    parsed = _parse(url)
    host = parsed.host or ""
    # Mask the Neon endpoint id (the first label's stem) — it identifies the project.
    first, _, rest = host.partition(".")
    kind = "pooled" if _POOLER_MARK in first else "direct"
    shown = "…" + first[-7:] if len(first) > 8 else first
    return f"{shown}{'.' + rest if rest else ''}/{parsed.database or ''} ({kind})"
