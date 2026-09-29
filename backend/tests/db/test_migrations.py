"""Phase 1 exit criterion: `clario db upgrade` is idempotent and creates the ownership schemas."""

from __future__ import annotations

import asyncio

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from clario.cli.main import alembic_config
from clario.main import create_app
from tests.support import make_settings

pytestmark = pytest.mark.db


def _upgrade(url: str) -> None:
    config = alembic_config(url)
    config.attributes["skip_logging_config"] = True
    command.upgrade(config, "head")


async def test_upgrade_is_idempotent_and_creates_schemas(test_database_url: str) -> None:
    await asyncio.to_thread(_upgrade, test_database_url)
    await asyncio.to_thread(_upgrade, test_database_url)  # second run must be a no-op

    engine = create_async_engine(test_database_url)
    try:
        async with engine.connect() as conn:
            schemas = set(
                (
                    await conn.execute(
                        text(
                            "SELECT schema_name FROM information_schema.schemata "
                            "WHERE schema_name IN ('core', 'finance')"
                        )
                    )
                ).scalars()
            )
            version = (
                await conn.execute(text("SELECT version_num FROM core.alembic_version"))
            ).scalar_one()
    finally:
        await engine.dispose()
    assert schemas == {"core", "finance"}
    assert (
        version == ScriptDirectory.from_config(alembic_config(test_database_url)).get_current_head()
    )


async def test_readiness_with_real_database(test_database_url: str) -> None:
    app = create_app(make_settings(database_url=test_database_url))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")
    await app.state.database.dispose()
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}
