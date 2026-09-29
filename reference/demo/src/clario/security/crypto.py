"""Encryption and auth helpers. Secrets never leave the server."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from clario.config import get_settings


class EncryptionError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.clario_encryption_key.strip()
    if key:
        return Fernet(key.encode("utf-8"))
    digest = hashlib.sha256(f"clario-enc:{settings.clario_jwt_secret}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    if plaintext == "":
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if ciphertext == "":
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError(
            "Could not decrypt stored Zoho token. Check CLARIO_ENCRYPTION_KEY."
        ) from exc


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *,
    user_id: str,
    email: str,
    tenant_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=settings.clario_jwt_hours),
        "typ": "access",
    }
    if tenant_id:
        payload["tid"] = tenant_id
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.clario_jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.clario_jwt_secret, algorithms=["HS256"])


def generate_api_key() -> tuple[str, str, str]:
    raw = f"clr_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    return raw, prefix, hash_password(raw)


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    return verify_password(raw_key, key_hash)


def reset_crypto_cache() -> None:
    _fernet.cache_clear()
