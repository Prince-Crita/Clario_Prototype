"""Provider-neutral LLM interface (plan §20). Domains, tools and the runtime depend only on this;
each provider (Groq now) is one adapter file that maps it to its own wire format."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text from the model; the toolset validates it


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()  # assistant messages that call tools
    tool_call_id: str | None = None  # tool messages: which call this answers


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: Mapping[str, Any]  # JSON Schema of the arguments


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class LLMRequest:
    messages: Sequence[Message]
    tools: Sequence[ToolSpec] = ()
    temperature: float = 0.2
    max_output_tokens: int = 1024


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    # Seconds before the provider will accept another request of this size, when a limit it
    # reported is exhausted (e.g. no requests left today); None = nothing reported exhausted.
    wait_before_next: float | None = None


class ProviderError(Exception):
    """The provider could not answer (after its own retries). `code` is safe to show."""

    code = "assistant.unavailable"


LimitScope = Literal["daily", "minute"]


class ProviderRateLimitedError(ProviderError):
    """The provider's usage limit is reached. `retry_after` (seconds until it accepts this request
    again) and `scope` come from the provider's own response when it states them."""

    code = "assistant.limit_reached"

    def __init__(
        self,
        message: str = "rate limited",
        *,
        retry_after: float | None = None,
        scope: LimitScope | None = None,
    ) -> None:
        self.retry_after = retry_after
        self.scope = scope
        super().__init__(message)


class MalformedToolCallError(ProviderError):
    """The provider rejected the model's own tool call (Groq: HTTP 400 'tool call validation').
    Recoverable: the runtime retries, then corrects the model (plan §21.4)."""

    code = "assistant.malformed_tool_call"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class LLMProvider(Protocol):
    name: str
    model: str

    async def complete(self, request: LLMRequest) -> LLMResponse: ...
