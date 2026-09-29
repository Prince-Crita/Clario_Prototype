"""All SQL for conversations. Every read is scoped to the connection AND the owning user: a
conversation is private to the person who started it."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from clario.platform.access.scopes import ConnectionScope
from clario.platform.conversations.models import ChatMessage, Conversation, ToolInvocation


def _mine(scope: ConnectionScope) -> list[ColumnElement[bool]]:
    return [
        Conversation.workspace_id == scope.workspace_id,
        Conversation.connection_id == scope.connection_id,
        Conversation.user_id == scope.user_id,
        Conversation.deleted_at.is_(None),
    ]


async def list_for(
    session: AsyncSession, scope: ConnectionScope, limit: int = 50
) -> list[Conversation]:
    rows = await session.scalars(
        select(Conversation)
        .where(*_mine(scope), Conversation.last_message_at.is_not(None))  # none asked yet: hidden
        .order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc())
        .limit(limit)
    )
    return list(rows)


async def get(
    session: AsyncSession, scope: ConnectionScope, conversation_id: uuid.UUID, *, lock: bool = False
) -> Conversation | None:
    statement = select(Conversation).where(*_mine(scope), Conversation.id == conversation_id)
    if lock:
        statement = statement.with_for_update()  # one turn at a time per conversation
    return await session.scalar(statement)


async def messages(session: AsyncSession, conversation: Conversation) -> list[ChatMessage]:
    rows = await session.scalars(
        select(ChatMessage)
        .where(
            ChatMessage.conversation_id == conversation.id,
            ChatMessage.workspace_id == conversation.workspace_id,
        )
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return list(rows)


async def invocations(
    session: AsyncSession, conversation: Conversation, message_ids: list[uuid.UUID]
) -> list[ToolInvocation]:
    if not message_ids:
        return []
    rows = await session.scalars(
        select(ToolInvocation)
        .where(
            ToolInvocation.workspace_id == conversation.workspace_id,
            ToolInvocation.message_id.in_(message_ids),
        )
        .order_by(ToolInvocation.created_at, ToolInvocation.id)
    )
    return list(rows)


def touch(conversation: Conversation, now: datetime) -> None:
    conversation.last_message_at = now


async def purge_connection(session: AsyncSession, scope: ConnectionScope) -> None:
    """Disconnect: conversations hold the connection's financial data, so they go with it."""
    await session.execute(
        delete(Conversation).where(
            Conversation.workspace_id == scope.workspace_id,
            Conversation.connection_id == scope.connection_id,
        )
    )
