"""The agent loop (plan §18.2), Clario's own thin runtime (ADR-006).

    messages = [system(policy + domain instructions + context)] + history + user
    for each round (max LLM_MAX_TOOL_ROUNDS):
        response = provider.complete(messages, tools=the domain's toolset)
        tool calls → dispatch each through the toolset (server-side checks), append results, repeat
        text      → grounding guard → done
    rounds exhausted → a safe fallback answer

Malformed tool calls (the provider rejects the model's own call, seen in Phase 0): retried up to
twice, then the model is told what went wrong and which tools exist, once; every attempt is
recorded as a `rejected` invocation. Other provider errors propagate (the caller answers 503).
No state lives in the process: history comes from the database on every turn.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from clario.ai.context import AgentContext
from clario.ai.guards import grounding
from clario.ai.policy.base import system_prompt
from clario.ai.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MalformedToolCallError,
    Message,
    Usage,
)
from clario.ai.tools.base import Dispatched, ToolResult, Toolset, error
from clario.core.text import normalise_typography
from clario.platform.access.permissions import Permission

logger = logging.getLogger(__name__)

MALFORMED_RETRIES = 2
FALLBACK = "I couldn't complete that. Please try a narrower question."


@dataclass(frozen=True, slots=True)
class AssistantSpec:
    """What a domain supplies (plan §18.3)."""

    domain: str  # "finance"
    domain_name: str  # "Finance"
    display_name: str  # "Finance Assistant"
    instructions: str
    toolset_factory: Callable[[AgentContext], Toolset]
    suggested_questions: tuple[str, ...]
    tool_labels: Mapping[str, str] = field(default_factory=dict)  # for the "Based on …" line
    required_permission: Permission = Permission.ASSISTANT_USE


@dataclass(frozen=True, slots=True)
class Invocation:
    round: int
    call_id: str
    name: str
    dispatched: Dispatched


@dataclass(slots=True)
class TurnResult:
    text: str
    invocations: list[Invocation] = field(default_factory=list)
    rounds: int = 0
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    latency_ms: int = 0
    fallback: bool = False
    ungrounded: tuple[str, ...] = ()
    wait_before_next: float | None = None  # from the provider's last response (usage limits)

    @property
    def grounding_flag(self) -> bool:
        return bool(self.ungrounded)


def _malformed(round_no: int, attempt: int, reason: str) -> Invocation:
    result = error("tool.malformed_call", reason[:300])
    return Invocation(
        round_no,
        f"malformed-{round_no}-{attempt}",
        "(malformed call)",
        Dispatched("(malformed call)", None, result, "rejected", 0),
    )


async def run_turn(
    provider: LLMProvider,
    spec: AssistantSpec,
    ctx: AgentContext,
    history: Sequence[Message],
    user_message: str,
    *,
    max_rounds: int,
    evidence: Sequence[str] = (),
) -> TurnResult:
    """One user turn. `evidence` = earlier tool results of this conversation (for grounding)."""
    started = time.perf_counter()
    toolset = spec.toolset_factory(ctx)
    messages: list[Message] = [
        Message(
            "system", system_prompt(ctx, spec.display_name, spec.domain_name, spec.instructions)
        ),
        *history,
        Message("user", user_message),
    ]
    turn = TurnResult(text="")
    input_tokens = output_tokens = 0

    for round_no in range(1, max_rounds + 1):
        turn.rounds = round_no
        response = await _complete(provider, toolset, messages, turn, round_no)
        if response is None:
            turn.text, turn.fallback = FALLBACK, True
            break
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens
        turn.model = response.model or provider.model
        turn.wait_before_next = response.wait_before_next
        if not response.tool_calls:
            # Plain hyphens and spaces, so "INV-1011" copied from an answer finds the invoice.
            text = normalise_typography(response.text).strip()
            turn.text = text or FALLBACK
            turn.fallback = not text
            break
        messages.append(Message("assistant", response.text, tool_calls=response.tool_calls))
        for call in response.tool_calls:
            dispatched = await toolset.dispatch(ctx, call.name, call.arguments)
            turn.invocations.append(Invocation(round_no, call.id, call.name, dispatched))
            messages.append(Message("tool", dispatched.result.for_model(), tool_call_id=call.id))
    else:
        turn.text, turn.fallback = FALLBACK, True

    turn.usage = Usage(input_tokens, output_tokens)
    turn.latency_ms = int((time.perf_counter() - started) * 1000)
    if not turn.fallback:
        results = [*evidence, *(i.dispatched.result.for_model() for i in turn.invocations)]
        report = grounding.check(turn.text, results)
        turn.ungrounded = report.ungrounded
        if report.ungrounded:
            logger.warning(
                "Answer contains figures not found in tool results",
                extra={
                    "conversation_id": str(ctx.conversation_id),
                    "figures": list(report.ungrounded),
                },
            )
    return turn


async def _complete(
    provider: LLMProvider,
    toolset: Toolset,
    messages: list[Message],
    turn: TurnResult,
    round_no: int,
) -> LLMResponse | None:
    """One completion with malformed-tool-call recovery. None = give up with the fallback."""
    corrected = False
    attempt = 0
    while True:
        attempt += 1
        try:
            return await provider.complete(LLMRequest(messages=list(messages), tools=toolset.specs))
        except MalformedToolCallError as exc:
            turn.invocations.append(_malformed(round_no, attempt, exc.reason))
            if attempt <= MALFORMED_RETRIES:
                continue
            if corrected:
                return None
            corrected = True
            messages.append(
                Message(
                    "user",
                    f"(System note) The previous tool call was invalid: {exc.reason[:200]}. "
                    f"Call one of: {', '.join(toolset.names)} with valid JSON arguments, "
                    "or answer without tools.",
                )
            )


def sources_of(turn: TurnResult, toolset_label: Callable[[str], str]) -> list[str]:
    """Human labels of the tools that returned data this turn (for the "Based on …" line)."""
    labels: list[str] = []
    for invocation in turn.invocations:
        if invocation.dispatched.status == "ok":
            label = toolset_label(invocation.name)
            if label not in labels:
                labels.append(label)
    return labels


def as_of_of(results: Sequence[ToolResult]) -> str | None:
    stamps = [r.as_of for r in results if r.as_of]
    return min(stamps) if stamps else None
