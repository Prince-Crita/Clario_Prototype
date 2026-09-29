"""Test helpers shared across test packages (importable, unlike conftest)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import text

from clario.api.registry import build_registry
from clario.core.db import Database
from clario.integrations.zoho_books.tokens import ZohoSecret
from clario.platform.access.deps import load_workspace_scope
from clario.platform.access.permissions import Role
from clario.platform.access.scopes import ConnectionScope
from clario.platform.connections import repository as connection_repo
from clario.platform.connections import vault
from clario.platform.connections.models import ConnectionStatus
from clario.platform.connections.service import narrow
from clario.platform.integrations import repository as integration_repo
from clario.platform.integrations import service as integration_service
from clario.platform.integrations.contract import (
    AccountProfile,
    ConnectionContext,
    ConsentRedirect,
    ExternalAccount,
    Grant,
    IntegrationManifest,
)
from clario.platform.workspaces import service
from clario.settings import AppEnv, Settings

UNREACHABLE_DB = "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/unreachable_test"
PASSWORD = "correct horse battery staple"
APP_ORIGIN = "http://localhost:5173"
CORE_TABLES = (
    "finance.balance_snapshots, finance.ledger_monthly_amounts, finance.payments_made, "
    "finance.expenses, finance.payments_received, finance.invoices, finance.parties, "
    "finance.accounts, core.connection_datasets, core.sync_runs, "
    "core.tool_invocations, core.messages, core.conversations, "
    "core.audit_logs, core.user_sessions, core.oauth_states, core.connection_credentials, "
    "core.integration_connections, core.workspace_integrations, core.workspace_members, "
    "core.workspaces, core.users"
)
ZOHO_SCOPES = "ZohoBooks.settings.READ,ZohoBooks.invoices.READ,ZohoBooks.reports.READ"


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": AppEnv.TEST,
        "app_base_url": APP_ORIGIN,
        "database_url": UNREACHABLE_DB,
        "session_secret": "s" * 48,
        "encryption_keys": Fernet.generate_key().decode(),
        "log_level": "WARNING",
        # A fictitious Zoho app, so the connect flow runs; tests mock Zoho with respx.
        "zoho_client_id": "1000.TESTCLIENT",
        "zoho_client_secret": "test-client-secret",
        "zoho_scopes": ZOHO_SCOPES,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


class Factory:
    """Creates test data through the real services (so audit rows and invariants apply)."""

    def __init__(self, url: str) -> None:
        self.database = Database(url, pool_size=2, max_overflow=0)

    async def close(self) -> None:
        await self.database.dispose()

    async def truncate(self) -> None:
        async with self.database.engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {CORE_TABLES} RESTART IDENTITY CASCADE"))

    async def sql(self, statement: str, **params: Any) -> list[Any] | None:
        """Run raw SQL in its own committed transaction; SELECTs return their rows."""
        async with self.database.engine.begin() as conn:
            result = await conn.execute(text(statement), params)
            return list(result.all()) if result.returns_rows else None

    async def user(self, email: str, *, password: str = PASSWORD, admin: bool = False) -> uuid.UUID:
        async with self.database.sessions() as session:
            user = await service.create_user(
                session,
                email=email,
                full_name=email.split("@")[0].title(),
                password=password,
                is_platform_admin=admin,
            )
            await session.commit()
            return user.id

    async def workspace(self, name: str, owner_email: str) -> uuid.UUID:
        async with self.database.sessions() as session:
            workspace = await service.create_workspace(session, name=name, owner_email=owner_email)
            await session.commit()
            return workspace.id

    async def role(self, workspace_slug: str, email: str, role: Role) -> None:
        async with self.database.sessions() as session:
            await service.set_member_role(
                session, workspace_slug=workspace_slug, email=email, role=role
            )
            await session.commit()


async def show_integration(
    factory: Factory, workspace_slug: str, key: str, visible: bool = True
) -> None:
    async with factory.database.sessions() as session:
        await integration_service.set_workspace_visibility(
            session, build_registry(), workspace_slug=workspace_slug, key=key, visible=visible
        )
        await session.commit()


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> str:
    """Sign in on `client` (cookie stored in its jar); return the CSRF token."""
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token: str = response.json()["csrf_token"]
    return token


class FakeConnector:
    """A minimal connector satisfying `IntegrationPlugin` (registry and contract tests)."""

    def __init__(self, manifest: IntegrationManifest) -> None:
        self._manifest = manifest

    @property
    def manifest(self) -> IntegrationManifest:
        return self._manifest

    def consent_redirect(
        self, settings: Settings, *, state: str, region: str | None
    ) -> ConsentRedirect:
        return ConsentRedirect(url=f"https://provider.invalid/consent?state={state}", region=region)

    async def exchange(
        self, settings: Settings, callback: Mapping[str, str], *, region: str | None
    ) -> Grant:
        return Grant(secret={"token": "t"}, granted_scopes=(), region=region)

    async def list_accounts(self, context: ConnectionContext) -> list[ExternalAccount]:
        return [ExternalAccount(id="1", name="Account")]

    async def account_profile(self, context: ConnectionContext, account_id: str) -> AccountProfile:
        return AccountProfile(id=account_id, name="Account")

    async def revoke(self, settings: Settings, secret: Mapping[str, Any]) -> None:
        return None

    def data_source(self, context: ConnectionContext) -> object:
        return object()


ZOHO_ORG_ID = "60089553909"


async def zoho_connection(
    factory: Factory, settings: Settings, workspace_id: uuid.UUID, owner_email: str
) -> ConnectionScope:
    """A connected Zoho Books connection with a fresh (fake) token, as after Phase 5's flow.

    Returns the owner's ConnectionScope for it (what the API would build for that owner).
    """
    registry = build_registry()
    async with factory.database.sessions() as session:
        await integration_repo.upsert_catalog(session, registry.manifests)
        user_id = await session.scalar(
            text("SELECT id FROM core.users WHERE email = :e"), {"e": owner_email}
        )
        scope = await load_workspace_scope(session, workspace_id, user_id)
        connection = await connection_repo.ensure_pending(session, scope, "zoho-books", "in")
        connection.status = ConnectionStatus.CONNECTED
        connection.external_account_id = ZOHO_ORG_ID
        connection.external_account_name = "Crita Creative LLP (TEST trial)"
        connection.settings = {
            "currency": "INR",
            "timezone": "Asia/Calcutta",
            "fiscal_year_start_month": 4,
        }
        connection.connected_by = user_id
        connection_scope = narrow(scope, connection, "finance")
        await vault.store(
            session,
            settings,
            connection_scope,
            ZohoSecret(
                refresh_token="1000.refresh-BBB",
                access_token="1000.access-AAA",
                access_expires_at=datetime.now(UTC) + timedelta(hours=1),
                accounts_server="https://accounts.zoho.in",
                api_domain="https://www.zohoapis.in",
            ).to_json(),
            granted_scopes=ZOHO_SCOPES.split(","),
        )
        await session.commit()
        return connection_scope


GOLDEN_NOW = datetime(2026, 9, 25, 10, 26, tzinfo=UTC)  # the director PDFs' "Updated 25 Sept"


async def golden_connection(
    factory: Factory, app: Any, owner_email: str, workspace_name: str = "Alpha Traders"
) -> ConnectionScope:
    """A workspace whose Zoho Books connection holds the golden dataset (the PDFs' figures)."""
    return await fixture_connection(factory, app, owner_email, workspace_name, "golden")


async def fixture_connection(
    factory: Factory,
    app: Any,
    owner_email: str,
    workspace_name: str,
    dataset: Literal["golden", "evaluation"],
) -> ConnectionScope:
    """A workspace whose Zoho Books connection is synced from a fixture dataset on 25 Sep 2026."""
    from clario.platform.sync.models import SyncTrigger

    await factory.user(owner_email)
    workspace = await factory.workspace(workspace_name, owner_email)
    scope = await zoho_connection(factory, app.state.settings, workspace, owner_email)
    app.state.settings.finance_fixture_source = True
    app.state.settings.finance_fixture_dataset = dataset
    app.state.sync.clock = lambda: GOLDEN_NOW
    outcome = await app.state.sync.trigger(scope, SyncTrigger.SCHEDULED)
    assert outcome.started
    await app.state.sync.wait_idle()
    return scope
