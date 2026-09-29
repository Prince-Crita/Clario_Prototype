"""Session cookie tokens and CSRF tokens (plan §12).

* The cookie holds a random 256-bit token; the database stores only its SHA-256.
* The CSRF token is an HMAC of that hash with SESSION_SECRET — stateless to verify, bound to the
  session, and useless to an attacker who cannot read the (httpOnly) cookie.
* With Secure cookies the `__Host-` prefix is used: the browser then refuses the cookie unless it
  is Secure, host-only and Path=/, which blocks subdomain cookie injection.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

CSRF_HEADER = "X-CSRF-Token"


def cookie_name(secure: bool) -> str:
    return "__Host-clario_session" if secure else "clario_session"


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def csrf_token_for(token_hash: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), b"csrf:" + token_hash, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def csrf_valid(session_token: str, provided: str | None, secret: str) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(csrf_token_for(hash_token(session_token), secret), provided)
