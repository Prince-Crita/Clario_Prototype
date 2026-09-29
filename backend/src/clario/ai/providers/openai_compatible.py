"""The shared adapter for providers that speak the OpenAI chat-completions API (Groq, OpenRouter,
and most others). Everything provider-neutral lives here: the request body, retries, tool calls,
parsing and error typing. A provider subclass supplies only what differs: its base URL, headers,
extra body fields, and how it reports usage limits.

* 429: short waits are waited out and retried; a daily limit, or a wait longer than `max_wait`,
  raises `ProviderRateLimitedError` at once with the provider's own reset time and scope.
* 400 "tool call validation" / "failed to call a function": `MalformedToolCallError`, which the
  runtime recovers from (plan §21.4).
* Transport errors and 5xx: retried briefly, then `ProviderError`. Response bodies are logged
  without message content; the API key never is.
* Provider quirks (e.g. `reasoning` fields) stay here: only the answer text and tool calls leave.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Any, ClassVar

import httpx

from clario.ai.providers.base import (
    LimitScope,
    LLMRequest,
    LLMResponse,
    MalformedToolCallError,
    Message,
    ProviderError,
    ProviderRateLimitedError,
    ToolCall,
    Usage,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
MAX_WAIT_SECONDS = 10.0
MALFORMED = ("tool call validation", "failed to call a function", "tool_use_failed")


def _wire(message: Message) -> dict[str, Any]:
    wire: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        wire["tool_calls"] = [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in message.tool_calls
        ]
    if message.tool_call_id:
        wire["tool_call_id"] = message.tool_call_id
    return wire


class OpenAICompatibleProvider:
    name: str  # the LLMProvider protocol attribute; each subclass sets it
    label: ClassVar[str]  # for logs: "Groq", "OpenRouter"
    base_url: ClassVar[str]
    max_tokens_field: ClassVar[str] = "max_completion_tokens"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
        max_attempts: int = MAX_ATTEMPTS,
        max_wait: float = MAX_WAIT_SECONDS,
    ) -> None:
        self.model = model
        self._key = api_key
        self._timeout = httpx.Timeout(timeout)
        self._attempts = max_attempts  # the evaluation is more patient than a user
        self._max_wait = max_wait

    # ---------------------------------------------------------------- provider hooks

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}"}

    def _extra_body(self, request: LLMRequest) -> dict[str, Any]:
        return {}

    def _limit(self, response: httpx.Response) -> tuple[float | None, LimitScope | None]:
        """A 429's wait in seconds and whether a daily or per-minute limit was hit."""
        return _seconds(response.headers.get("retry-after")), None

    def _wait_after_success(self, response: httpx.Response, parsed: LLMResponse) -> float | None:
        """Seconds before another request this size would be accepted, if the provider says a
        limit is now exhausted; None otherwise."""
        return None

    # ---------------------------------------------------------------- shared behaviour

    def _body(self, request: LLMRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [_wire(m) for m in request.messages],
            "temperature": request.temperature,
            self.max_tokens_field: request.max_output_tokens,
        }
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": dict(t.parameters),
                    },
                }
                for t in request.tools
            ]
            body["tool_choice"] = "auto"
        return {**body, **self._extra_body(request)}

    async def complete(self, request: LLMRequest) -> LLMResponse:
        body = self._body(request)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout) as http:
            for attempt in range(1, self._attempts + 1):
                last = attempt == self._attempts
                try:
                    response = await http.post(
                        "/chat/completions", json=body, headers=self._headers()
                    )
                except httpx.TransportError as exc:
                    logger.warning(
                        "%s unreachable", self.label, extra={"error": type(exc).__name__}
                    )
                    if last:
                        raise ProviderError("provider unreachable") from None
                    await asyncio.sleep(attempt)
                    continue
                if response.status_code == 429:
                    retry_after, scope = self._limit(response)
                    too_long = retry_after is not None and retry_after > self._max_wait
                    if last or too_long or scope == "daily":  # waiting here would not help
                        logger.warning(
                            "%s usage limit reached",
                            self.label,
                            extra={"limit_scope": scope, "retry_after": retry_after},
                        )
                        raise ProviderRateLimitedError(retry_after=retry_after, scope=scope)
                    await asyncio.sleep(retry_after if retry_after is not None else attempt * 2)
                    continue
                if response.status_code == 400 and any(
                    m in response.text.lower() for m in MALFORMED
                ):
                    raise MalformedToolCallError(self._error_message(response))
                if response.status_code >= 500 and not last:
                    await asyncio.sleep(attempt)
                    continue
                if response.status_code >= 400:
                    logger.warning(
                        "%s request failed",
                        self.label,
                        extra={
                            "status": response.status_code,
                            "error": self._error_message(response),
                        },
                    )
                    raise ProviderError(f"HTTP {response.status_code}")
                parsed = self._parse(response.json())
                return replace(parsed, wait_before_next=self._wait_after_success(response, parsed))
        raise ProviderError("no response")

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            error = response.json().get("error") or {}
            return str(error.get("message") or error.get("code") or "")[:300]
        except ValueError:
            return response.text[:300]

    def _parse(self, payload: dict[str, Any]) -> LLMResponse:
        if isinstance(payload.get("error"), dict) and not payload.get("choices"):
            # Some gateways (OpenRouter) report an upstream failure inside a 200 response.
            logger.warning(
                "%s returned an error",
                self.label,
                extra={"error": str(payload["error"].get("message") or "")[:300]},
            )
            raise ProviderError("provider error")
        try:
            message = payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("unexpected response") from None
        calls = tuple(
            ToolCall(
                id=str(c.get("id") or f"call_{i}"),
                name=str((c.get("function") or {}).get("name") or ""),
                arguments=str((c.get("function") or {}).get("arguments") or "{}"),
            )
            for i, c in enumerate(message.get("tool_calls") or [])
        )
        usage = payload.get("usage") or {}
        return LLMResponse(
            text=str(message.get("content") or "").strip(),
            tool_calls=calls,
            usage=Usage(
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
            model=str(payload.get("model") or self.model),
        )

    async def available_models(self) -> set[str]:
        """The model ids this key can use."""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout) as http:
            response = await http.get("/models", headers=self._headers())
        response.raise_for_status()
        return {str(m.get("id")) for m in response.json().get("data") or []}


def _seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
