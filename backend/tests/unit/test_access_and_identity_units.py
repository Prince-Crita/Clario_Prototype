from __future__ import annotations

from datetime import timedelta

import pytest

from clario.core.errors import ValidationFailedError
from clario.platform.access.permissions import ROLE_PERMISSIONS, Permission, Role
from clario.platform.identity import passwords
from clario.platform.identity.ratelimit import SlidingWindowLimiter
from clario.platform.identity.service import LOCKOUT_MAX, _lockout_for
from clario.platform.identity.tokens import (
    cookie_name,
    csrf_token_for,
    csrf_valid,
    hash_token,
    new_session_token,
)

P = Permission
# The permission matrix from plan §13.2 — any change to roles must update this table deliberately.
EXPECTED = {
    Role.OWNER: {
        P.WORKSPACE_VIEW,
        P.FINANCE_VIEW,
        P.ASSISTANT_USE,
        P.INTEGRATIONS_MANAGE,
        P.MEMBERS_MANAGE,
    },
    Role.ADMIN: {P.WORKSPACE_VIEW, P.FINANCE_VIEW, P.ASSISTANT_USE, P.INTEGRATIONS_MANAGE},
    Role.MEMBER: {P.WORKSPACE_VIEW, P.FINANCE_VIEW, P.ASSISTANT_USE},
    Role.VIEWER: {P.WORKSPACE_VIEW, P.FINANCE_VIEW},
}


def test_permission_matrix_matches_plan() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)
    for role, expected in EXPECTED.items():
        assert ROLE_PERMISSIONS[role] == expected, role


def test_session_tokens_and_csrf() -> None:
    token_a, token_b = new_session_token(), new_session_token()
    assert token_a != token_b
    assert len(hash_token(token_a)) == 32
    csrf_a = csrf_token_for(hash_token(token_a), "secret" * 8)
    assert csrf_valid(token_a, csrf_a, "secret" * 8)
    assert not csrf_valid(token_b, csrf_a, "secret" * 8)  # bound to the session
    assert not csrf_valid(token_a, csrf_a, "other-secret" * 4)  # bound to the server secret
    assert not csrf_valid(token_a, None, "secret" * 8)
    assert cookie_name(secure=True) == "__Host-clario_session"
    assert cookie_name(secure=False) == "clario_session"


@pytest.mark.parametrize(
    ("password", "fragment"),
    [
        ("short", "at least 12"),
        (" leading space pw", "spaces"),
        ("person@example.com", "different from your email"),
    ],
)
def test_password_policy_rejects(password: str, fragment: str) -> None:
    with pytest.raises(ValidationFailedError, match=fragment):
        passwords.validate_password(password, email="person@example.com")


def test_password_hash_roundtrip() -> None:
    hashed = passwords.hash_password("a perfectly fine password")
    assert hashed.startswith("$argon2id$")
    assert passwords.verify_password(hashed, "a perfectly fine password")
    assert not passwords.verify_password(hashed, "wrong password here")
    assert not passwords.verify_password("not-a-hash", "anything")


def test_sliding_window_limiter() -> None:
    limiter = SlidingWindowLimiter(max_attempts=3, window_seconds=60)
    assert all(limiter.hit("ip", now=t) for t in (0, 1, 2))
    assert not limiter.hit("ip", now=3)
    assert limiter.hit("other-ip", now=3)
    assert limiter.hit("ip", now=61)  # first hit slid out of the window


def test_lockout_backoff_doubles_and_caps() -> None:
    assert _lockout_for(5) == timedelta(minutes=15)
    assert _lockout_for(6) == timedelta(minutes=30)
    assert _lockout_for(7) == timedelta(minutes=60)
    assert _lockout_for(50) == LOCKOUT_MAX
