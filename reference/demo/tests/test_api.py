from __future__ import annotations

from fastapi.testclient import TestClient

from clario.api.main import app

client = TestClient(app)


def test_health_reports_multi_tenant():
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["multi_tenant"] is True
    assert "client_secret" not in str(body).lower()


def test_status_requires_auth():
    response = client.get("/api/status")
    assert response.status_code == 401


def test_chat_requires_auth():
    response = client.post("/api/chat", json={"message": "Which customers owe us the most?"})
    assert response.status_code == 401


def test_legacy_oauth_start_points_to_multi_tenant_flow():
    response = client.get("/oauth/zoho/start", follow_redirects=False)
    assert response.status_code == 400
    assert "Multi-tenant OAuth" in response.text


def test_index_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Clario" in response.text
    assert "Create account" in response.text
