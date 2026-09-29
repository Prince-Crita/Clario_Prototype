"""All SQL for users and sessions. Users are platform-global (not tenant-owned)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from clario.platform.identity.models import User, UserSession


def normalise_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(
        select(User).where(User.email == normalise_email(email), User.deleted_at.is_(None))
    )


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))


async def add_user(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    full_name: str,
    is_platform_admin: bool = False,
) -> User:
    user = User(
        email=normalise_email(email),
        password_hash=password_hash,
        full_name=full_name.strip(),
        is_platform_admin=is_platform_admin,
    )
    session.add(user)
    await session.flush()
    return user


async def add_session(session: AsyncSession, record: UserSession) -> UserSession:
    session.add(record)
    await session.flush()
    return record


async def get_session_and_user(
    session: AsyncSession, token_hash: bytes
) -> tuple[UserSession, User] | None:
    row = (
        await session.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.token_hash == token_hash, User.deleted_at.is_(None))
        )
    ).one_or_none()
    return (row[0], row[1]) if row else None


async def revoke_session(session: AsyncSession, session_id: uuid.UUID, at: datetime) -> None:
    await session.execute(
        update(UserSession)
        .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=at)
    )


async def revoke_user_sessions(
    session: AsyncSession, user_id: uuid.UUID, at: datetime, *, keep: uuid.UUID | None = None
) -> int:
    statement = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=at)
    )
    if keep is not None:
        statement = statement.where(UserSession.id != keep)
    result = await session.execute(statement)
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def count_active_sessions(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.absolute_expires_at > now,
            )
        )
        or 0
    )
