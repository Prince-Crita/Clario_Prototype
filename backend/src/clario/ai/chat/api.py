"""Assistant routes (plan §11.2, §26), under one connection:

    GET    …/connections/{c}/assistant                                   assistant info
    GET    …/connections/{c}/assistant/conversations                     your conversations
    POST   …/connections/{c}/assistant/conversations                     start one
    GET    …/connections/{c}/assistant/conversations/{id}                messages
    DELETE …/connections/{c}/assistant/conversations/{id}                delete
    POST   …/connections/{c}/assistant/conversations/{id}/messages       ask (runs the assistant)

All require `assistant.use`; conversations are private to their user. Answers are complete
(non-streaming) in the prototype.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, status

from clario.ai.chat import service
from clario.ai.chat.schemas import (
    AssistantInfo,
    AssistantStatus,
    ConversationDetail,
    ConversationList,
    ConversationSummary,
    Reply,
    SendMessage,
)
from clario.platform.access.permissions import Permission
from clario.platform.access.scopes import ConnectionScope
from clario.platform.connections.deps import connection_access
from clario.platform.conversations import repository as repo
from clario.platform.integrations.deps import RegistryDep
from clario.platform.web import ClientInfoDep, SessionDep, SettingsDep

router = APIRouter(
    prefix="/workspaces/{workspace_id}/connections/{connection_id}/assistant", tags=["assistant"]
)
CanChat = Annotated[ConnectionScope, Depends(connection_access(Permission.ASSISTANT_USE))]
ConversationId = Annotated[uuid.UUID, Path(description="Conversation id")]


def deps(request: Request, registry: RegistryDep, settings: SettingsDep) -> service.ChatDeps:
    state = request.app.state
    return service.ChatDeps(
        provider=state.llm_provider,
        registry=registry,
        settings=settings,
        limiter=state.chat_limiter,
        clock=state.sync.clock,
        status=state.provider_status,
    )


Deps = Annotated[service.ChatDeps, Depends(deps)]


@router.get("", response_model=AssistantInfo, summary="The assistant for this connection")
async def get_assistant(scope: CanChat, chat: Deps) -> AssistantInfo:
    spec = service.assistant_for(chat.registry, scope)
    limit = chat.status.limit()
    state = chat.status.state()
    return AssistantInfo(
        domain=spec.domain,
        display_name=spec.display_name,
        suggested_questions=list(spec.suggested_questions),
        available=chat.provider is not None,
        status=AssistantStatus(
            state="not_configured" if chat.provider is None else state,
            resets_in_seconds=limit.resets_in_seconds if limit else None,
            limit_scope=limit.scope if limit else None,
        ),
    )


@router.get("/conversations", response_model=ConversationList, summary="Your conversations")
async def list_conversations(scope: CanChat, session: SessionDep, chat: Deps) -> ConversationList:
    service.assistant_for(chat.registry, scope)
    return ConversationList(
        conversations=[service.summary(c) for c in await repo.list_for(session, scope)]
    )


@router.post(
    "/conversations",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation",
)
async def create_conversation(
    scope: CanChat, session: SessionDep, chat: Deps
) -> ConversationSummary:
    return service.summary(await service.create(session, chat.registry, scope))


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationDetail, summary="A conversation"
)
async def get_conversation(
    conversation_id: ConversationId, scope: CanChat, session: SessionDep, chat: Deps
) -> ConversationDetail:
    spec = service.assistant_for(chat.registry, scope)
    conversation = await service.get(session, scope, conversation_id)
    return ConversationDetail(
        **service.summary(conversation).model_dump(),
        messages=await service.transcript(session, conversation, dict(spec.tool_labels)),
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
async def delete_conversation(
    conversation_id: ConversationId, scope: CanChat, session: SessionDep, client: ClientInfoDep
) -> Response:
    await service.delete(session, scope, conversation_id, client)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=Reply,
    summary="Ask the assistant",
    responses={
        429: {"description": "Sending too quickly, or the AI usage limit is reached"},
        503: {"description": "Assistant unavailable or not configured"},
    },
)
async def send_message(
    conversation_id: ConversationId,
    body: SendMessage,
    scope: CanChat,
    session: SessionDep,
    chat: Deps,
) -> Reply:
    conversation, user, assistant, invocations, spec = await service.send(
        session, chat, scope, conversation_id, body.content
    )
    labels = dict(spec.tool_labels)
    return Reply(
        conversation=service.summary(conversation),
        user_message=service.message_out(user, [], labels),
        assistant_message=service.message_out(assistant, invocations, labels),
    )
