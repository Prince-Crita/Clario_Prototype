"""`FakeProvider`: a scripted LLM for tests and offline development (plan §32).

Each step is either a response or an exception. A step may also be a function of the request,
so a test can answer based on what the runtime sent (e.g. the tool results). Every request is
recorded for assertions.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from clario.ai.providers.base import LLMRequest, LLMResponse, ToolCall

Step = LLMResponse | Exception | Callable[[LLMRequest], LLMResponse]


def say(text: str) -> LLMResponse:
    return LLMResponse(text=text, model="fake")


def call(name: str, arguments: str = "{}", call_id: str | None = None) -> LLMResponse:
    return LLMResponse(
        text="", tool_calls=(ToolCall(call_id or f"call_{name}", name, arguments),), model="fake"
    )


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, steps: Sequence[Step] = ()) -> None:
        self.steps = list(steps)
        self.requests: list[LLMRequest] = []

    def script(self, *steps: Step) -> None:
        self.steps.extend(steps)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self.steps:
            return say("(no scripted answer)")
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, LLMResponse):
            return step
        return step(request)
