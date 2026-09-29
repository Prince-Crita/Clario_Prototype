"""Shared fixtures.

Unit and API tests use a fully explicit `Settings` (no .env), so they are deterministic on any
machine. Tests using `db_*` fixtures run against TEST_DATABASE_URL, which MUST name a database
ending in `_test` — anything else aborts the session so a developer database can never be touched.
Each db test starts from empty core tables (TRUNCATE on the test database only).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from urllib.parse import urlsplit

import pytest
from alembic import command
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from clario.cli.main import alembic_config
from clario.main import create_app
from clario.settings import Settings
from tests.support import APP_ORIGIN, Factory, make_settings


def _test_database_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL")
    if url is None:
        try:
            url = Settings().test_database_url  # type: ignore[call-arg]  # reads .env / .env.local
        except Exception:
            url = None
    if url and not urlsplit(url).path.lstrip("/").endswith("_test"):
        pytest.exit(
            "Refusing to run: TEST_DATABASE_URL database must end in '_test' "
            f"({urlsplit(url).path})"
        )
    return url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = _test_database_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return url


@pytest.fixture(scope="session")
async def migrated_database_url(test_database_url: str) -> str:
    def upgrade() -> None:
        config = alembic_config(test_database_url)
        config.attributes["skip_logging_config"] = True
        command.upgrade(config, "head")

    await asyncio.to_thread(upgrade)
    return test_database_url


# ---------------------------------------------------------------- no-database app
@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.state.database.dispose()


# ---------------------------------------------------------------- database-backed app
@pytest.fixture
async def factory(migrated_database_url: str) -> AsyncIterator[Factory]:
    helper = Factory(migrated_database_url)
    await helper.truncate()
    yield helper
    await helper.close()


@pytest.fixture
def db_settings(migrated_database_url: str) -> Settings:
    return make_settings(database_url=migrated_database_url)


@pytest.fixture
async def db_app(db_settings: Settings, factory: Factory) -> AsyncIterator[FastAPI]:
    application = create_app(db_settings)
    yield application
    await application.state.sync.shutdown()  # background syncs never outlive their test
    await application.state.database.dispose()


@pytest.fixture
async def make_client(db_app: FastAPI) -> AsyncIterator[Callable[[], AsyncClient]]:
    """Factory for independent browser-like clients (each with its own cookie jar)."""
    clients: list[AsyncClient] = []

    def new() -> AsyncClient:
        ac = AsyncClient(
            transport=ASGITransport(
                app=db_app, raise_app_exceptions=False, client=("203.0.113.10", 5000)
            ),
            base_url="http://test",
            headers={"Origin": APP_ORIGIN},
        )
        clients.append(ac)
        return ac

    yield new
    for ac in clients:
        await ac.aclose()


@pytest.fixture
def db_client(make_client: Callable[[], AsyncClient]) -> AsyncClient:
    return make_client()
