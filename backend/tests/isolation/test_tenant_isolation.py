"""Tenant-isolation harness (plan §13.3, §32) — self-discovering.

It enumerates every operation in the application's OpenAPI schema, so endpoints added in later
phases are covered automatically:

  1. Every non-public route rejects anonymous callers (401).
  2. Every route with `{workspace_id}` answers a member of workspace A who targets workspace B with
     exactly the same 404 as for a workspace that does not exist (ids cannot be probed).
  3. The same routes do NOT 404 for the caller's own workspace (proves the harness is not vacuous).

A route is exempt only if listed in PUBLIC_ROUTES with a reason.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response

from tests.support import Factory, login

pytestmark = pytest.mark.db

PUBLIC_ROUTES = {
    ("POST", "/api/v1/auth/login"): "sign-in",
    ("GET", "/api/v1/health"): "liveness probe, no data",
    ("GET", "/api/v1/health/ready"): "readiness probe, no data",
    ("GET", "/api/v1/oauth/{integration}/callback"): (
        "provider redirect target: always answers 302, checks session + state itself "
        "(tests/db/test_connections.py)"
    ),
}
_PARAM = re.compile(r"\{(\w+)(?::\w+)?\}")


def api_routes(app: FastAPI) -> list[tuple[str, str]]:
    """Every API operation, from the OpenAPI schema (the public contract; version-proof)."""
    paths: dict[str, dict[str, object]] = app.openapi()["paths"]
    return sorted(
        (method.upper(), path)
        for path, operations in paths.items()
        if path.startswith("/api/")
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS"}
    )


def fill(path: str, workspace_id: uuid.UUID) -> str:
    return _PARAM.sub(
        lambda m: str(workspace_id) if m.group(1) == "workspace_id" else str(uuid.uuid4()), path
    )


async def call(client: AsyncClient, method: str, url: str, csrf: str | None) -> Response:
    headers = {"X-CSRF-Token": csrf} if csrf and method != "GET" else {}
    return await client.request(method, url, headers=headers, json={} if method != "GET" else None)


def without_request_id(response: Response) -> tuple[int, dict[str, object]]:
    return response.status_code, {k: v for k, v in response.json().items() if k != "request_id"}


async def test_every_non_public_route_requires_authentication(
    db_app: FastAPI, db_client: AsyncClient
) -> None:
    protected = [r for r in api_routes(db_app) if r not in PUBLIC_ROUTES]
    assert len(protected) >= 5, "harness found suspiciously few routes"
    for method, path in protected:
        response = await call(db_client, method, fill(path, uuid.uuid4()), None)
        assert response.status_code == 401, f"{method} {path} is reachable anonymously"


async def test_foreign_workspace_ids_are_indistinguishable_from_missing_ones(
    db_app: FastAPI, factory: Factory, make_client: Callable[[], AsyncClient]
) -> None:
    await factory.user("owner@alpha.test")
    await factory.user("owner@beta.test")
    alpha = await factory.workspace("Alpha Traders", "owner@alpha.test")
    beta = await factory.workspace("Beta Foods", "owner@beta.test")
    client = make_client()
    csrf = await login(
        client, "owner@alpha.test"
    )  # owner: every permission, so only scope can refuse

    scoped = [(m, p) for m, p in api_routes(db_app) if "{workspace_id}" in p]
    assert len(scoped) >= 2, "harness found no workspace-scoped routes"
    for method, path in scoped:
        foreign = await call(client, method, fill(path, beta), csrf)
        missing = await call(client, method, fill(path, uuid.uuid4()), csrf)
        assert foreign.status_code == 404, (
            f"{method} {path} leaked across workspaces ({foreign.status_code})"
        )
        assert foreign.json()["code"] == "workspace.not_found"
        assert without_request_id(foreign) == without_request_id(missing), (
            f"{method} {path} is probe-able"
        )

        own = await call(client, method, fill(path, alpha), csrf)
        assert not (own.status_code == 404 and own.json().get("code") == "workspace.not_found"), (
            f"{method} {path} rejected the caller's own workspace — harness would be vacuous"
        )
