"""Shared plumbing for CLI commands: a unit-of-work DB session, password input, error output."""

from __future__ import annotations

import asyncio
import getpass
import sys
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.db import Database
from clario.core.errors import ClarioError
from clario.settings import get_settings


def run_in_session[T](operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Run `operation` in one transaction on DATABASE_URL: commit on success, else roll back."""

    async def runner() -> T:
        database = Database(get_settings().database_url, pool_size=1, max_overflow=0)
        try:
            async with database.sessions() as session:
                try:
                    result = await operation(session)
                    await session.commit()
                    return result
                except BaseException:
                    await session.rollback()
                    raise
        finally:
            await database.dispose()

    return asyncio.run(runner())


def read_password(*, from_stdin: bool, prompt: str = "Password") -> str:
    """Never accept passwords as CLI arguments (shell history, process lists)."""
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass(f"{prompt} (min 12 characters): ")
    if getpass.getpass(f"Repeat {prompt.lower()}: ") != first:
        raise SystemExit("error: passwords do not match")
    return first


def guarded(command: Callable[[], int]) -> int:
    """Print ClarioError details as a one-line error instead of a traceback."""
    try:
        return command()
    except ClarioError as exc:
        print(f"error: {exc.detail} [{exc.code}]", file=sys.stderr)
        return 1
