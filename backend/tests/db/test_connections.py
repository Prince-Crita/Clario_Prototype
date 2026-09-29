"""Phase 5 exit criteria: Zoho Books connects end to end (mocked), tokens are encrypted, and the
needs_reauth path works. Plus every OAuth safety rule of plan §17 / §32: state tampering, reuse,
expiry, wrong user, data-center allow-list, and a callback that never renders input.

Zoho is mocked with respx; no test talks to Zoho.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlsplit

import httpx
import pytest
import respx
from fastapi import FastAPI
from httpx import AsyncClient, Response

from clario.core.crypto import Encryptor, key_fingerprint
from clario.platform.access.permissions import Role
from clario.platform.sync.service import SyncRunner
from tests.support import APP_ORIGIN, ZOHO_SCOPES, Factory, login

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def no_initial_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """Choosing an organisation starts an import in the background; these tests are about the
    connection itself (the import is covered by tests/db/test_sync.py)."""

    async def skip(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(SyncRunner, "start_quietly", skip)


OWNER = "owner@alpha.test"
ACCOUNTS = "https://accounts.zoho.in"
API = "https://www.zohoapis.in/books/v3"
ORG_ID = "60089553909"
ORG = {
    "organization_id": ORG_ID,
    "name": "Crita TEST Trial",
    "currency_code": "INR",
    "time_zone": "Asia/Calcutta",
    "is_default_org": True,
}
UNSUPPORTED_ORG = {"organization_id": "600111", "name": "Old Org", "isOrgNotSupported": True}
OTHER_ORG = {"organization_id": "600222", "name": "Someone Else", "currency_code": "USD"}
SETUP = f"{APP_ORIGIN}/w/alpha-traders/zoho-books"


def token_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "access_token": "1000.access-AAA",
        "refresh_token": "1000.refresh-BBB",
        "api_domain": "https://www.zohoapis.in",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": ZOHO_SCOPES,
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not None}


@dataclass
class Zoho:
    router: respx.MockRouter
    token: respx.Route
    revoke: respx.Route
    orgs: respx.Route
    org_detail: respx.Route

    def form(self, route: respx.Route, index: int = -1) -> dict[str, str]:
        request = route.calls[index].request
        assert "secret" not in str(request.url)
        assert "token=" not in str(request.url)
        return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


@pytest.fixture
def zoho() -> Iterator[Zoho]:
    with respx.mock(assert_all_called=False) as router:
        yield Zoho(
            router=router,
            token=router.post(f"{ACCOUNTS}/oauth/v2/token").mock(
                return_value=httpx.Response(200, json=token_payload())
            ),
            revoke=router.post(f"{ACCOUNTS}/oauth/v2/token/revoke").mock(
                return_value=httpx.Response(200, json={"status": "success"})
            ),
            orgs=router.get(f"{API}/organizations").mock(
                return_value=httpx.Response(
                    200, json={"code": 0, "organizations": [ORG, UNSUPPORTED_ORG]}
                )
            ),
            org_detail=router.get(f"{API}/organizations/{ORG_ID}").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "organization": {
                            **ORG,
                            "fiscal_year_start_month": "april",
                            "country": "India",
                        },
                    },
                )
            ),
        )


# ---------------------------------------------------------------- helpers


@dataclass
class Session:
    client: AsyncClient
    workspace: str
    csrf: str

    @property
    def headers(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf}

    def url(self, path: str) -> str:
        return f"/api/v1/workspaces/{self.workspace}{path}"

    async def start(self, **body: str) -> dict[str, str]:
        response = await self.client.post(
            self.url("/integrations/zoho-books/connect"), headers=self.headers, json=body or None
        )
        assert response.status_code == 200, response.text
        return dict(parse_qsl(urlsplit(response.json()["redirect_url"]).query))

    async def callback(self, **params: str) -> str:
        return location(await self.client.get("/api/v1/oauth/zoho-books/callback", params=params))

    async def complete(self, state: str, **extra: str) -> str:
        return await self.callback(
            code="1000.code", state=state, location="in", **{"accounts-server": ACCOUNTS, **extra}
        )

    async def tile(self) -> dict[str, Any]:
        response = await self.client.get(self.url("/integrations/zoho-books"))
        assert response.status_code == 200, response.text
        tile: dict[str, Any] = response.json()
        return tile

    async def connection_id(self) -> str:
        return str((await self.tile())["connection"]["id"])

    async def authorise(self) -> None:
        assert await self.complete((await self.start())["state"]) == f"{SETUP}/setup"

    async def connect(self) -> str:
        await self.authorise()
        cid = await self.connection_id()
        response = await self.client.post(
            self.url(f"/connections/{cid}/account"),
            headers=self.headers,
            json={"account_id": ORG_ID},
        )
        assert response.status_code == 200, response.text
        return cid


def location(response: Response) -> str:
    assert response.status_code == 302, response.text
    assert "text/html" not in response.headers.get("content-type", "")
    return response.headers["location"]


@pytest.fixture
async def owner(factory: Factory, make_client: Callable[[], AsyncClient]) -> Session:
    await factory.user(OWNER)
    workspace = str(await factory.workspace("Alpha Traders", OWNER))
    client = make_client()
    return Session(client, workspace, await login(client, OWNER))


async def stored_secret(factory: Factory, app: FastAPI) -> tuple[dict[str, Any], str, list[str]]:
    rows = await factory.sql(
        "SELECT ciphertext, key_id, granted_scopes FROM core.connection_credentials"
    )
    assert rows
    assert len(rows) == 1
    ciphertext, key_id, scopes = rows[0]
    assert b"1000." not in ciphertext  # tokens never stored in clear
    secret = json.loads(Encryptor(app.state.settings.fernet_keys).decrypt(ciphertext))
    return secret, key_id, scopes


async def expire_access_token(factory: Factory, app: FastAPI) -> None:
    secret, _, _ = await stored_secret(factory, app)
    secret["access_expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    sealed = Encryptor(app.state.settings.fernet_keys).encrypt(json.dumps(secret).encode())
    await factory.sql("UPDATE core.connection_credentials SET ciphertext = :c", c=sealed.ciphertext)


async def audit_actions(factory: Factory) -> list[str]:
    rows = await factory.sql("SELECT action FROM core.audit_logs ORDER BY id") or []
    return [r[0] for r in rows if r[0].startswith(("integration.", "connection."))]


# ---------------------------------------------------------------- connect


async def test_connect_returns_consent_url_and_stores_only_a_state_hash(
    owner: Session, factory: Factory
) -> None:
    query = await owner.start()
    assert query["client_id"] == "1000.TESTCLIENT"
    assert query["scope"] == ZOHO_SCOPES
    assert query["access_type"] == "offline"
    assert query["prompt"] == "consent"
    assert query["redirect_uri"] == "http://localhost:5173/api/v1/oauth/zoho-books/callback"
    assert len(query["state"]) >= 40

    rows = await factory.sql("SELECT state_hash, region, consumed_at FROM core.oauth_states")
    assert rows == [(hashlib.sha256(query["state"].encode()).digest(), "in", None)]
    tile = await owner.tile()
    assert tile["connection_state"] == "pending"
    assert tile["connection"]["authorised"] is False
    assert tile["regions"][0]["code"] == "in"
    assert await audit_actions(factory) == ["integration.connect_started"]


async def test_region_choice_is_allow_listed(owner: Session) -> None:
    response = await owner.client.post(
        owner.url("/integrations/zoho-books/connect"), headers=owner.headers, json={"region": "eu"}
    )
    assert response.json()["redirect_url"].startswith("https://accounts.zoho.eu/oauth/v2/auth?")
    bad = await owner.client.post(
        owner.url("/integrations/zoho-books/connect"),
        headers=owner.headers,
        json={"region": "mars"},
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "integration.invalid_region"


async def test_first_connection_end_to_end(
    owner: Session, factory: Factory, db_app: FastAPI, zoho: Zoho
) -> None:
    await owner.authorise()

    exchange = zoho.form(zoho.token)
    assert exchange["grant_type"] == "authorization_code"
    assert exchange["code"] == "1000.code"
    assert exchange["client_secret"] == "test-client-secret"
    secret, key_id, scopes = await stored_secret(factory, db_app)
    assert secret["refresh_token"] == "1000.refresh-BBB"
    assert secret["api_domain"] == "https://www.zohoapis.in"
    assert key_id == key_fingerprint(db_app.state.settings.fernet_keys[0])
    assert scopes == ZOHO_SCOPES.split(",")

    tile = await owner.tile()
    assert (tile["connection_state"], tile["connection"]["authorised"]) == ("pending", True)
    cid = tile["connection"]["id"]
    accounts = (await owner.client.get(owner.url(f"/connections/{cid}/accounts"))).json()
    assert accounts["accounts"] == [
        {
            "id": ORG_ID,
            "name": "Crita TEST Trial",
            "detail": "INR · Asia/Calcutta",
            "is_default": True,
            "selectable": True,
        },
        {"id": "600111", "name": "Old Org", "detail": "", "is_default": False, "selectable": False},
    ]
    assert (
        zoho.orgs.calls.last.request.headers["authorization"] == "Zoho-oauthtoken 1000.access-AAA"
    )

    unsupported = await owner.client.post(
        owner.url(f"/connections/{cid}/account"),
        headers=owner.headers,
        json={"account_id": "600111"},
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["code"] == "connection.unknown_account"

    chosen = await owner.client.post(
        owner.url(f"/connections/{cid}/account"), headers=owner.headers, json={"account_id": ORG_ID}
    )
    assert chosen.status_code == 200, chosen.text
    body = chosen.json()
    assert body["status"] == "connected"
    assert body["account"] == {
        "id": ORG_ID,
        "name": "Crita TEST Trial",
        "currency": "INR",
        "timezone": "Asia/Calcutta",
        "fiscal_year_start_month": 4,
    }
    assert body["connected_by"] == "Owner"
    assert "secret" not in json.dumps(body)
    assert "1000." not in json.dumps(body)
    assert (await owner.tile())["connection_state"] == "connected"

    again = await owner.client.post(
        owner.url(f"/connections/{cid}/account"), headers=owner.headers, json={"account_id": ORG_ID}
    )
    assert again.status_code == 409
    assert again.json()["code"] == "connection.account_locked"
    assert await audit_actions(factory) == [
        "integration.connect_started",
        "integration.authorized",
        "integration.connected",
    ]


async def test_accounts_need_an_authorised_connection(owner: Session) -> None:
    await owner.start()
    cid = await owner.connection_id()
    response = await owner.client.get(owner.url(f"/connections/{cid}/accounts"))
    assert response.status_code == 409
    assert response.json()["code"] == "connection.not_authorised"


# ---------------------------------------------------------------- callback safety


async def test_state_is_single_use(owner: Session, zoho: Zoho) -> None:
    state = (await owner.start())["state"]
    assert await owner.complete(state) == f"{SETUP}/setup"
    assert await owner.complete(state) == f"{SETUP}?error=state_invalid"
    assert zoho.token.call_count == 1


async def test_expired_state_is_rejected(owner: Session, factory: Factory, zoho: Zoho) -> None:
    state = (await owner.start())["state"]
    await factory.sql("UPDATE core.oauth_states SET expires_at = now() - interval '1 minute'")
    assert await owner.complete(state) == f"{SETUP}?error=state_invalid"
    assert zoho.token.call_count == 0


async def test_forged_state_and_missing_session(
    owner: Session, make_client: Callable[[], AsyncClient], zoho: Zoho
) -> None:
    assert await owner.complete("forged-" + "x" * 40) == f"{APP_ORIGIN}/w"
    state = (await owner.start())["state"]
    anonymous = Session(make_client(), owner.workspace, "")
    assert await anonymous.complete(state) == f"{APP_ORIGIN}/login"
    assert zoho.token.call_count == 0


async def test_another_user_cannot_complete_someone_elses_consent(
    owner: Session, factory: Factory, make_client: Callable[[], AsyncClient], zoho: Zoho
) -> None:
    """Login-CSRF style attack: a victim's browser is sent an attacker's code + state."""
    await factory.user("admin@alpha.test")
    await factory.role("alpha-traders", "admin@alpha.test", Role.ADMIN)
    other = make_client()
    victim = Session(other, owner.workspace, await login(other, "admin@alpha.test"))
    state = (await owner.start())["state"]
    assert await victim.complete(state) == f"{APP_ORIGIN}/w"
    assert zoho.token.call_count == 0
    assert (await owner.tile())["connection"]["authorised"] is False


async def test_callback_rechecks_permission(owner: Session, factory: Factory, zoho: Zoho) -> None:
    state = (await owner.start())["state"]
    await factory.user("second@alpha.test")
    await factory.role("alpha-traders", "second@alpha.test", Role.OWNER)
    await factory.role("alpha-traders", OWNER, Role.VIEWER)  # demoted mid-flow
    assert await owner.complete(state) == f"{SETUP}?error=forbidden"
    assert zoho.token.call_count == 0


@pytest.mark.parametrize(
    ("callback_extra", "token_overrides", "expected", "revoked"),
    [
        ({"error": "access_denied"}, {}, "access_denied", False),
        ({"accounts-server": "https://accounts.evil.example"}, {}, "server_rejected", False),
        ({}, {"access_token": None, "error": "invalid_code"}, "exchange_failed", False),
        ({}, {"refresh_token": None}, "exchange_failed", False),
        ({}, {"scope": "ZohoBooks.settings.READ"}, "missing_scopes", True),
        ({}, {"api_domain": "https://www.evil.example"}, "server_rejected", True),
    ],
)
async def test_failed_authorisations_redirect_with_a_code_and_store_nothing(
    owner: Session,
    factory: Factory,
    zoho: Zoho,
    callback_extra: dict[str, str],
    token_overrides: dict[str, Any],
    expected: str,
    revoked: bool,
) -> None:
    zoho.token.mock(return_value=httpx.Response(200, json=token_payload(**token_overrides)))
    state = (await owner.start())["state"]
    assert await owner.complete(state, **callback_extra) == f"{SETUP}?error={expected}"
    assert await factory.sql("SELECT 1 FROM core.connection_credentials") == []
    assert (await owner.tile())["connection_state"] == "pending"
    assert zoho.revoke.called is revoked
    failures = await factory.sql(
        "SELECT metadata->>'failure' FROM core.audit_logs "
        "WHERE action = 'integration.connect_failed'"
    )
    assert failures == [(expected,)]


async def test_callback_never_reflects_input(owner: Session, zoho: Zoho) -> None:
    script = "<script>alert(1)</script>"
    response = await owner.client.get(
        "/api/v1/oauth/zoho-books/callback", params={"state": script, "code": script}
    )
    assert location(response) == f"{APP_ORIGIN}/w"
    assert script not in response.text
    state = (await owner.start())["state"]
    target = await owner.complete(state, error=script)
    assert target == f"{SETUP}?error=access_denied"


# ---------------------------------------------------------------- tokens


async def test_expired_access_token_is_refreshed_once(
    owner: Session, factory: Factory, db_app: FastAPI, zoho: Zoho
) -> None:
    cid = await owner.connect()
    await expire_access_token(factory, db_app)
    zoho.token.mock(
        return_value=httpx.Response(
            200, json=token_payload(access_token="1000.access-NEW", refresh_token=None)
        )
    )
    calls_before = zoho.token.call_count

    assert (await owner.client.get(owner.url(f"/connections/{cid}/accounts"))).status_code == 200
    assert zoho.token.call_count == calls_before + 1
    refresh = zoho.form(zoho.token)
    assert (refresh["grant_type"], refresh["refresh_token"]) == (
        "refresh_token",
        "1000.refresh-BBB",
    )
    assert (
        zoho.orgs.calls.last.request.headers["authorization"] == "Zoho-oauthtoken 1000.access-NEW"
    )
    secret, _, _ = await stored_secret(factory, db_app)
    assert (secret["access_token"], secret["refresh_token"]) == (
        "1000.access-NEW",
        "1000.refresh-BBB",
    )

    assert (await owner.client.get(owner.url(f"/connections/{cid}/accounts"))).status_code == 200
    assert zoho.token.call_count == calls_before + 1  # fresh now: no second refresh


async def test_rejected_refresh_token_moves_the_connection_to_needs_reauth(
    owner: Session, factory: Factory, db_app: FastAPI, zoho: Zoho
) -> None:
    cid = await owner.connect()
    await expire_access_token(factory, db_app)
    zoho.token.mock(return_value=httpx.Response(200, json={"error": "invalid_code"}))

    response = await owner.client.get(owner.url(f"/connections/{cid}/accounts"))
    assert response.status_code == 409
    assert response.json()["code"] == "connection.needs_reauth"
    connection = (await owner.client.get(owner.url(f"/connections/{cid}"))).json()
    assert (connection["status"], connection["last_error_code"]) == (
        "needs_reauth",
        "zoho.refresh_rejected",
    )
    assert (await owner.tile())["connection_state"] == "needs_reauth"
    audit = await factory.sql(
        "SELECT actor_type FROM core.audit_logs WHERE action = 'connection.needs_reauth'"
    )
    assert audit == [("system",)]


# ---------------------------------------------------------------- reconnect


async def test_reconnect_restores_the_connection(
    owner: Session, factory: Factory, db_app: FastAPI, zoho: Zoho
) -> None:
    cid = await owner.connect()
    await factory.sql("UPDATE core.integration_connections SET status = 'needs_reauth'")
    zoho.token.mock(
        return_value=httpx.Response(200, json=token_payload(refresh_token="1000.refresh-CCC"))
    )

    assert await owner.complete((await owner.start())["state"]) == f"{SETUP}?reconnected=1"
    connection = (await owner.client.get(owner.url(f"/connections/{cid}"))).json()
    assert (connection["status"], connection["last_error_code"]) == ("connected", None)
    assert connection["account"]["id"] == ORG_ID  # same organisation, same connection
    secret, _, _ = await stored_secret(factory, db_app)
    assert secret["refresh_token"] == "1000.refresh-CCC"
    assert "integration.reconnected" in await audit_actions(factory)


async def test_reconnect_with_a_login_that_cannot_see_the_organisation(
    owner: Session, factory: Factory, db_app: FastAPI, zoho: Zoho
) -> None:
    await owner.connect()
    zoho.token.mock(
        return_value=httpx.Response(200, json=token_payload(refresh_token="1000.refresh-CCC"))
    )
    zoho.orgs.mock(return_value=httpx.Response(200, json={"code": 0, "organizations": [OTHER_ORG]}))

    assert await owner.complete((await owner.start())["state"]) == f"{SETUP}?error=account_mismatch"
    secret, _, _ = await stored_secret(factory, db_app)
    assert secret["refresh_token"] == "1000.refresh-BBB"  # the working credentials are kept
    assert zoho.form(zoho.revoke)["token"] == "1000.refresh-CCC"  # the unusable grant is revoked
    assert (await owner.tile())["connection_state"] == "connected"


# ---------------------------------------------------------------- disconnect


async def test_disconnect_revokes_deletes_credentials_and_allows_a_fresh_start(
    owner: Session, factory: Factory, zoho: Zoho
) -> None:
    cid = await owner.connect()
    response = await owner.client.delete(owner.url(f"/connections/{cid}"), headers=owner.headers)
    assert response.status_code == 204

    assert zoho.form(zoho.revoke)["token"] == "1000.refresh-BBB"
    assert await factory.sql("SELECT 1 FROM core.connection_credentials") == []
    rows = await factory.sql(
        "SELECT status, deleted_at IS NOT NULL FROM core.integration_connections"
    )
    assert rows == [("disconnected", True)]
    tile = await owner.tile()
    assert (tile["connection_state"], tile["connection"]) == ("not_connected", None)
    assert (await owner.client.get(owner.url(f"/connections/{cid}"))).status_code == 404
    audit = await factory.sql(
        "SELECT metadata->>'revoked_at_provider' FROM core.audit_logs "
        "WHERE action = 'integration.disconnected'"
    )
    assert audit == [("true",)]

    await owner.start()  # a new connection can be started
    assert await owner.connection_id() != cid


async def test_disconnect_still_works_when_zoho_is_down(
    owner: Session, factory: Factory, zoho: Zoho
) -> None:
    cid = await owner.connect()
    zoho.revoke.mock(return_value=httpx.Response(503))
    response = await owner.client.delete(owner.url(f"/connections/{cid}"), headers=owner.headers)
    assert response.status_code == 204
    assert await factory.sql("SELECT 1 FROM core.connection_credentials") == []


# ---------------------------------------------------------------- roles and tenancy


async def test_viewers_see_the_connection_but_cannot_manage_it(
    owner: Session, factory: Factory, make_client: Callable[[], AsyncClient], zoho: Zoho
) -> None:
    cid = await owner.connect()
    await factory.user("viewer@alpha.test")
    await factory.role("alpha-traders", "viewer@alpha.test", Role.VIEWER)
    client = make_client()
    viewer = Session(client, owner.workspace, await login(client, "viewer@alpha.test"))

    seen = await viewer.client.get(viewer.url(f"/connections/{cid}"))
    assert seen.status_code == 200
    assert seen.json()["account"]["name"] == "Crita TEST Trial"
    for method, path in (
        ("GET", f"/connections/{cid}/accounts"),
        ("POST", f"/connections/{cid}/account"),
        ("DELETE", f"/connections/{cid}"),
    ):
        response = await viewer.client.request(
            method, viewer.url(path), headers=viewer.headers, json={"account_id": ORG_ID}
        )
        assert response.status_code == 403, (method, path)


async def test_a_connection_is_unreachable_from_another_workspace(
    owner: Session, factory: Factory, make_client: Callable[[], AsyncClient], zoho: Zoho
) -> None:
    cid = await owner.connect()
    await factory.user("owner@beta.test")
    beta = str(await factory.workspace("Beta Foods", "owner@beta.test"))
    client = make_client()
    other = Session(client, beta, await login(client, "owner@beta.test"))

    for method, path in (
        ("GET", f"/connections/{cid}"),
        ("GET", f"/connections/{cid}/accounts"),
        ("POST", f"/connections/{cid}/account"),
        ("DELETE", f"/connections/{cid}"),
    ):
        response = await other.client.request(
            method, other.url(path), headers=other.headers, json={"account_id": ORG_ID}
        )
        assert response.status_code == 404, (method, path)
        assert response.json()["code"] == "connection.not_found"
    assert (await owner.tile())["connection_state"] == "connected"
    assert (await other.tile())["connection_state"] == "not_connected"
