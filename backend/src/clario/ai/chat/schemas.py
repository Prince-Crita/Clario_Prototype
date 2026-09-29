"""Assistant API contracts (plan §11.2, §26)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MAX_MESSAGE_CHARS = 4000


class AssistantStatus(BaseModel):
    """What the AI provider's own responses last reported (never guessed). `unconfirmed`: nothing
    known yet, or a limit's reset time has passed; the next question's real response decides."""

    state: Literal["available", "limit_reached", "unconfirmed", "not_configured"]
    resets_in_seconds: int | None = Field(
        None, description="Seconds until questions are accepted again, from the provider's reply"
    )
    limit_scope: Literal["daily", "minute"] | None = None


class AssistantInfo(BaseModel):
    domain: str
    display_name: str
    suggested_questions: list[str]
    available: bool = Field(description="False when no AI provider is configured on the server")
    status: AssistantStatus


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    last_message_at: datetime | None


class ConversationList(BaseModel):
    conversations: list[ConversationSummary]


class MessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    status: Literal["complete", "failed"]
    created_at: datetime
    sources: list[str] = Field(default_factory=list, description='For "Based on …" (assistant)')
    as_of: datetime | None = Field(None, description="Data freshness of the figures used")


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]


class SendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class Reply(BaseModel):
    conversation: ConversationSummary
    user_message: MessageOut
    assistant_message: MessageOut
