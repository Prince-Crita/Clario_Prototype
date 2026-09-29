"""The Finance Assistant (plan §18.3): what the Finance domain supplies to the shared runtime."""

from __future__ import annotations

from pathlib import Path

from clario.ai.context import AgentContext
from clario.ai.runtime.agent import AssistantSpec
from clario.ai.tools.base import Toolset
from clario.domains.finance.assistant.tools import TOOLS

INSTRUCTIONS = (Path(__file__).with_name("instructions.md")).read_text(encoding="utf-8")


def toolset(_: AgentContext) -> Toolset:
    return Toolset(TOOLS)


ASSISTANT = AssistantSpec(
    domain="finance",
    domain_name="Finance",
    display_name="Finance Assistant",
    instructions=INSTRUCTIONS,
    toolset_factory=toolset,
    suggested_questions=(
        "How are we doing this financial year?",
        "Which invoices are overdue?",
        "Who owes us the most?",
        "How did cash collection this month compare with last month?",
        "What are our biggest expenses this year?",
    ),
    tool_labels={t.name: t.label for t in TOOLS},
)
