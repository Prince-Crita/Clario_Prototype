"""ADK runner wrapper used by the FastAPI chat endpoint."""

from __future__ import annotations

import os
import uuid
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from clario.agent.agent import get_root_agent
from clario.config import get_settings
from clario.logging import get_logger

logger = get_logger("clario.agent.runner")

APP_NAME = "clario"
DEFAULT_USER_ID = "local-user"


class ClarioRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        if self.settings.groq_api_key:
            os.environ.setdefault("GROQ_API_KEY", self.settings.groq_api_key)
        if self.settings.google_api_key:
            os.environ.setdefault("GOOGLE_API_KEY", self.settings.google_api_key)
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=get_root_agent(),
            app_name=APP_NAME,
            session_service=self.session_service,
        )

    async def ensure_session(self, session_id: str | None, user_id: str = DEFAULT_USER_ID) -> str:
        sid = session_id or str(uuid.uuid4())
        existing = await self.session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=sid
        )
        if existing is None:
            await self.session_service.create_session(
                app_name=APP_NAME, user_id=user_id, session_id=sid
            )
        return sid

    async def ask(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str = DEFAULT_USER_ID,
    ) -> dict[str, Any]:
        if not self.settings.llm_ready():
            provider = self.settings.llm_provider.strip().lower()
            if provider == "groq":
                raise RuntimeError(
                    "GROQ_API_KEY is not set. Add a Groq API key to .env before starting the agent."
                )
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Add a Gemini API key to .env before starting the agent."
            )
        sid = await self.ensure_session(session_id, user_id=user_id)
        content = types.Content(role="user", parts=[types.Part(text=message)])
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=sid,
            new_message=content,
        ):
            function_calls = []
            try:
                function_calls = event.get_function_calls() or []
            except Exception:
                function_calls = []
            for call in function_calls:
                tool_calls.append({"tool": call.name, "args": dict(call.args or {})})
                logger.info("Agent called tool %s", call.name)

            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        text_parts.append(part.text)

        answer = "".join(text_parts).strip()
        if not answer:
            answer = (
                "I don't have enough data in Zoho Books to answer that reliably. "
                "The agent did not return a final response."
            )
        return {
            "session_id": sid,
            "answer": answer,
            "tool_calls": tool_calls,
        }

    async def clear(self, session_id: str, user_id: str = DEFAULT_USER_ID) -> None:
        try:
            await self.session_service.delete_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("Could not delete session %s: %s", session_id, exc)


_runner: ClarioRunner | None = None


def get_runner() -> ClarioRunner:
    global _runner
    if _runner is None:
        _runner = ClarioRunner()
    return _runner
