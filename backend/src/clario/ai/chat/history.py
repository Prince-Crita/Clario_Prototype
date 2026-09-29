"""Rebuild the model's view of a conversation from the database (plan §18.2).

Only THIS conversation's messages and tool invocations are loaded; there is no process-local state.
Budget: the last `MAX_TURNS` user turns. Each earlier assistant turn is replayed with its tool calls
and compact results, so follow-ups ("them", "that invoice") resolve from what tools returned.
Failed turns (the question and its failed answer) and malformed calls are skipped.
"""

from __future__ import annotations

import json
from collections import defaultdict

from clario.ai.providers.base import Message, ToolCall
from clario.ai.tools.base import MAX_RESULT_CHARS
from clario.platform.conversations.models import (
    ChatMessage,
    MessageRole,
    MessageStatus,
    ToolInvocation,
)

MAX_TURNS = 8


def _compact(result: dict[str, object]) -> str:
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
    return (
        text
        if len(text) <= MAX_RESULT_CHARS
        else text[: MAX_RESULT_CHARS - 40] + '…","truncated":true}'
    )


def build(
    messages: list[ChatMessage], invocations: list[ToolInvocation]
) -> tuple[list[Message], list[str]]:
    """→ (history messages, every earlier tool result as JSON for the grounding guard)."""
    by_message: dict[object, list[ToolInvocation]] = defaultdict(list)
    for invocation in invocations:
        by_message[invocation.message_id].append(invocation)

    user_positions = [i for i, m in enumerate(messages) if m.role == MessageRole.USER]
    start = user_positions[-MAX_TURNS] if len(user_positions) > MAX_TURNS else 0

    window = messages[start:]
    history: list[Message] = []
    evidence: list[str] = []
    for position, message in enumerate(window):
        if message.role == MessageRole.USER:
            reply = window[position + 1] if position + 1 < len(window) else None
            answered = (
                reply is not None
                and reply.role == MessageRole.ASSISTANT
                and reply.status == MessageStatus.COMPLETE
            )
            if answered:  # an unanswered question is asked again, not replayed twice
                history.append(Message("user", message.content))
            continue
        if message.status != MessageStatus.COMPLETE:
            continue
        rounds: dict[int, list[ToolInvocation]] = defaultdict(list)
        for invocation in by_message.get(message.id, []):
            if invocation.tool_name != "(malformed call)":
                rounds[invocation.round].append(invocation)
        for round_no in sorted(rounds):
            calls = rounds[round_no]
            history.append(
                Message(
                    "assistant",
                    "",
                    tool_calls=tuple(
                        ToolCall(c.call_id, c.tool_name, json.dumps(c.arguments or {}))
                        for c in calls
                    ),
                )
            )
            for c in calls:
                text = _compact(c.result)
                history.append(Message("tool", text, tool_call_id=c.call_id))
                evidence.append(text)
        history.append(Message("assistant", message.content))
    return history, evidence
