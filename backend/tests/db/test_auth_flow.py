"""Phase 2 exit criterion: login / session / logout end to end, plus the security properties."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from clario.platform.identity.ratelimit import SlidingWindowLimiter
from tests.support import PASSWORD, Factory, login

pytestmark = pytest.mark.db
EMAIL = "owner@alpha.test"


async def test_login_sets_hardened_cookie_and_returns_session(
    factory: Factory, db_client: AsyncClient
) -> None:
    await factory.user(EMAIL)
    await factory.workspace("Alpha Traders", EMAIL)

    response = await db_client.post(
        "/api/v1/auth/login", json={"email": "Owner@Alpha.test ", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("clario_session=")
    for flag in ("HttpOnly", "Path=/", "SameSite=lax"):
        assert flag.lower() in cookie.lower()
    body = response.json()
    assert body["user"]["email"] == EMAIL
    assert [w["slug"] for w in body["workspaces"]] == ["alpha-traders"]
    assert body["workspaces"][0]["role"] == "owner"
    assert body["csrf_token"]

    token = db_client.cookies["clario_session"]
    stored = await factory.sql("SELECT token_hash FROM core.user_sessions")
    assert len(stored) == 1
    assert token.encode() not in bytes(stored[0][0])  # only the hash is stored

    session = await db_client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["email"] == EMAIL


async def test_secure_cookie_uses_host_prefix(migrated_database_url: str, factory: Factory) -> None:
    from httpx import ASGITransport

    from clario.main import create_app
    from tests.support import APP_ORIGIN, make_settings

    await factory.user(EMAIL)
    app = create_app(make_settings(database_url=migrated_database_url, session_cookie_secure=True))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"Origin": APP_ORIGIN}
    ) as c:
        response = await c.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    await app.state.database.dispose()
    assert response.headers["set-cookie"].startswith("__Host-clario_session=")
    assert "secure" in response.headers["set-cookie"].lower()


async def test_wrong_password_and_unknown_email_are_indistinguishable(
    factory: Factory, db_client: AsyncClient
) -> None:
    await factory.user(EMAIL)
    wrong = await db_client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "not the password!"}
    )
    unknown = await db_client.post(
        "/api/v1/auth/login", json={"email": "nobody@alpha.test", "password": PASSWORD}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert {k: v for k, v in wrong.json().items() if k != "request_id"} == {
        k: v for k, v in unknown.json().items() if k != "request_id"
    }
    reasons = await factory.sql(
        "SELECT metadata->>'reason' FROM core.audit_logs "
        "WHERE action = 'auth.login.failed' ORDER BY id"
    )
    assert [r[0] for r in reasons] == ["invalid_password", "unknown_email"]


async def test_account_lockout_persists_and_blocks_even_the_right_password(
    factory: Factory, db_client: AsyncClient
) -> None:
    await factory.user(EMAIL)
    for _ in range(5):
        response = await db_client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "wrong password!!"}
        )
        assert response.status_code == 401
    locked = await db_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert locked.status_code == 429
    assert locked.json()["code"] == "auth.too_many_attempts"
    rows = await factory.sql("SELECT failed_login_count, locked_until IS NOT NULL FROM core.users")
    assert rows == [(5, True)]


async def test_per_ip_rate_limit(factory: Factory, db_app: FastAPI, db_client: AsyncClient) -> None:
    db_app.state.login_limiter = SlidingWindowLimiter(max_attempts=2, window_seconds=300)
    await factory.user(EMAIL)
    for _ in range(2):
        await db_client.post(
            "/api/v1/auth/login", json={"email": "x@alpha.test", "password": "whatever-123"}
        )
    blocked = await db_client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert blocked.status_code == 429


async def test_logout_requires_csrf_and_revokes_session(
    factory: Factory, db_client: AsyncClient
) -> None:
    await factory.user(EMAIL)
    csrf = await login(db_client, EMAIL)

    no_token = await db_client.post("/api/v1/auth/logout")
    assert no_token.status_code == 403
    assert no_token.json()["code"] == "auth.csrf_failed"
    forged = await db_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "forged"})
    assert forged.status_code == 403

    token = db_client.cookies["clario_session"]
    out = await db_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert out.status_code == 204
    db_client.cookies.set("clario_session", token)  # replaying the old cookie must not work
    after = await db_client.get("/api/v1/auth/session")
    assert after.status_code == 401
    actions = await factory.sql("SELECT action FROM core.audit_logs ORDER BY id")
    assert [a[0] for a in actions][-2:] == ["auth.login.succeeded", "auth.logout"]


async def test_cross_site_origin_is_rejected(factory: Factory, db_client: AsyncClient) -> None:
    await factory.user(EMAIL)
    response = await db_client.post(
        "/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "auth.origin_rejected"


async def test_anonymous_requests_get_401(db_client: AsyncClient, factory: Factory) -> None:
    for path in ("/api/v1/auth/session", "/api/v1/workspaces"):
        response = await db_client.get(path)
        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"


@pytest.mark.parametrize("column", ["idle_expires_at", "absolute_expires_at"])
async def test_expired_sessions_are_rejected(
    column: str, factory: Factory, db_client: AsyncClient
) -> None:
    await factory.user(EMAIL)
    await login(db_client, EMAIL)
    statement = f"UPDATE core.user_sessions SET {column} = now() - interval '1 minute'"  # noqa: S608
    await factory.sql(statement)  # `column` comes from the parametrize list above, not user input
    response = await db_client.get("/api/v1/auth/session")
    assert response.status_code == 401
    assert response.json()["code"] == "auth.session_expired"


async def test_disabled_user_loses_access(factory: Factory, db_client: AsyncClient) -> None:
    await factory.user(EMAIL)
    await login(db_client, EMAIL)
    await factory.sql("UPDATE core.users SET status = 'disabled'")
    assert (await db_client.get("/api/v1/auth/session")).status_code == 401
    relogin = await db_client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert relogin.status_code == 401


async def test_change_password_revokes_other_sessions(
    factory: Factory, make_client: Callable[[], AsyncClient]
) -> None:
    await factory.user(EMAIL)
    laptop, phone = make_client(), make_client()
    csrf = await login(laptop, EMAIL)
    await login(phone, EMAIL)

    wrong = await laptop.post(
        "/api/v1/auth/password",
        json={"current_password": "not it at all", "new_password": "a brand new passphrase"},
        headers={"X-CSRF-Token": csrf},
    )
    assert wrong.status_code == 422
    weak = await laptop.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers={"X-CSRF-Token": csrf},
    )
    assert weak.json()["code"] == "auth.weak_password"

    ok = await laptop.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "a brand new passphrase"},
        headers={"X-CSRF-Token": csrf},
    )
    assert ok.status_code == 204
    assert (
        await laptop.get("/api/v1/auth/session")
    ).status_code == 200  # this device stays signed in
    assert (await phone.get("/api/v1/auth/session")).status_code == 401  # other devices signed out
    fresh = make_client()
    await login(fresh, EMAIL, "a brand new passphrase")


async def test_can_sign_in_again_while_holding_an_expired_cookie(
    factory: Factory, db_client: AsyncClient
) -> None:
    """Regression: a stale cookie must not make sign-in fail the CSRF check (found in Phase 2)."""
    await factory.user(EMAIL)
    await login(db_client, EMAIL)
    await factory.sql("UPDATE core.user_sessions SET revoked_at = now()")
    assert (await db_client.get("/api/v1/auth/session")).status_code == 401
    await login(db_client, EMAIL)  # still holding the old cookie
    assert (await db_client.get("/api/v1/auth/session")).status_code == 200
