"""Shared FastAPI dependencies for every feature layer (platform, domains, integrations).

Lives in `platform` (not `api`) so feature modules can depend on it without importing the
composition root.

`get_session` is the unit of work for a request: commit when the handler succeeds, roll back on
any exception. Repositories receive this session; route handlers never run SQL themselves.
Services that must persist something *despite* raising (e.g. a failed-login counter) commit
explicitly before raising.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.db import Database
from clario.settings import Settings


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async with database.sessions() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


@dataclass(frozen=True, slots=True)
class ClientInfo:
    """Who is calling, for audit logs and rate limits. `ip` honours uvicorn proxy_headers."""

    ip: str | None
    user_agent: str | None


def get_client_info(request: Request) -> ClientInfo:
    user_agent = request.headers.get("user-agent")
    return ClientInfo(
        ip=request.client.host if request.client else None,
        user_agent=user_agent[:500] if user_agent else None,
    )


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DatabaseDep = Annotated[Database, Depends(get_database)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
ClientInfoDep = Annotated[ClientInfo, Depends(get_client_info)]
