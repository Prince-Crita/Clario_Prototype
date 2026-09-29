"""Workspace API and provisioning service behaviour."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from clario.core.errors import ConflictError, NotFoundError, ValidationFailedError
from clario.platform.access.permissions import Role
from clario.platform.workspaces import service
from tests.support import Factory, login

pytestmark = pytest.mark.db


async def test_user_sees_only_own_workspaces_with_role_permissions(
    factory: Factory, db_client: AsyncClient
) -> None:
    await factory.user("owner@alpha.test")
    await factory.user("viewer@alpha.test")
    await factory.user("owner@beta.test")
    alpha = await factory.workspace("Alpha Traders", "owner@alpha.test")
    await factory.workspace("Beta Foods", "owner@beta.test")
    await factory.role("alpha-traders", "viewer@alpha.test", Role.VIEWER)

    await login(db_client, "viewer@alpha.test")
    listed = (await db_client.get("/api/v1/workspaces")).json()["workspaces"]
    assert [(w["slug"], w["role"]) for w in listed] == [("alpha-traders", "viewer")]

    detail = (await db_client.get(f"/api/v1/workspaces/{alpha}")).json()
    assert detail["timezone"] == "Asia/Kolkata"
    assert detail["base_currency"] == "INR"
    assert detail["fiscal_year_start_month"] == 4
    assert detail["permissions"] == ["finance.view", "workspace.view"]

    members = (await db_client.get(f"/api/v1/workspaces/{alpha}/members")).json()["members"]
    assert {(m["email"], m["role"]) for m in members} == {
        ("owner@alpha.test", "owner"),
        ("viewer@alpha.test", "viewer"),
    }


async def test_suspended_workspace_blocks_members(factory: Factory, db_client: AsyncClient) -> None:
    await factory.user("owner@alpha.test")
    alpha = await factory.workspace("Alpha Traders", "owner@alpha.test")
    await login(db_client, "owner@alpha.test")
    await factory.sql("UPDATE core.workspaces SET status = 'suspended'")
    response = await db_client.get(f"/api/v1/workspaces/{alpha}")
    assert response.status_code == 403
    assert response.json()["code"] == "workspace.inactive"


async def test_removed_member_loses_access(factory: Factory, db_client: AsyncClient) -> None:
    await factory.user("owner@alpha.test")
    await factory.user("member@alpha.test")
    alpha = await factory.workspace("Alpha Traders", "owner@alpha.test")
    await factory.role("alpha-traders", "member@alpha.test", Role.MEMBER)
    await login(db_client, "member@alpha.test")
    assert (await db_client.get(f"/api/v1/workspaces/{alpha}")).status_code == 200

    async with factory.database.sessions() as session:
        await service.remove_member(
            session, workspace_slug="alpha-traders", email="member@alpha.test"
        )
        await session.commit()
    assert (await db_client.get(f"/api/v1/workspaces/{alpha}")).status_code == 404


async def test_provisioning_rules_and_audit(factory: Factory) -> None:
    await factory.user("owner@alpha.test")
    async with factory.database.sessions() as session:
        with pytest.raises(ConflictError):
            await service.create_user(
                session, email="OWNER@alpha.test", full_name="Dup", password="another long password"
            )
        with pytest.raises(ValidationFailedError, match="time zone"):
            await service.create_workspace(
                session, name="Alpha", owner_email="owner@alpha.test", timezone="Mars/Olympus"
            )
        with pytest.raises(NotFoundError):
            await service.create_workspace(session, name="Alpha", owner_email="ghost@alpha.test")
        workspace = await service.create_workspace(
            session, name="Alpha & Sons, Ltd.", owner_email="owner@alpha.test"
        )
        assert workspace.slug == "alpha-sons-ltd"
        with pytest.raises(ConflictError, match="at least one owner"):
            await service.set_member_role(
                session, workspace_slug="alpha-sons-ltd", email="owner@alpha.test", role=Role.ADMIN
            )
        await session.commit()

    audit = await factory.sql("SELECT action, actor_type FROM core.audit_logs ORDER BY id")
    assert audit == [("user.created", "system"), ("workspace.created", "system")]


async def test_reset_password_clears_lockout_and_signs_out(
    factory: Factory, db_client: AsyncClient
) -> None:
    await factory.user("owner@alpha.test")
    await login(db_client, "owner@alpha.test")
    await factory.sql(
        "UPDATE core.users SET failed_login_count = 9, locked_until = now() + interval '1 hour'"
    )
    async with factory.database.sessions() as session:
        await service.reset_password(
            session, email="owner@alpha.test", new_password="operator set this one"
        )
        await session.commit()
    assert (await db_client.get("/api/v1/auth/session")).status_code == 401
    assert await factory.sql("SELECT failed_login_count, locked_until FROM core.users") == [
        (0, None)
    ]
    await login(db_client, "owner@alpha.test", "operator set this one")
