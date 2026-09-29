from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from clario.config import reload_settings
from clario.db.session import init_db, reset_engine
from clario.security.crypto import reset_crypto_cache


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("CLARIO_JWT_SECRET", "test-secret-key-at-least-32-bytes-long")
    monkeypatch.setenv("CLARIO_ENCRYPTION_KEY", "")
    monkeypatch.setenv("ZOHO_CLIENT_ID", "test-client")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("MULTI_TENANT_ENABLED", "true")
    reset_engine()
    reset_crypto_cache()
    reload_settings()
    await init_db()

    from clario.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    reset_engine()
    reset_crypto_cache()


@pytest.mark.asyncio
async def test_register_login_and_tenant_isolation(client):
    reg_a = await client.post(
        "/api/auth/register",
        json={
            "email": "a@example.com",
            "password": "password123",
            "full_name": "Alice",
            "tenant_name": "Alpha Co",
        },
    )
    assert reg_a.status_code == 200, reg_a.text
    token_a = reg_a.json()["access_token"]
    tenant_a = reg_a.json()["tenant_id"]

    reg_b = await client.post(
        "/api/auth/register",
        json={
            "email": "b@example.com",
            "password": "password123",
            "full_name": "Bob",
            "tenant_name": "Beta Co",
        },
    )
    assert reg_b.status_code == 200
    token_b = reg_b.json()["access_token"]
    tenant_b = reg_b.json()["tenant_id"]
    assert tenant_a != tenant_b

    me_a = await client.get(
        "/api/me", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert me_a.status_code == 200
    assert me_a.json()["tenants"][0]["name"] == "Alpha Co"

    # Alice cannot use Bob's tenant id
    forbidden = await client.get(
        "/api/status",
        headers={"Authorization": f"Bearer {token_a}", "X-Tenant-Id": tenant_b},
    )
    assert forbidden.status_code == 403

    ok = await client.get(
        "/api/status",
        headers={"Authorization": f"Bearer {token_a}", "X-Tenant-Id": tenant_a},
    )
    assert ok.status_code == 200
    assert ok.json()["tenant_id"] == tenant_a
    assert ok.json()["zoho_ready"] is False


@pytest.mark.asyncio
async def test_second_workspace_and_oauth_start_url(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "c@example.com", "password": "password123", "tenant_name": "One"},
    )
    token = reg.json()["access_token"]
    created = await client.post(
        "/api/tenants",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Two"},
    )
    assert created.status_code == 200
    tenant_id = created.json()["id"]

    start = await client.get(
        "/api/oauth/zoho/start",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id},
    )
    assert start.status_code == 200
    body = start.json()
    assert "accounts.zoho" in body["authorization_url"]
    assert "client_id=test-client" in body["authorization_url"]
    assert "access_type=offline" in body["authorization_url"]


@pytest.mark.asyncio
async def test_zoho_settings_updates_data_center(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "z@example.com", "password": "password123", "tenant_name": "Zoho Co"},
    )
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}

    updated = await client.post(
        "/api/tenants/current/zoho/settings",
        headers=headers,
        json={
            "data_center": "eu",
            "organization_id": "org-123",
            "client_id": "tenant-client-id",
            "client_secret": "tenant-client-secret",
        },
    )
    assert updated.status_code == 200, updated.text
    zoho = updated.json()["zoho"]
    assert zoho["data_center"] == "eu"
    assert zoho["organization_id"] == "org-123"
    assert "zoho.eu" in zoho["accounts_url"]
    assert zoho["is_connected"] is False
    assert zoho["client_id"] == "tenant-client-id"
    assert zoho["client_secret_configured"] is True
    assert zoho["client_secret_masked"].endswith("cret") or "••••" in zoho["client_secret_masked"]
    assert zoho["uses_platform_oauth_app"] is False
    assert "redirect_uri" in zoho


@pytest.mark.asyncio
async def test_chat_requires_zoho_connection(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "d@example.com", "password": "password123"},
    )
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant_id"]
    response = await client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id},
        json={"message": "How is the business doing?"},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "Zoho" in detail or "GOOGLE_API_KEY" in detail or "GROQ_API_KEY" in detail


@pytest.mark.asyncio
async def test_analytics_requires_zoho_connection(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "e@example.com", "password": "password123"},
    )
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant_id"]
    response = await client.get(
        "/api/analytics/overview",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id},
    )
    assert response.status_code == 503
    assert "Zoho" in response.json()["detail"]
