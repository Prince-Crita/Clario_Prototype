"""Single Clario Business Analysis Agent (Google ADK)."""

from __future__ import annotations

from typing import Any

from google.adk.agents import Agent

from clario.agent.instructions import AGENT_DESCRIPTION, AGENT_INSTRUCTION, AGENT_NAME
from clario.config import Settings, get_settings
from clario.tools.zoho_tools import ALL_TOOLS

# Groq rejects these on *inbound* assistant history (gpt-oss reasoning models).
_GROQ_UNSUPPORTED_ASSISTANT_KEYS = ("reasoning_content", "reasoning", "thinking_blocks")


def _strip_groq_unsupported_message_fields(messages: Any) -> Any:
    """Remove reasoning fields Groq does not accept on request message replay."""
    if not isinstance(messages, list):
        return messages
    cleaned: list[Any] = []
    for message in messages:
        if not isinstance(message, dict):
            cleaned.append(message)
            continue
        if message.get("role") != "assistant":
            cleaned.append(message)
            continue
        cleaned.append(
            {key: value for key, value in message.items() if key not in _GROQ_UNSUPPORTED_ASSISTANT_KEYS}
        )
    return cleaned


def resolve_model(settings: Settings):
    """Return an ADK model string or LiteLlm wrapper based on LLM_PROVIDER."""
    provider = settings.llm_provider.strip().lower()
    if provider == "groq":
        from google.adk.models.lite_llm import LiteLlm, LiteLLMClient

        class GroqSafeLiteLLMClient(LiteLLMClient):
            """LiteLLM client that strips Groq-unsupported assistant reasoning fields."""

            async def acompletion(self, model, messages, tools, **kwargs):  # noqa: ANN001
                return await super().acompletion(
                    model=model,
                    messages=_strip_groq_unsupported_message_fields(messages),
                    tools=tools,
                    **kwargs,
                )

            def completion(self, model, messages, tools, stream=False, **kwargs):  # noqa: ANN001
                return super().completion(
                    model=model,
                    messages=_strip_groq_unsupported_message_fields(messages),
                    tools=tools,
                    stream=stream,
                    **kwargs,
                )

        model_id = settings.groq_model
        if not model_id.startswith("groq/"):
            model_id = f"groq/{model_id}"
        kwargs: dict[str, Any] = {
            "model": model_id,
            "llm_client": GroqSafeLiteLLMClient(),
            # Ignore provider-specific params LiteLLM may not map for every Groq model.
            "drop_params": True,
        }
        # gpt-oss returns reasoning that ADK/LiteLLM replay as reasoning_content;
        # ask Groq not to include it when supported.
        if "gpt-oss" in model_id:
            kwargs["include_reasoning"] = False
        return LiteLlm(**kwargs)
    if provider == "gemini":
        return settings.gemini_model
    raise RuntimeError(
        f"Unsupported LLM_PROVIDER={settings.llm_provider!r}. Use 'groq' or 'gemini'."
    )


def build_agent() -> Agent:
    settings = get_settings()
    return Agent(
        name=AGENT_NAME,
        model=resolve_model(settings),
        description=AGENT_DESCRIPTION,
        instruction=AGENT_INSTRUCTION,
        tools=list(ALL_TOOLS),
    )


root_agent = None


def get_root_agent() -> Agent:
    global root_agent
    if root_agent is None:
        root_agent = build_agent()
    return root_agent
