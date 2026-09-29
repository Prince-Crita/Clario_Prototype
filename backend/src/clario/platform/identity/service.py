"""Authentication use cases: login, session validation, logout, password change (plan §12).

Security properties:
  * Same error and similar timing for unknown email, wrong password and disabled account.
  * Per-account lockout with exponential backoff (5 failures → 15 min, doubling, max 24 h),
    persisted even though the request fails; plus a best-effort per-IP limiter.
  * Sessions: idle timeout (sliding) and absolute timeout; revocable; hashed at rest.
  * Password change revokes every other session of the user.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.dates import utc_now
from clario.core.errors import AuthenticationError, RateLimitedError, ValidationFailedError
from clario.platform.audit.service import AuditAction, record
from clario.platform.identity import passwords
from clario.platform.identity import repository as repo
from clario.platform.identity.models import UserSession, UserStatus
from clario.platform.identity.ratelimit import SlidingWindowLimiter
from clario.platform.identity.tokens import hash_token, new_session_token
from clario.platform.web import ClientInfo
from clario.settings import Settings

LOCKOUT_THRESHOLD = 5
LOCKOUT_BASE = timedelta(minutes=15)
LOCKOUT_MAX = timedelta(hours=24)
TOUCH_INTERVAL = timedelta(minutes=5)  # limit last_seen writes to one per 5 minutes per session

INVALID_CREDENTIALS = "Incorrect email or password."
TOO_MANY_ATTEMPTS = "Too many sign-in attempts. Try again in a few minutes."


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: uuid.UUID
    session_id: uuid.UUID
    email: str
    full_name: str
    is_platform_admin: bool
    token_hash: bytes


@dataclass(frozen=True, slots=True)
class LoginResult:
    token: str
    auth: AuthContext
    expires_at: datetime


def _lockout_for(failures: int) -> timedelta:
    doublings = max(failures - LOCKOUT_THRESHOLD, 0)
    return min(LOCKOUT_BASE * (1 << min(doublings, 16)), LOCKOUT_MAX)


async def login(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    client: ClientInfo,
    ip_limiter: SlidingWindowLimiter,
) -> LoginResult:
    now = utc_now()
    normalised = repo.normalise_email(email)

    if not ip_limiter.hit(client.ip or "unknown"):
        raise RateLimitedError(TOO_MANY_ATTEMPTS, code="auth.too_many_attempts")

    user = await repo.get_user_by_email(session, normalised)

    async def fail(reason: str) -> None:
        record(
            session,
            AuditAction.LOGIN_FAILED,
            actor_user_id=user.id if user else None,
            target_type="user",
            target_id=user.id if user else None,
            client=client,
            details={"email": normalised, "reason": reason},
        )
        await session.commit()  # persist the counter and audit row even though we raise

    if user is None:
        passwords.burn_verification_time(password)
        await fail("unknown_email")
        raise AuthenticationError(INVALID_CREDENTIALS, code="auth.invalid_credentials")

    if user.locked_until is not None and user.locked_until > now:
        await fail("locked")
        raise RateLimitedError(TOO_MANY_ATTEMPTS, code="auth.too_many_attempts")

    if (
        not passwords.verify_password(user.password_hash, password)
        or user.status != UserStatus.ACTIVE
    ):
        user.failed_login_count += 1
        if user.failed_login_count >= LOCKOUT_THRESHOLD:
            user.locked_until = now + _lockout_for(user.failed_login_count)
        await fail("disabled" if user.status != UserStatus.ACTIVE else "invalid_password")
        raise AuthenticationError(INVALID_CREDENTIALS, code="auth.invalid_credentials")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)

    token = new_session_token()
    idle = timedelta(hours=settings.session_idle_hours)
    absolute_expires = now + timedelta(days=settings.session_absolute_days)
    user_session = await repo.add_session(
        session,
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            last_seen_at=now,
            idle_expires_at=min(now + idle, absolute_expires),
            absolute_expires_at=absolute_expires,
            ip=client.ip,
            user_agent=client.user_agent,
        ),
    )
    record(
        session,
        AuditAction.LOGIN_SUCCEEDED,
        actor_user_id=user.id,
        target_type="session",
        target_id=user_session.id,
        client=client,
    )
    return LoginResult(
        token=token,
        auth=AuthContext(
            user_id=user.id,
            session_id=user_session.id,
            email=user.email,
            full_name=user.full_name,
            is_platform_admin=user.is_platform_admin,
            token_hash=user_session.token_hash,
        ),
        expires_at=absolute_expires,
    )


async def authenticate(session: AsyncSession, settings: Settings, token: str | None) -> AuthContext:
    """Resolve a session cookie to an AuthContext, or raise 401."""
    if not token:
        raise AuthenticationError(code="auth.required")
    found = await repo.get_session_and_user(session, hash_token(token))
    if found is None:
        raise AuthenticationError(code="auth.required")
    user_session, user = found
    now = utc_now()
    if (
        user_session.revoked_at is not None
        or user_session.absolute_expires_at <= now
        or user_session.idle_expires_at <= now
    ):
        raise AuthenticationError(
            "Your session has ended. Sign in again.", code="auth.session_expired"
        )
    if user.status != UserStatus.ACTIVE:
        raise AuthenticationError(code="auth.required")

    if now - user_session.last_seen_at >= TOUCH_INTERVAL:
        user_session.last_seen_at = now
        user_session.idle_expires_at = min(
            now + timedelta(hours=settings.session_idle_hours), user_session.absolute_expires_at
        )
    return AuthContext(
        user_id=user.id,
        session_id=user_session.id,
        email=user.email,
        full_name=user.full_name,
        is_platform_admin=user.is_platform_admin,
        token_hash=user_session.token_hash,
    )


async def logout(session: AsyncSession, auth: AuthContext, client: ClientInfo) -> None:
    await repo.revoke_session(session, auth.session_id, utc_now())
    record(
        session,
        AuditAction.LOGOUT,
        actor_user_id=auth.user_id,
        target_type="session",
        target_id=auth.session_id,
        client=client,
    )


async def change_password(
    session: AsyncSession,
    auth: AuthContext,
    *,
    current_password: str,
    new_password: str,
    client: ClientInfo,
) -> int:
    """Change the signed-in user's password; returns how many other sessions were revoked."""
    user = await repo.get_user(session, auth.user_id)
    if user is None:
        raise AuthenticationError(code="auth.required")
    if not passwords.verify_password(user.password_hash, current_password):
        raise ValidationFailedError(
            "Your current password is incorrect.", code="auth.wrong_password"
        )
    if current_password == new_password:
        raise ValidationFailedError(
            "Choose a password you have not used here.", code="auth.password_unchanged"
        )
    passwords.validate_password(new_password, email=user.email)
    user.password_hash = passwords.hash_password(new_password)
    revoked = await repo.revoke_user_sessions(session, user.id, utc_now(), keep=auth.session_id)
    record(
        session,
        AuditAction.PASSWORD_CHANGED,
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        client=client,
        details={"other_sessions_revoked": revoked},
    )
    return revoked
