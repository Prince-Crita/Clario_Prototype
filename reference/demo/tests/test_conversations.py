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
async def test_conversation_history_endpoints(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "hist@example.com", "password": "password123", "tenant_name": "Hist Co"},
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant_id"]
    user_id = reg.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}

    from clario.db.session import get_session_factory
    from clario.tenancy.service import add_message, ensure_conversation

    maker = get_session_factory()
    async with maker() as db:
        convo = await ensure_conversation(db, tenant_id=tenant_id, user_id=user_id)
        await add_message(db, conversation=convo, role="user", content="How are sales?")
        await add_message(db, conversation=convo, role="assistant", content="Sales look fine.")
        await db.commit()
        convo_id = convo.id

    listed = await client.get("/api/conversations", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()["conversations"]
    assert any(r["id"] == convo_id for r in rows)
    assert any(r["title"] == "How are sales?" for r in rows)

    detail = await client.get(f"/api/conversations/{convo_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"

    deleted = await client.delete(f"/api/conversations/{convo_id}", headers=headers)
    assert deleted.status_code == 200
    listed2 = await client.get("/api/conversations", headers=headers)
    assert all(r["id"] != convo_id for r in listed2.json()["conversations"])
