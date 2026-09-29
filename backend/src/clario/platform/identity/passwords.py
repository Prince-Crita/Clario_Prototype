"""Password hashing (argon2id, OWASP's first choice) and policy (plan §12)."""

from __future__ import annotations

import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from clario.core.errors import ValidationFailedError

MIN_LENGTH = 12
MAX_LENGTH = 256

_hasher = PasswordHasher()  # argon2id, RFC 9106 low-memory profile


def validate_password(password: str, *, email: str | None = None) -> None:
    problems = []
    if len(password) < MIN_LENGTH:
        problems.append(f"at least {MIN_LENGTH} characters")
    if len(password) > MAX_LENGTH:
        problems.append(f"at most {MAX_LENGTH} characters")
    if password.strip() != password or not password.strip():
        problems.append("no leading or trailing spaces")
    if email and password.lower() == email.lower():
        problems.append("different from your email address")
    if problems:
        raise ValidationFailedError(
            "Password must be " + ", ".join(problems) + ".", code="auth.weak_password"
        )


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(24))


def burn_verification_time(password: str) -> None:
    """Spend a real verification's time when the account does not exist (no user enumeration)."""
    verify_password(_dummy_hash(), password)
