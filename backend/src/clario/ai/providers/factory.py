"""`get_provider(settings)`: the configured LLM provider, or None when AI is not configured.

Adding a provider: an adapter implementing `LLMProvider` (for an OpenAI-compatible API, subclass
`OpenAICompatibleProvider` and supply only its URL, headers and limit reporting), its settings, and
one branch here. Nothing else changes: the runtime, tools, domains and UI only see `LLMProvider`.
"""

from __future__ import annotations

from pydantic import SecretStr

from clario.ai.providers.base import LLMProvider
from clario.ai.providers.groq import GroqProvider
from clario.ai.providers.openrouter import OpenRouterProvider
from clario.settings import Settings


def _key(secret: SecretStr | None) -> str | None:
    value = secret.get_secret_value().strip() if secret is not None else ""
    return value or None


def get_provider(settings: Settings) -> LLMProvider | None:
    timeout = settings.llm_timeout_seconds
    if settings.llm_provider == "groq" and (key := _key(settings.groq_api_key)):
        return GroqProvider(key, settings.groq_model, timeout=timeout)
    if settings.llm_provider == "openrouter" and (key := _key(settings.openrouter_api_key)):
        return OpenRouterProvider(key, settings.openrouter_model, timeout=timeout)
    return None
