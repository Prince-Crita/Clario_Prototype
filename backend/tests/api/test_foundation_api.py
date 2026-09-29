from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient

from clario.core.errors import ConflictError
from clario.main import create_app
from tests.support import make_settings

PROBLEM = "application/problem+json"


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"]


async def test_readiness_reports_unreachable_database_as_problem(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith(PROBLEM)
    body = response.json()
    assert body["code"] == "health.database_unavailable"
    assert body["request_id"] == response.headers["x-request-id"]


async def test_unknown_route_is_problem_json(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["code"] == "not_found"


async def test_inbound_request_id_is_propagated_only_when_well_formed(client: AsyncClient) -> None:
    good = await client.get("/api/v1/health", headers={"X-Request-ID": "proxy-req-12345678"})
    assert good.headers["x-request-id"] == "proxy-req-12345678"
    bad = await client.get("/api/v1/health", headers={"X-Request-ID": "<script>"})
    assert bad.headers["x-request-id"] != "<script>"


async def test_clario_error_and_unhandled_error_rendering(
    app: FastAPI, client: AsyncClient
) -> None:
    @app.get("/boom/conflict")
    async def conflict() -> None:
        raise ConflictError("Already connected.", code="connection.already_connected")

    @app.get("/boom/crash")
    async def crash() -> None:
        raise RuntimeError("secret internal detail")

    conflict_response = await client.get("/boom/conflict")
    assert conflict_response.status_code == 409
    assert conflict_response.json()["code"] == "connection.already_connected"
    assert conflict_response.json()["detail"] == "Already connected."

    crash_response = await client.get("/boom/crash")
    assert crash_response.status_code == 500
    assert crash_response.json()["code"] == "internal_error"
    assert "secret internal detail" not in crash_response.text


async def test_validation_errors_list_fields(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/boom/validate")
    async def validate(limit: int) -> dict[str, int]:
        return {"limit": limit}

    response = await client.get("/boom/validate", params={"limit": "many"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"].endswith("limit")


def test_docs_disabled_in_production() -> None:
    app = create_app(
        make_settings(
            app_env="production", session_cookie_secure=True, app_base_url="https://clario.example"
        )
    )
    assert app.openapi_url is None
    assert app.docs_url is None
    assert create_app(make_settings()).openapi_url == "/api/v1/openapi.json"
