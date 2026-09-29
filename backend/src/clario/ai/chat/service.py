"""Chat use cases (plan §26): conversations under one connection, one assistant per domain.

Enforcement (plan §21.2):
  1. Route: a conversation is created under exactly one connection and is private to its user;
     every read and post re-checks workspace + user + connection (repository scoping), so a
     conversation cannot be moved to another scope.
  2. Assistant resolution: the server maps the connection's domain to its AssistantSpec; the
     client cannot choose a domain or tools.
  3-4. Toolset and data scope: `Toolset.dispatch` and the domain's scoped repositories.
Plus a per-user rate limit, a message length limit, and one turn at a time per conversation.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from clario.ai.chat import history as history_builder
from clario.ai.chat.schemas import ConversationSummary, MessageOut
from clario.ai.context import AgentContext, OtherModule
from clario.ai.providers.base import LLMProvider, ProviderError, ProviderRateLimitedError
from clario.ai.providers.status import ProviderStatus, UsageLimit
from clario.ai.runtime.agent import AssistantSpec, run_turn
from clario.core.dates import fiscal_year_label, today_in
from clario.core.errors import (
    NotFoundError,
    RateLimitedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from clario.platform.access.scopes import ConnectionScope
from clario.platform.audit.service import AuditAction, record
from clario.platform.connections import repository as connection_repo
from clario.platform.connections.service import connection_profile
from clario.platform.conversations import repository as repo
from clario.platform.conversations.models import (
    ChatMessage,
    Conversation,
    MessageRole,
    MessageStatus,
    ToolInvocation,
)
from clario.platform.identity.ratelimit import SlidingWindowLimiter
from clario.platform.integrations import service as catalog
from clario.platform.integrations.contract import Availability
from clario.platform.integrations.registry import Registry
from clario.platform.web import ClientInfo
from clario.platform.workspaces import repository as workspace_repo
from clario.settings import Settings

logger = logging.getLogger(__name__)

UNAVAILABLE = "The assistant is temporarily unavailable; your dashboard data is unaffected."
LIMIT_REACHED = "AI usage limit reached. Your dashboard data is unaffected."
CONVERSATION_NOT_FOUND = "Conversation not found."


@dataclass(frozen=True, slots=True)
class ChatDeps:
    provider: LLMProvider | None
    registry: Registry
    settings: Settings
    limiter: SlidingWindowLimiter
    clock: Callable[[], datetime]
    status: ProviderStatus


def assistant_for(registry: Registry, scope: ConnectionScope) -> AssistantSpec:
    domain = registry.domain(scope.domain)
    spec = domain.assistant if domain else None
    if not isinstance(spec, AssistantSpec):
        raise NotFoundError("This system has no assistant.", code="assistant.not_available")
    return spec


async def build_context(
    session: AsyncSession,
    deps: ChatDeps,
    scope: ConnectionScope,
    conversation_id: uuid.UUID | None,
) -> AgentContext:
    """The server-built context of a turn (plan §18.2)."""
    connection = await connection_repo.get_live(session, scope, scope.connection_id)
    if connection is None:
        raise NotFoundError("Connection not found.", code="connection.not_found")
    tz, fy_month = connection_profile(connection, scope)
    today = today_in(tz, deps.clock())
    manifest = deps.registry.manifest(scope.integration_key)
    others = tuple(
        OtherModule(
            e.manifest.name, e.domain_name, e.manifest.availability is Availability.AVAILABLE
        )
        for e in await catalog.workspace_catalog(session, deps.registry, scope)
        if e.manifest.key != scope.integration_key
    )
    return AgentContext(
        scope=scope,
        session=session,
        conversation_id=conversation_id,
        workspace_name=await workspace_repo.name_for(session, scope),
        system_name=manifest.name if manifest else scope.integration_key,
        organisation=connection.external_account_name or "your organisation",
        currency=(connection.settings or {}).get("currency") or scope.base_currency,
        timezone=str(tz),
        today=today,
        fiscal_year_start_month=fy_month,
        fiscal_year=fiscal_year_label(today, fy_month),
        other_modules=others,
        clock=deps.clock,
    )


# ---------------------------------------------------------------- conversations


def summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        last_message_at=conversation.last_message_at,
    )


async def create(session: AsyncSession, registry: Registry, scope: ConnectionScope) -> Conversation:
    spec = assistant_for(registry, scope)
    conversation = Conversation(
        workspace_id=scope.workspace_id,
        connection_id=scope.connection_id,
        user_id=scope.user_id,
        domain=spec.domain,
    )
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    return conversation


async def get(
    session: AsyncSession, scope: ConnectionScope, conversation_id: uuid.UUID, *, lock: bool = False
) -> Conversation:
    conversation = await repo.get(session, scope, conversation_id, lock=lock)
    if conversation is None:
        raise NotFoundError(CONVERSATION_NOT_FOUND, code="conversation.not_found")
    return conversation


def message_out(
    message: ChatMessage, invocations: list[ToolInvocation], labels: dict[str, str]
) -> MessageOut:
    sources: list[str] = []
    stamps: list[str] = []
    for invocation in invocations:
        if invocation.status == "ok":
            label = labels.get(invocation.tool_name, invocation.tool_name)
            if label not in sources:
                sources.append(label)
            if isinstance(invocation.result.get("as_of"), str):
                stamps.append(invocation.result["as_of"])
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        status=message.status,
        created_at=message.created_at,
        sources=sources,
        as_of=datetime.fromisoformat(min(stamps)) if stamps else None,
    )


async def transcript(
    session: AsyncSession, conversation: Conversation, labels: dict[str, str]
) -> list[MessageOut]:
    messages = await repo.messages(session, conversation)
    invocations = await repo.invocations(session, conversation, [m.id for m in messages])
    by_message: dict[uuid.UUID, list[ToolInvocation]] = {}
    for invocation in invocations:
        by_message.setdefault(invocation.message_id, []).append(invocation)
    return [message_out(m, by_message.get(m.id, []), labels) for m in messages]


async def delete(
    session: AsyncSession, scope: ConnectionScope, conversation_id: uuid.UUID, client: ClientInfo
) -> None:
    conversation = await get(session, scope, conversation_id)
    conversation.deleted_at = datetime.now(conversation.created_at.tzinfo)
    record(
        session,
        AuditAction.CONVERSATION_DELETED,
        actor_user_id=scope.user_id,
        workspace_id=scope.workspace_id,
        target_type="conversation",
        target_id=conversation.id,
        client=client,
    )


# ---------------------------------------------------------------- a turn


def limit_reached(limit: UsageLimit | None) -> RateLimitedError:
    """429 with the provider's own reset time (seconds, relative, so the browser's clock can't
    skew the countdown) and whether it is the daily or per-minute limit."""
    return RateLimitedError(
        LIMIT_REACHED,
        code=ProviderRateLimitedError.code,
        extra={
            "resets_in_seconds": limit.resets_in_seconds if limit else None,
            "limit_scope": limit.scope if limit else None,
        },
    )


async def send(
    session: AsyncSession,
    deps: ChatDeps,
    scope: ConnectionScope,
    conversation_id: uuid.UUID,
    content: str,
) -> tuple[Conversation, ChatMessage, ChatMessage, list[ToolInvocation], AssistantSpec]:
    """Run one user turn and store it. Raises 429 / 503 with safe messages."""
    text = content.strip()
    if not text:
        raise ValidationFailedError("Type a question first.", code="assistant.empty_message")
    if not deps.limiter.hit(str(scope.user_id)):
        raise RateLimitedError(
            "You're sending messages quickly. Wait a moment and try again.",
            code="assistant.rate_limited",
        )
    spec = assistant_for(deps.registry, scope)
    if deps.provider is None:
        raise ServiceUnavailableError(
            "The assistant isn't configured on this server.", code="assistant.not_configured"
        )
    if limit := deps.status.limit():  # known to be refused: don't spend a call, keep the question
        raise limit_reached(limit)
    conversation = await get(session, scope, conversation_id, lock=True)
    earlier = await repo.messages(session, conversation)
    history, evidence = history_builder.build(
        earlier, await repo.invocations(session, conversation, [m.id for m in earlier])
    )

    now = deps.clock()
    user = ChatMessage(
        conversation_id=conversation.id,
        workspace_id=scope.workspace_id,
        role=MessageRole.USER,
        content=text,
        status=MessageStatus.COMPLETE,
    )
    session.add(user)
    if not conversation.title:
        conversation.title = text if len(text) <= 60 else text[:57].rstrip() + "…"
    repo.touch(conversation, now)
    await session.flush()

    ctx = await build_context(session, deps, scope, conversation.id)
    try:
        turn = await run_turn(
            deps.provider,
            spec,
            ctx,
            history,
            text,
            max_rounds=deps.settings.llm_max_tool_rounds,
            evidence=evidence,
        )
    except ProviderRateLimitedError as exc:
        # Not an outage: nothing is stored (the request rolls back) and the question goes back
        # to the box with the reset time.
        deps.status.record_limit(exc.retry_after, exc.scope)
        raise limit_reached(deps.status.limit()) from None
    except ProviderError as exc:
        logger.warning("Assistant provider failed", extra={"error_code": exc.code})
        failed = ChatMessage(
            conversation_id=conversation.id,
            workspace_id=scope.workspace_id,
            role=MessageRole.ASSISTANT,
            content="",
            status=MessageStatus.FAILED,
            provider=deps.provider.name,
            model=deps.provider.model,
        )
        session.add(failed)
        await session.commit()  # keep the question; the error is raised after
        raise ServiceUnavailableError(UNAVAILABLE, code=exc.code) from None

    deps.status.record_success(turn.wait_before_next)
    assistant = ChatMessage(
        conversation_id=conversation.id,
        workspace_id=scope.workspace_id,
        role=MessageRole.ASSISTANT,
        content=turn.text,
        status=MessageStatus.COMPLETE,
        provider=deps.provider.name,
        model=turn.model or deps.provider.model,
        input_tokens=turn.usage.input_tokens,
        output_tokens=turn.usage.output_tokens,
        latency_ms=turn.latency_ms,
        grounding_flag=turn.grounding_flag,
    )
    session.add(assistant)
    await session.flush()
    invocations = [
        ToolInvocation(
            message_id=assistant.id,
            workspace_id=scope.workspace_id,
            call_id=i.call_id[:64],
            round=i.round,
            tool_name=i.name[:100],
            arguments=i.dispatched.arguments,
            result=i.dispatched.result.as_dict(),
            status=i.dispatched.status,
            duration_ms=i.dispatched.duration_ms,
        )
        for i in turn.invocations
    ]
    session.add_all(invocations)
    repo.touch(conversation, deps.clock())
    await session.flush()
    await session.refresh(user)
    await session.refresh(assistant)
    return conversation, user, assistant, invocations, spec
