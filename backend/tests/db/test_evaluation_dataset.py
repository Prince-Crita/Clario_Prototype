# ruff: noqa: E501  (the call table reads best one per line)
"""The evaluation dataset is sound (plan §32): the Finance tools return the hand-derived figures in
`clario.domains.finance.testing.evaluation`, and every figure an evaluation case expects is in
some tool result. So when the live evaluation fails, the model is wrong, never the data.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI

from clario.ai.chat import service
from clario.ai.tools.base import Toolset
from clario.domains.finance.assistant.tools import TOOLS
from clario.platform.identity.ratelimit import SlidingWindowLimiter
from tests.ai_eval.cases import CASES, normalise
from tests.support import Factory, fixture_connection

pytestmark = pytest.mark.db

CALLS: list[tuple[str, dict[str, Any]]] = [
    ("get_financial_overview", {}),
    ("get_profit_and_loss", {"period": "fy_to_date", "by_month": True}),
    ("get_profit_and_loss", {"period": "last_quarter"}),
    ("get_profit_and_loss", {"period": "this_quarter"}),
    ("get_profit_and_loss", {"period": "last_fy"}),
    ("get_cash_movement", {"period": "fy_to_date"}),
    ("get_cash_movement", {"period": "custom", "start_date": "2026-07-01", "end_date": "2026-07-31"}),
    ("get_receivables", {}),
    ("get_customer_summary", {"party": "Northwind"}),
    ("get_customer_summary", {"party": "Bluefin"}),
    ("get_customer_summary", {"party": "Kestrel"}),
    ("find_invoices", {"number": "INV-1009"}),
    ("find_invoices", {"period": "last_month"}),
    ("get_expense_breakdown", {"period": "fy_to_date"}),
    ("get_gst_position", {}),
    ("get_action_items", {}),
    ("compare_periods", {"metric": "collected", "period_a": "this_month", "period_b": "last_month"}),
    ("compare_periods", {"metric": "revenue", "period_a": "this_quarter", "period_b": "last_quarter"}),
    ("get_data_freshness", {}),
]  # fmt: skip


async def test_the_tools_return_the_hand_derived_figures(db_app: FastAPI, factory: Factory) -> None:
    scope = await fixture_connection(
        factory, db_app, "owner@eval.test", "TEST Evaluation", "evaluation"
    )
    deps = service.ChatDeps(
        provider=None,
        registry=db_app.state.registry,
        settings=db_app.state.settings,
        limiter=SlidingWindowLimiter(1, 1),
        clock=db_app.state.sync.clock,
        status=db_app.state.provider_status,
    )
    toolset = Toolset(TOOLS)
    results: dict[str, dict[str, Any]] = {}
    async with factory.database.sessions() as session:
        ctx = await service.build_context(session, deps, scope, None)
        for name, args in CALLS:
            dispatched = await toolset.dispatch(ctx, name, json.dumps(args))
            assert dispatched.status in ("ok", "no_data"), (name, dispatched.result)
            results[f"{name} {json.dumps(args)}"] = dispatched.result.as_dict()

    def display(name: str, args: dict[str, Any] | None = None) -> dict[str, str]:
        shown: dict[str, str] = results[f"{name} {json.dumps(args or {})}"]["display"]
        return shown

    pnl = display("get_profit_and_loss", {"period": "fy_to_date", "by_month": True})
    assert (pnl["revenue"], pnl["gross_margin"], pnl["net_pnl"], pnl["net_margin"]) == (
        "₹11,40,000",
        "80%",
        "−₹97,500",
        "−9%",
    )
    assert display("get_profit_and_loss", {"period": "last_quarter"})["net_pnl"] == "−₹83,000"
    assert display("get_profit_and_loss", {"period": "last_fy"})["revenue"] == "₹85,000"
    assert display("get_cash_movement", {"period": "fy_to_date"})["collected"] == "₹9,70,100"
    receivables = display("get_receivables")
    assert (receivables["outstanding"], receivables["overdue"], receivables["overdue_count"]) == (
        "₹4,16,400",
        "₹2,04,000",
        "5",
    )
    assert display("get_financial_overview")["cash_on_hand"].startswith("₹2,50,000 (balance, ")
    assert display("get_customer_summary", {"party": "Northwind"})["collected"] == "₹7,13,600"
    assert display("get_customer_summary", {"party": "Bluefin"})["billed_lifetime"] == "₹3,48,100"
    kestrel = results['get_customer_summary {"party": "Kestrel"}']
    assert kestrel["code"] == "finance.ambiguous_client"
    assert display("get_gst_position")["net_payable"] == "₹30,600"

    evidence = normalise(json.dumps(results, ensure_ascii=False))
    for case in CASES:
        for item in case.figures:
            assert any(alt in evidence for alt in item.split("|")), (case.id, item)
