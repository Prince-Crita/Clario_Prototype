from __future__ import annotations

from clario.security.crypto import (
    create_access_token,
    decode_access_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    reset_crypto_cache,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("password123")
    assert verify_password("password123", hashed)
    assert not verify_password("wrong", hashed)


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setenv("CLARIO_JWT_SECRET", "enc-test-secret")
    monkeypatch.setenv("CLARIO_ENCRYPTION_KEY", "")
    reset_crypto_cache()
    from clario.config import reload_settings

    reload_settings()
    cipher = encrypt_secret("zoho-refresh-token")
    assert "zoho-refresh-token" not in cipher
    assert decrypt_secret(cipher) == "zoho-refresh-token"
    reset_crypto_cache()


def test_jwt_contains_tenant_claim(monkeypatch):
    monkeypatch.setenv("CLARIO_JWT_SECRET", "test-secret-key-at-least-32-bytes-long")
    from clario.config import reload_settings

    reload_settings()
    token = create_access_token(user_id="u1", email="a@x.com", tenant_id="t1")
    payload = decode_access_token(token)
    assert payload["sub"] == "u1"
    assert payload["tid"] == "t1"
