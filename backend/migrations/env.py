"""Alembic environment (async, PostgreSQL, multi-schema).

* The URL comes from `sqlalchemy.url` set by `clario db …` / tests; otherwise from settings.
* The version table lives in `core.alembic_version` (plan §14.4). `core` is created first so a
  brand-new database can be migrated.
* `include_schemas=True` so autogenerate sees every module schema (core, finance, …).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from clario.api.orm_registry import metadata

config = context.config
if config.config_file_name is not None and not config.attributes.get("skip_logging_config"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

VERSION_SCHEMA = "core"


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    from clario.settings import get_settings

    return get_settings().database_url


def _configure(connection: Connection | None = None) -> None:
    options = {
        "target_metadata": metadata,
        "include_schemas": True,
        "version_table_schema": VERSION_SCHEMA,
        "compare_type": True,
        "compare_server_default": True,
    }
    if connection is None:
        context.configure(url=_url(), literal_binds=True, **options)
    else:
        context.configure(connection=connection, **options)


def run_migrations_offline() -> None:
    _configure()
    with context.begin_transaction():
        context.execute(f"CREATE SCHEMA IF NOT EXISTS {VERSION_SCHEMA}")
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {VERSION_SCHEMA}"))
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        {"sqlalchemy.url": _url()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
