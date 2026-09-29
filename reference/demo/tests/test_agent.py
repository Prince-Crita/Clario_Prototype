from __future__ import annotations

from clario.agent.instructions import AGENT_INSTRUCTION
from clario.tools.zoho_tools import ALL_TOOLS


QUESTION_TOOLS = [
    ("What were our sales this month?", "get_sales_summary"),
    ("Compare this month with last month.", "get_business_summary"),
    ("Which invoices are overdue?", "get_overdue_invoices"),
    ("Which customers owe us the most?", "get_customer_balances"),
    ("What were our biggest expenses?", "get_expense_summary"),
    ("Give me a business summary.", "get_business_summary"),
    ("What changed significantly this month?", "get_business_summary"),
    ("What should I pay attention to?", "get_business_summary"),
    ("Show top customers.", "get_top_customers"),
    ("Explain the biggest change.", "get_business_summary"),
    ("What about their payment history?", "get_customer_payments"),
]


def test_instruction_maps_mvp_questions_to_tools():
    for question, tool in QUESTION_TOOLS:
        assert tool in AGENT_INSTRUCTION, f"{tool} missing from instructions for {question!r}"


def test_agent_tool_list_covers_mvp():
    names = {fn.__name__ for fn in ALL_TOOLS}
    expected = {tool for _, tool in QUESTION_TOOLS}
    assert expected <= names


def test_instruction_forbids_hallucination():
    text = AGENT_INSTRUCTION.lower()
    assert "never invent" in text
    assert "must call a tool" in text
    assert "don't have enough data" in AGENT_INSTRUCTION
