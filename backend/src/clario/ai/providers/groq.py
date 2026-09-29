"""Groq (plan §20): the OpenAI-compatible adapter plus how Groq reports its usage limits.

Limits (measured 2026-09-28) are per Groq ORGANISATION, not per key: the headers report requests
per day (`x-ratelimit-*-requests`) and tokens per minute (`x-ratelimit-*-tokens`); tokens per DAY
appear only in a 429's message ("tokens per day (TPD): Limit 200000, Used …, Requested …"). The
wait reported to Clario is the LATEST of every exhausted limit: the 429's `retry-after` (else the
"try again in 2m19.968s" in the message), requests per day at zero, and tokens per minute below the
request's size. Successful answers report it too, so "available" is never assumed.
"""

from __future__ import annotations

import re

import httpx

from clario.ai.providers.base import LimitScope, LLMResponse
from clario.ai.providers.openai_compatible import (
    MAX_ATTEMPTS,
    MAX_WAIT_SECONDS,
    OpenAICompatibleProvider,
    _seconds,
)

BASE_URL = "https://api.groq.com/openai/v1"
__all__ = ["BASE_URL", "MAX_ATTEMPTS", "MAX_WAIT_SECONDS", "GroqProvider", "parse_duration"]


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    label = "Groq"
    base_url = BASE_URL

    def _limit(self, response: httpx.Response) -> tuple[float | None, LimitScope | None]:
        message = self._error_message(response).lower()
        retry_after = _seconds(response.headers.get("retry-after"))
        if retry_after is None and (found := re.search(r"try again in ([\d.hms]+)", message)):
            retry_after = parse_duration(found.group(1))
        scope: LimitScope | None = (
            "daily"
            if re.search(r"per day|\((?:tpd|rpd)\)", message)
            else "minute"
            if re.search(r"per minute|\((?:tpm|rpm)\)", message)
            else None
        )
        requested = re.search(r"requested (\d+)", message)  # the refused request's size
        needed = int(requested.group(1)) if requested else None
        return _exhausted_wait(response, needed, retry_after), scope

    def _wait_after_success(self, response: httpx.Response, parsed: LLMResponse) -> float | None:
        return _exhausted_wait(response, parsed.usage.input_tokens or None)


def _exhausted_wait(
    response: httpx.Response, needed_tokens: int | None, floor: float | None = None
) -> float | None:
    """The latest reset among the limits Groq's headers show exhausted, and `floor` (a 429's
    retry-after). None when nothing is exhausted."""
    waits = [floor] if floor is not None else []
    headers = response.headers

    def number(name: str) -> int | None:
        try:
            return int(float(headers[name]))
        except (KeyError, ValueError):
            return None

    requests_left = number("x-ratelimit-remaining-requests")
    if requests_left is not None and requests_left <= 0:
        waits.append(parse_duration(headers.get("x-ratelimit-reset-requests", "")) or 0.0)
    tokens_left = number("x-ratelimit-remaining-tokens")
    if tokens_left is not None and needed_tokens is not None and tokens_left < needed_tokens:
        waits.append(parse_duration(headers.get("x-ratelimit-reset-tokens", "")) or 0.0)
    return max(waits) if waits else None


_DURATION = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_UNIT_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}


def parse_duration(text: str) -> float | None:
    """Groq's durations: "8h42m3.2s", "2m19.968s", "607ms" → seconds."""
    parts = _DURATION.findall(text)
    return sum(float(n) * _UNIT_SECONDS[unit] for n, unit in parts) if parts else None
