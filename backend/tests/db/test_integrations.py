"""Phase 4 exit criterion: coming-soon cards visible, inert, and rejected by the API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from clario.platform.access.permissions import Role
from clario.platform.integrations import repository
from clario.platform.integrations.contract import Availability
from tests.support import Factory, login, show_integration

pytestmark = pytest.mark.db
OWNER = "owner@alpha.test"


async def setup_alpha(factory: Factory) -> str:
    await factory.user(OWNER)
    return str(await factory.workspace("Alpha Traders", OWNER))


async def test_default_catalog_shows_available_integrations_only(
    factory: Factory, db_client: AsyncClient
) -> None:
    alpha = await setup_alpha(factory)
    await login(db_client, OWNER)
    tiles = (await db_client.get(f"/api/v1/workspaces/{alpha}/integrations")).json()["integrations"]
    assert [t["key"] for t in tiles] == ["zoho-books"]
    zoho = tiles[0]
    assert zoho["connection_state"] == "not_connected"
    assert zoho["domain_name"] == "Finance"
    assert zoho["read_only"] is True
    assert zoho["can_manage"] is True
    assert len(zoho["reads"]) == 4


async def test_enabled_placeholders_appear_as_coming_soon(
    factory: Factory, db_client: AsyncClient
) -> None:
    alpha = await setup_alpha(factory)
    await show_integration(factory, "alpha-traders", "city-threads-inventory")
    await show_integration(factory, "alpha-traders", "lead-management")
    await login(db_client, OWNER)
    tiles = (await db_client.get(f"/api/v1/workspaces/{alpha}/integrations")).json()["integrations"]
    assert [(t["key"], t["connection_state"]) for t in tiles] == [
        ("zoho-books", "not_connected"),
        ("city-threads-inventory", "coming_soon"),
        ("lead-management", "coming_soon"),
    ]
    detail = await db_client.get(f"/api/v1/workspaces/{alpha}/integrations/lead-management")
    assert detail.status_code == 200
    assert detail.json()["domain_name"] == "Leads"


async def test_hidden_or_unknown_integrations_are_not_found(
    factory: Factory, db_client: AsyncClient
) -> None:
    alpha = await setup_alpha(factory)
    await show_integration(factory, "alpha-traders", "zoho-books", visible=False)
    await login(db_client, OWNER)
    assert (await db_client.get(f"/api/v1/workspaces/{alpha}/integrations")).json()[
        "integrations"
    ] == []
    for key in ("zoho-books", "veloce-inventory", "no-such-thing"):
        response = await db_client.get(f"/api/v1/workspaces/{alpha}/integrations/{key}")
        assert response.status_code == 404, key
        assert response.json()["code"] == "integration.not_found"


async def test_connect_gate(factory: Factory, db_client: AsyncClient) -> None:
    alpha = await setup_alpha(factory)
    await show_integration(factory, "alpha-traders", "veloce-inventory")
    csrf = await login(db_client, OWNER)
    headers = {"X-CSRF-Token": csrf}

    def connect(key: str) -> str:
        return f"/api/v1/workspaces/{alpha}/integrations/{key}/connect"

    coming_soon = await db_client.post(connect("veloce-inventory"), headers=headers)
    assert coming_soon.status_code == 409
    assert coming_soon.json()["code"] == "integration.not_available"

    hidden = await db_client.post(connect("lead-management"), headers=headers)
    assert hidden.status_code == 404

    unknown = await db_client.post(connect("no-such-thing"), headers=headers)
    assert unknown.status_code == 404

    no_csrf = await db_client.post(connect("zoho-books"))
    assert no_csrf.status_code == 403
    assert no_csrf.json()["code"] == "auth.csrf_failed"

    # Every check passed → the connector builds the provider consent URL.
    zoho = await db_client.post(connect("zoho-books"), headers=headers)
    assert zoho.status_code == 200
    assert zoho.json()["redirect_url"].startswith("https://accounts.zoho.in/oauth/v2/auth?")


async def test_viewers_cannot_connect(factory: Factory, db_client: AsyncClient) -> None:
    alpha = await setup_alpha(factory)
    await factory.user("viewer@alpha.test")
    await factory.role("alpha-traders", "viewer@alpha.test", Role.VIEWER)
    csrf = await login(db_client, "viewer@alpha.test")
    tiles = (await db_client.get(f"/api/v1/workspaces/{alpha}/integrations")).json()["integrations"]
    assert tiles[0]["can_manage"] is False
    response = await db_client.post(
        f"/api/v1/workspaces/{alpha}/integrations/zoho-books/connect",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403
    assert response.json()["required"] == "integrations.manage"


async def test_visibility_is_per_workspace_and_audited(
    factory: Factory, db_client: AsyncClient
) -> None:
    await setup_alpha(factory)
    await factory.user("owner@beta.test")
    beta = await factory.workspace("Beta Foods", "owner@beta.test")
    await show_integration(factory, "alpha-traders", "city-threads-inventory")
    await login(db_client, "owner@beta.test")
    tiles = (await db_client.get(f"/api/v1/workspaces/{beta}/integrations")).json()["integrations"]
    assert [t["key"] for t in tiles] == ["zoho-books"]  # Alpha's card choice does not leak to Beta
    audit = await factory.sql(
        "SELECT action, target_id, metadata->>'visible' FROM core.audit_logs "
        "WHERE action = 'integration.visibility_changed'"
    )
    assert audit == [("integration.visibility_changed", "city-threads-inventory", "true")]


async def test_catalog_upsert_is_idempotent_and_retires_removed_keys(factory: Factory) -> None:
    from clario.api.registry import build_registry

    manifests = build_registry().manifests
    async with factory.database.sessions() as session:
        await repository.upsert_catalog(session, manifests)
        await repository.upsert_catalog(session, manifests)
        await repository.upsert_catalog(
            session, [m for m in manifests if m.key != "lead-management"]
        )
        await session.commit()
    rows = dict(await factory.sql("SELECT key, availability FROM core.integrations") or [])
    assert rows["zoho-books"] == Availability.AVAILABLE.value
    assert rows["lead-management"] == Availability.RETIRED.value
    async with factory.database.sessions() as session:  # restore for other tests
        await repository.upsert_catalog(session, manifests)
        await session.commit()
