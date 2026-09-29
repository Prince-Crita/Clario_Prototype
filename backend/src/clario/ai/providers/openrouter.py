"""OpenRouter: the OpenAI-compatible adapter plus OpenRouter's routing and usage limits.

* One key reaches many models; the model is `OPENROUTER_MODEL`. Requests with tools set
  `provider.require_parameters`, so OpenRouter only routes to endpoints that support tool calling.
* Limits: free models allow a small number of requests per minute and per day (more once credits
  are bought). A 429 carries `X-RateLimit-Reset` (epoch milliseconds), in the response headers or
  in `error.metadata.headers`, and a message naming the limit ("free-models-per-day"). An upstream
  provider can also be rate-limited; then OpenRouter gives no reset time and Clario holds briefly.
* Free endpoints may log prompts: use synthetic data until the data terms are agreed (R6).
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from clario.ai.providers.base import LimitScope, LLMRequest
from clario.ai.providers.openai_compatible import OpenAICompatibleProvider, _seconds

BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"
    label = "OpenRouter"
    base_url = BASE_URL
    max_tokens_field = "max_tokens"

    def _headers(self) -> dict[str, str]:
        return {**super()._headers(), "X-Title": "Clario"}  # app attribution, no user data

    def _extra_body(self, request: LLMRequest) -> dict[str, Any]:
        return {"provider": {"require_parameters": True}} if request.tools else {}

    def _limit(self, response: httpx.Response) -> tuple[float | None, LimitScope | None]:
        message = self._error_message(response).lower()
        retry_after = _seconds(response.headers.get("retry-after"))
        if retry_after is None:
            reset = response.headers.get("x-ratelimit-reset") or _metadata_header(
                response, "x-ratelimit-reset"
            )
            if (epoch_ms := _seconds(reset)) is not None:
                retry_after = max(epoch_ms / 1000 - time.time(), 0.0)
        scope: LimitScope | None = (
            "daily"
            if re.search(r"per[- ]day", message)
            else "minute"
            if re.search(r"per[- ]min", message)
            else None
        )
        return retry_after, scope


def _metadata_header(response: httpx.Response, name: str) -> str | None:
    """OpenRouter repeats limit headers inside the error body: error.metadata.headers."""
    try:
        headers = ((response.json().get("error") or {}).get("metadata") or {}).get("headers")
    except ValueError:
        return None
    if not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if str(key).lower() == name:
            return str(value)
    return None
