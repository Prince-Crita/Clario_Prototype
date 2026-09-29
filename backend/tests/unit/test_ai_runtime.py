"""The AI runtime without a database (plan §32 "AI runtime"): toolset enforcement, the agent loop
with a scripted FakeProvider, malformed-call recovery, grounding, and the Groq adapter."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, date, datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from pydantic import Field

from clario.ai.context import AgentContext, OtherModule
from clario.ai.guards import grounding
from clario.ai.policy.base import system_prompt
from clario.ai.providers import openai_compatible as adapter_module
from clario.ai.providers.base import (
    LLMRequest,
    MalformedToolCallError,
    Message,
    ProviderError,
    ProviderRateLimitedError,
    ToolSpec,
)
from clario.ai.providers.factory import get_provider
from clario.ai.providers.fake import FakeProvider, call, say
from clario.ai.providers.groq import GroqProvider, parse_duration
from clario.ai.providers.openrouter import OpenRouterProvider
from clario.ai.providers.status import ProviderStatus, UsageLimit
from clario.ai.runtime.agent import FALLBACK, AssistantSpec, run_turn
from clario.ai.tools.base import Tool, ToolArgs, ToolResult, Toolset, ToolsetError
from clario.domains.finance.assistant.spec import ASSISTANT
from clario.domains.finance.assistant.tools import TOOLS
from clario.platform.access.permissions import Permission, Role, permissions_for
from clario.platform.access.scopes import ConnectionScope
from tests.support import make_settings

GROQ = "https://api.groq.com/openai/v1"


def context(role: Role = Role.MEMBER) -> AgentContext:
    scope = ConnectionScope(
        workspace_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=role,
        permissions=permissions_for(role),
        timezone=ZoneInfo("Asia/Kolkata"),
        base_currency="INR",
        fiscal_year_start_month=4,
        connection_id=uuid.uuid4(),
        integration_key="zoho-books",
        domain="finance",
    )
    return AgentContext(
        scope=scope,
        session=cast(Any, None),
        conversation_id=None,
        workspace_name="Alpha Traders",
        system_name="Zoho Books",
        organisation="Crita Creative LLP",
        currency="INR",
        timezone="Asia/Kolkata",
        today=date(2026, 9, 25),
        fiscal_year_start_month=4,
        fiscal_year="FY 2026-27",
        other_modules=(OtherModule("Veloce Inventory", "Inventory", False),),
        clock=lambda: datetime(2026, 9, 25, tzinfo=UTC),
    )


class RevenueArgs(ToolArgs):
    period: str = Field("fy_to_date")


async def revenue(_: AgentContext, args: RevenueArgs) -> ToolResult:
    return ToolResult(status="ok", data={"revenue": "728540"}, display={"revenue": "₹7,28,540"})


async def boom(_: AgentContext, __: RevenueArgs) -> ToolResult:
    raise RuntimeError("database password is hunter2")


def toolset() -> Toolset:
    return Toolset(
        [
            Tool(
                "get_revenue", "Revenue.", RevenueArgs, Permission.FINANCE_VIEW, revenue, "Revenue"
            ),
            Tool("explode", "Fails.", RevenueArgs, Permission.FINANCE_VIEW, boom),
            Tool(
                "admin_only", "Needs manage.", RevenueArgs, Permission.INTEGRATIONS_MANAGE, revenue
            ),
        ]
    )


SPEC = AssistantSpec(
    domain="finance",
    domain_name="Finance",
    display_name="Finance Assistant",
    instructions="Finance rules.",
    toolset_factory=lambda _: toolset(),
    suggested_questions=(),
)


# ---------------------------------------------------------------- toolset (plan §19.2)


async def test_unknown_tools_are_rejected() -> None:
    result = await toolset().dispatch(context(), "get_inventory", "{}")
    assert result.status == "rejected"
    assert result.result.code == "tool.unavailable"
    assert "get_revenue" in (result.result.message or "")


async def test_arguments_cannot_carry_identity_or_unknown_fields() -> None:
    result = await toolset().dispatch(context(), "get_revenue", json.dumps({"workspace_id": "x"}))
    assert (result.status, result.result.code) == ("rejected", "tool.invalid_arguments")
    not_json = await toolset().dispatch(context(), "get_revenue", "[1, 2]")
    assert not_json.status == "rejected"


def test_toolsets_refuse_identity_fields_at_construction() -> None:
    class Leaky(ToolArgs):
        workspace_id: str

    with pytest.raises(ToolsetError, match="identity"):
        Toolset([Tool("leaky", "x", Leaky, Permission.FINANCE_VIEW, revenue)])


async def test_permissions_are_checked_per_tool() -> None:
    result = await toolset().dispatch(context(Role.MEMBER), "admin_only", "{}")
    assert (result.status, result.result.code) == ("rejected", "tool.forbidden")
    allowed = await toolset().dispatch(context(Role.ADMIN), "admin_only", "{}")
    assert allowed.status == "ok"


async def test_failures_never_leak_internal_messages() -> None:
    result = await toolset().dispatch(context(), "explode", "{}")
    assert (result.status, result.result.code) == ("error", "tool.failed")
    assert "hunter2" not in result.result.for_model()


def test_finance_toolset_is_well_formed() -> None:
    finance = Toolset(TOOLS)  # constructing it checks every argument model
    names = {t.name for t in TOOLS}
    assert names == {
        "get_financial_overview",
        "get_profit_and_loss",
        "get_cash_movement",
        "get_receivables",
        "get_customer_summary",
        "find_invoices",
        "get_expense_breakdown",
        "get_gst_position",
        "get_action_items",
        "compare_periods",
        "get_data_freshness",
    }
    for spec in finance.specs:
        assert spec.parameters["additionalProperties"] is False
        assert "title" not in json.dumps(spec.parameters)
    assert all(t.label for t in TOOLS)
    assert ASSISTANT.tool_labels["get_receivables"] == "Receivables"


# ---------------------------------------------------------------- the loop (plan §18.2, §21.4)


async def test_a_turn_calls_tools_then_answers() -> None:
    provider = FakeProvider(
        [call("get_revenue", '{"period": "fy_to_date"}'), say("Revenue is ₹7,28,540 this year.")]
    )
    turn = await run_turn(provider, SPEC, context(), [], "What's our revenue?", max_rounds=6)
    assert turn.text == "Revenue is ₹7,28,540 this year."
    assert [i.name for i in turn.invocations] == ["get_revenue"]
    assert turn.grounding_flag is False
    second = provider.requests[1].messages
    assert second[-1].role == "tool"
    assert "₹7,28,540" in second[-1].content
    system = provider.requests[0].messages[0].content
    assert "Alpha Traders" in system
    assert "Veloce Inventory (Inventory, coming soon)" in system
    assert {t.name for t in provider.requests[0].tools} == {"get_revenue", "explode", "admin_only"}


async def test_answers_use_plain_hyphens_and_spaces() -> None:
    provider = FakeProvider([say("Invoice INV‑1011 is overdue by 21 days: −₹53,400.")])
    turn = await run_turn(provider, SPEC, context(), [], "Which invoice?", max_rounds=6)
    assert turn.text == "Invoice INV-1011 is overdue by 21 days: −₹53,400."


async def test_ungrounded_figures_are_flagged() -> None:
    provider = FakeProvider([call("get_revenue"), say("Revenue is ₹9,99,999.")])
    turn = await run_turn(provider, SPEC, context(), [], "Revenue?", max_rounds=6)
    assert turn.ungrounded == ("₹9,99,999",)
    assert turn.grounding_flag is True


async def test_malformed_tool_calls_are_retried_then_corrected() -> None:
    bad = MalformedToolCallError("Tool call validation failed: missing arguments")
    provider = FakeProvider([bad, bad, bad, call("get_revenue"), say("Revenue is ₹7,28,540.")])
    turn = await run_turn(provider, SPEC, context(), [], "Revenue?", max_rounds=6)
    assert turn.text == "Revenue is ₹7,28,540."
    rejected = [i for i in turn.invocations if i.dispatched.status == "rejected"]
    assert len(rejected) == 3
    correction = provider.requests[3].messages[-1]
    assert correction.role == "user"
    assert "previous tool call was invalid" in correction.content
    assert "get_revenue" in correction.content


async def test_persistent_malformed_calls_end_with_the_fallback() -> None:
    bad = MalformedToolCallError("Failed to call a function")
    turn = await run_turn(FakeProvider([bad] * 5), SPEC, context(), [], "Revenue?", max_rounds=6)
    assert (turn.text, turn.fallback) == (FALLBACK, True)


async def test_rounds_are_limited() -> None:
    turn = await run_turn(
        FakeProvider([call("get_revenue")] * 10), SPEC, context(), [], "Loop", max_rounds=3
    )
    assert (turn.rounds, turn.text, turn.fallback) == (3, FALLBACK, True)
    assert len(turn.invocations) == 3


async def test_provider_errors_propagate() -> None:
    with pytest.raises(ProviderError):
        await run_turn(
            FakeProvider([ProviderError("down")]), SPEC, context(), [], "Hi", max_rounds=6
        )


async def test_history_and_policy_reach_the_model() -> None:
    provider = FakeProvider([say("Client A.")])
    history = [
        Message("user", "Who owes us the most?"),
        Message("assistant", "Client A owes ₹23,965."),
    ]
    await run_turn(
        provider, SPEC, context(), history, "How much have we billed them?", max_rounds=6
    )
    sent = provider.requests[0].messages
    assert [m.role for m in sent] == ["system", "user", "assistant", "user"]
    assert "Every figure must come from a tool result" in sent[0].content
    assert sent[0].content.rstrip().endswith("Finance rules.")


def test_system_prompt_names_the_workspace_and_boundaries() -> None:
    prompt = system_prompt(context(), "Finance Assistant", "Finance", "x")
    assert 'workspace "Alpha Traders"' in prompt
    assert "only help with Alpha Traders's finance from Zoho Books" in prompt


# ---------------------------------------------------------------- grounding (plan §21.4)


@pytest.mark.parametrize(
    ("answer", "ungrounded"),
    [
        ("Net loss was −₹6,48,028 (−89% margin).", ()),
        ("You lost ₹6,48,028 this year.", ()),  # sign may differ in words
        ("That's about ₹6.48 lakh.", ()),
        ("INV‑00016 is ₹7,412 overdue, 89 %.", ()),  # typographic characters
        ("Revenue is ₹7,00,000.", ("₹7,00,000",)),
        ("Margin is 90%.", ("90%",)),
    ],
)
def test_grounding_compares_values_not_strings(answer: str, ungrounded: tuple[str, ...]) -> None:
    evidence = [
        {
            "display": {"net": "−₹6,48,028", "margin": "−89%"},
            "data": {"net": "-648028", "margin": "-88.95", "balance": "7412"},
        }
    ]
    assert grounding.check(answer, evidence).ungrounded == ungrounded


# ---------------------------------------------------------------- Groq adapter (plan §20)


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr(adapter_module.asyncio, "sleep", instant)


REQUEST = LLMRequest(
    messages=[Message("system", "s"), Message("user", "Revenue?")],
    tools=[ToolSpec("get_revenue", "Revenue.", {"type": "object", "properties": {}})],
)


@respx.mock
async def test_groq_maps_requests_and_responses() -> None:
    route = respx.post(f"{GROQ}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "reasoning": "hidden thoughts",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {"name": "get_revenue", "arguments": "{}"},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 9},
            },
        )
    )
    response = await GroqProvider("gsk_test", "openai/gpt-oss-120b").complete(REQUEST)
    assert response.tool_calls[0].name == "get_revenue"
    assert (response.usage.input_tokens, response.usage.output_tokens) == (120, 9)
    assert "hidden thoughts" not in response.text
    body = json.loads(route.calls.last.request.content)
    assert body["tool_choice"] == "auto"
    assert body["tools"][0]["function"]["name"] == "get_revenue"
    assert route.calls.last.request.headers["authorization"] == "Bearer gsk_test"


@respx.mock
async def test_groq_errors_are_typed() -> None:
    route = respx.post(f"{GROQ}/chat/completions")
    route.mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "Tool call validation failed: bad args"}}
        )
    )
    with pytest.raises(MalformedToolCallError, match="validation failed"):
        await GroqProvider("k", "m").complete(REQUEST)
    route.mock(return_value=httpx.Response(429, headers={"retry-after": "1"}, json={}))
    with pytest.raises(ProviderRateLimitedError):
        await GroqProvider("k", "m").complete(REQUEST)
    assert route.call_count == 1 + 3
    route.mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    assert (await GroqProvider("k", "m").complete(REQUEST)).text == "ok"
    route.mock(return_value=httpx.Response(401, json={"error": {"message": "invalid key"}}))
    with pytest.raises(ProviderError):
        await GroqProvider("k", "m").complete(REQUEST)


@respx.mock
async def test_groq_daily_limit_fails_fast_with_its_own_reset_time() -> None:
    body = {
        "error": {
            "message": "Rate limit reached for model `m` on tokens per day (TPD): Limit 200000, "
            "Used 198019, Requested 2305. Please try again in 8h42m10.5s.",
            "code": "rate_limit_exceeded",
        }
    }
    route = respx.post(f"{GROQ}/chat/completions")
    route.mock(return_value=httpx.Response(429, json=body))  # no retry-after header: body time
    with pytest.raises(ProviderRateLimitedError) as raised:
        await GroqProvider("k", "m").complete(REQUEST)
    assert route.call_count == 1  # a daily limit is not waited out
    assert (raised.value.retry_after, raised.value.scope) == (31330.5, "daily")
    route.mock(return_value=httpx.Response(429, headers={"retry-after": "140"}, json=body))
    with pytest.raises(ProviderRateLimitedError) as raised:
        await GroqProvider("k", "m").complete(REQUEST)
    assert raised.value.retry_after == 140  # the header wins when present
    assert parse_duration("607ms") == 0.607


def test_provider_status_is_never_assumed_available() -> None:
    clock = [1000.0]
    status = ProviderStatus(now=lambda: clock[0])
    assert (status.state(), status.limit()) == ("unconfirmed", None)  # nothing known yet
    status.record_limit(255.4, "daily")
    assert (status.state(), status.limit()) == ("limit_reached", UsageLimit(256, "daily"))
    clock[0] += 255.4
    # The wait is over, but only a real response can say the next question will get through.
    assert (status.state(), status.limit()) == ("unconfirmed", None)
    status.record_success(None)
    assert status.state() == "available"
    status.record_success(42.0)  # answered, but its headers show a limit now exhausted
    assert status.limit() == UsageLimit(42, None)
    clock[0] += 42
    status.record_limit(None, None)  # a 429 without any reset time: brief hold, no countdown
    assert status.limit() == UsageLimit(None, None)


@respx.mock
async def test_groq_wait_is_the_latest_of_every_exhausted_limit() -> None:
    # The shape Groq returned on 2026-09-28: the daily token limit is only in the message.
    body = {
        "error": {
            "message": "Rate limit reached ... on tokens per day (TPD): Limit 200000, "
            "Used 198712, Requested 1876. Please try again in 4m14.016s."
        }
    }
    limits = {
        "x-ratelimit-remaining-requests": "923",
        "x-ratelimit-reset-requests": "1h50m52.8s",
        "x-ratelimit-remaining-tokens": "8000",
        "x-ratelimit-reset-tokens": "1ms",
    }
    route = respx.post(f"{GROQ}/chat/completions")
    route.mock(
        return_value=httpx.Response(429, headers={"retry-after": "255", **limits}, json=body)
    )
    with pytest.raises(ProviderRateLimitedError) as raised:
        await GroqProvider("k", "m").complete(REQUEST)
    assert (raised.value.retry_after, raised.value.scope) == (255, "daily")
    exhausted = {**limits, "x-ratelimit-remaining-requests": "0"}  # and no requests left today
    route.mock(
        return_value=httpx.Response(429, headers={"retry-after": "255", **exhausted}, json=body)
    )
    with pytest.raises(ProviderRateLimitedError) as raised:
        await GroqProvider("k", "m").complete(REQUEST)
    assert raised.value.retry_after == pytest.approx(6652.8)  # the later of the two
    ok = {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 2300}}
    tight = {**limits, "x-ratelimit-remaining-tokens": "1200", "x-ratelimit-reset-tokens": "38.5s"}
    route.mock(return_value=httpx.Response(200, headers=tight, json=ok))
    answer = await GroqProvider("k", "m").complete(REQUEST)
    assert answer.wait_before_next == 38.5  # answered, but the next call this size wouldn't be
    route.mock(return_value=httpx.Response(200, headers=limits, json=ok))
    assert (await GroqProvider("k", "m").complete(REQUEST)).wait_before_next is None


OPENROUTER = "https://openrouter.ai/api/v1"


@respx.mock
async def test_openrouter_uses_the_shared_adapter_with_its_own_routing() -> None:
    route = respx.post(f"{OPENROUTER}/chat/completions")
    route.mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "vendor/model:free",
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning": "x",
                            "tool_calls": [
                                {"id": "c1", "function": {"name": "get_revenue", "arguments": "{}"}}
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 900, "completion_tokens": 12},
            },
        )
    )
    response = await OpenRouterProvider("sk-or-test", "vendor/model:free").complete(REQUEST)
    assert [c.name for c in response.tool_calls] == ["get_revenue"]
    sent = route.calls.last.request
    body = json.loads(sent.content)
    assert body["provider"] == {"require_parameters": True}  # only tool-capable endpoints
    assert body["max_tokens"] == REQUEST.max_output_tokens
    assert "max_completion_tokens" not in body
    assert sent.headers["authorization"] == "Bearer sk-or-test"
    assert sent.headers["x-title"] == "Clario"


@respx.mock
async def test_openrouter_daily_limit_uses_its_reported_reset() -> None:
    reset_ms = int((time.time() + 3 * 3600) * 1000)
    respx.post(f"{OPENROUTER}/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={
                "error": {
                    "code": 429,
                    "message": "Rate limit exceeded: free-models-per-day.",
                    "metadata": {"headers": {"X-RateLimit-Reset": str(reset_ms)}},
                }
            },
        )
    )
    with pytest.raises(ProviderRateLimitedError) as raised:
        await OpenRouterProvider("k", "m").complete(REQUEST)
    assert raised.value.scope == "daily"
    assert raised.value.retry_after == pytest.approx(3 * 3600, abs=5)


def test_the_factory_builds_the_configured_provider() -> None:
    groq = get_provider(make_settings(groq_api_key="gsk_x"))
    assert isinstance(groq, GroqProvider)
    chosen = make_settings(
        llm_provider="openrouter", openrouter_api_key="sk-or-x", openrouter_model="vendor/m"
    )
    provider = get_provider(chosen)
    assert isinstance(provider, OpenRouterProvider)
    assert (provider.name, provider.model) == ("openrouter", "vendor/m")
    assert get_provider(make_settings(llm_provider="openrouter")) is None  # no key: not set up
