"""Phase 9 exit criteria: the FakeProvider suite and scope enforcement (plan §21.2, §32).

The Finance tools run against the golden dataset (the director's PDF figures) and must return the
same numbers as the dashboard. The model is a scripted FakeProvider (no network).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from clario.ai.chat import service
from clario.ai.providers.base import (
    LLMRequest,
    LLMResponse,
    MalformedToolCallError,
    ProviderError,
    ProviderRateLimitedError,
)
from clario.ai.providers.fake import FakeProvider, call, say
from clario.ai.tools.base import Toolset
from clario.domains.finance.assistant.tools import TOOLS
from clario.platform.access.permissions import Role
from clario.platform.access.scopes import ConnectionScope
from clario.platform.identity.ratelimit import SlidingWindowLimiter
from tests.support import Factory, golden_connection, login

pytestmark = pytest.mark.db

OWNER = "director@alpha.test"


@pytest.fixture
async def golden(factory: Factory, db_app: FastAPI) -> ConnectionScope:
    return await golden_connection(factory, db_app, OWNER)


@pytest.fixture
def fake(db_app: FastAPI) -> FakeProvider:
    provider = FakeProvider()
    db_app.state.llm_provider = provider
    return provider


class Chat:
    def __init__(self, client: AsyncClient, csrf: str, scope: ConnectionScope) -> None:
        self.client, self.csrf = client, csrf
        self.base = (
            f"/api/v1/workspaces/{scope.workspace_id}/connections/{scope.connection_id}/assistant"
        )

    async def start(self) -> str:
        response = await self.client.post(
            f"{self.base}/conversations", headers={"X-CSRF-Token": self.csrf}
        )
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    async def ask(self, conversation: str, text: str, expect: int = 200) -> dict[str, Any]:
        response = await self.client.post(
            f"{self.base}/conversations/{conversation}/messages",
            headers={"X-CSRF-Token": self.csrf},
            json={"content": text},
        )
        assert response.status_code == expect, response.text
        body: dict[str, Any] = response.json()
        return body


@pytest.fixture
async def chat(golden: ConnectionScope, make_client: Callable[[], AsyncClient]) -> Chat:
    client = make_client()
    return Chat(client, await login(client, OWNER), golden)


def tool_result(request: LLMRequest) -> dict[str, Any]:
    last = request.messages[-1]
    assert last.role == "tool"
    result: dict[str, Any] = json.loads(last.content)
    return result


# ---------------------------------------------------------------- a full turn


async def test_a_question_is_answered_from_the_dashboard_figures(
    chat: Chat, fake: FakeProvider, factory: Factory
) -> None:
    def answer(request: LLMRequest) -> LLMResponse:
        display = tool_result(request)["display"]
        figure = {k: v.split(" (")[0] for k, v in display.items()}  # "₹7,28,540 (accrual, …)"
        return say(
            f"Revenue is {figure['revenue']} this financial year, "
            f"with a net loss of {figure['net_pnl']}."
        )

    fake.script(call("get_financial_overview"), answer)
    conversation = await chat.start()
    reply = await chat.ask(conversation, "How are we doing this year?")

    message = reply["assistant_message"]
    assert (
        message["content"]
        == "Revenue is ₹7,28,540 this financial year, with a net loss of −₹6,48,028."
    )
    assert message["sources"] == ["Overview"]
    assert message["as_of"] is not None
    assert reply["conversation"]["title"] == "How are we doing this year?"
    rows = await factory.sql(
        "SELECT role, status, grounding_flag, provider FROM core.messages ORDER BY created_at"
    )
    assert [tuple(r) for r in rows or []] == [
        ("user", "complete", False, None),
        ("assistant", "complete", False, "fake"),
    ]
    invocations = await factory.sql(
        "SELECT tool_name, status, result->'display'->>'revenue' FROM core.tool_invocations"
    )
    assert [tuple(r) for r in invocations or []] == [
        ("get_financial_overview", "ok", "₹7,28,540 (accrual, FY 2026-27 to date)")
    ]

    detail = await chat.client.get(f"{chat.base}/conversations/{conversation}")
    assert [m["role"] for m in detail.json()["messages"]] == ["user", "assistant"]
    assert detail.json()["messages"][1]["sources"] == ["Overview"]


async def test_follow_ups_see_earlier_tool_results(chat: Chat, fake: FakeProvider) -> None:
    fake.script(
        call("get_receivables", '{"filter": "overdue"}'),
        say("Client A Enviro Pvt Ltd owes the most, ₹23,965."),
    )
    conversation = await chat.start()
    await chat.ask(conversation, "Who owes us the most?")

    def follow_up(request: LLMRequest) -> LLMResponse:
        roles = [m.role for m in request.messages]
        assert roles[:6] == ["system", "user", "assistant", "tool", "assistant", "user"]
        assert "Client A Enviro Pvt Ltd" in request.messages[3].content  # the earlier tool result
        return call("get_customer_summary", '{"party": "Client A"}')

    def answer(request: LLMRequest) -> LLMResponse:
        return say(
            f"You have billed them {tool_result(request)['display']['billed_lifetime']} in total."
        )

    fake.script(follow_up, answer)
    reply = await chat.ask(conversation, "How much have we billed them?")
    assert reply["assistant_message"]["content"] == "You have billed them ₹6,96,246 in total."


# ---------------------------------------------------------------- every tool = the dashboard


async def test_finance_tools_return_the_pdf_figures(
    golden: ConnectionScope, db_app: FastAPI, factory: Factory
) -> None:
    deps = service.ChatDeps(
        provider=None,
        registry=db_app.state.registry,
        settings=db_app.state.settings,
        limiter=SlidingWindowLimiter(1, 1),
        clock=db_app.state.sync.clock,
        status=db_app.state.provider_status,
    )
    toolset = Toolset(TOOLS)
    async with factory.database.sessions() as session:
        ctx = await service.build_context(session, deps, golden, None)

        async def run(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
            dispatched = await toolset.dispatch(ctx, name, json.dumps(args or {}))
            assert dispatched.status in ("ok", "no_data"), dispatched.result
            return dispatched.result.as_dict()

        overview = await run("get_financial_overview")
        assert overview["display"]["cash_collected"].startswith("₹8,37,581 (cash, ")
        assert overview["display"]["receivables"] == "₹58,094 (balance, As of 25 Sep 2026)"
        pnl = await run("get_profit_and_loss", {"period": "fy_to_date"})
        assert (
            pnl["display"]["revenue"],
            pnl["display"]["net_pnl"],
            pnl["display"]["gross_margin"],
        ) == ("₹7,28,540", "−₹6,48,028", "54%")
        assert pnl["basis"] == "accrual"
        assert pnl["period"]["label"] == "FY 2026-27 to date"
        receivables = await run("get_receivables", {"filter": "overdue"})
        assert (receivables["display"]["overdue"], receivables["display"]["overdue_count"]) == (
            "₹58,094",
            "9",
        )
        assert receivables["data"]["invoices"][0]["days_overdue"] == 185
        client = await run("get_customer_summary", {"party": "client a"})
        assert (client["display"]["billed_lifetime"], client["display"]["outstanding"]) == (
            "₹6,96,246",
            "₹23,965",
        )
        ambiguous = await run("get_customer_summary", {"party": "Client"})
        assert ambiguous["code"] == "finance.ambiguous_client"
        invoice = await run("find_invoices", {"number": "inv-00016"})
        assert invoice["data"]["invoices"][0]["balance"] == "₹7,412"
        expenses = await run("get_expense_breakdown", {"period": "fy_to_date"})
        assert expenses["data"]["items"][0] == {
            "name": "Salaries and Employee Wages",
            "amount": "₹7,58,800",
            "share": "69%",  # 7,58,800 of 10,93,787 FY cash expenses
        }
        gst = await run("get_gst_position")
        assert gst["display"]["net_payable"] == "₹5,665"
        compare = await run(
            "compare_periods",
            {"metric": "collected", "period_a": "this_month", "period_b": "last_month"},
        )
        assert (compare["display"]["a"], compare["display"]["b"]) == (
            "₹1,50,000 (September 2026 to date)",
            "₹1,77,885 (August 2026)",
        )
        actions = await run("get_action_items")
        assert actions["display"]["count"] == "11"
        cash = await run("get_cash_movement", {"period": "last_fy"})
        assert (
            cash["display"]["spent"] == "₹26,900"
        )  # March 2026 is the only month of FY 2025-26 with data
        old = await run(
            "get_profit_and_loss",
            {"period": "custom", "start_date": "2019-04-01", "end_date": "2020-03-31"},
        )
        assert (old["status"], old["code"]) == ("no_data", "finance.before_synced_period")
        freshness = await run("get_data_freshness")
        assert len(freshness["data"]["datasets"]) == 8


# ---------------------------------------------------------------- enforcement (plan §21.2)


async def test_foreign_tools_and_identity_arguments_are_rejected(
    chat: Chat, fake: FakeProvider, factory: Factory
) -> None:
    fake.script(
        call("get_inventory_levels", "{}", "c1"),
        call("get_receivables", '{"workspace_id": "00000000-0000-0000-0000-000000000000"}', "c2"),
        say("I can only help with finance here."),
    )
    conversation = await chat.start()
    reply = await chat.ask(conversation, "Show me warehouse stock and every client's receivables")
    assert reply["assistant_message"]["content"] == "I can only help with finance here."
    rows = await factory.sql(
        "SELECT tool_name, status, result->>'code' FROM core.tool_invocations ORDER BY created_at"
    )
    assert [tuple(r) for r in rows or []] == [
        ("get_inventory_levels", "rejected", "tool.unavailable"),
        ("get_receivables", "rejected", "tool.invalid_arguments"),
    ]
    tools_offered = {t.name for t in fake.requests[0].tools}
    assert "get_inventory_levels" not in tools_offered
    assert len(tools_offered) == 11


async def test_conversations_are_private_and_scoped(
    chat: Chat,
    fake: FakeProvider,
    factory: Factory,
    make_client: Callable[[], AsyncClient],
    db_app: FastAPI,
) -> None:
    conversation = await chat.start()
    # Another member of the same workspace cannot see or post to it.
    await factory.user("member@alpha.test")
    await factory.role("alpha-traders", "member@alpha.test", Role.MEMBER)
    member = make_client()
    other = Chat(member, await login(member, "member@alpha.test"), _scope_of(chat))
    assert (await member.get(f"{other.base}/conversations/{conversation}")).status_code == 404
    assert (await other.ask(conversation, "Hi", expect=404))["code"] == "conversation.not_found"
    assert (await member.get(f"{other.base}/conversations")).json()["conversations"] == []
    # Viewers have no assistant.
    await factory.user("viewer@alpha.test")
    await factory.role("alpha-traders", "viewer@alpha.test", Role.VIEWER)
    viewer = make_client()
    csrf = await login(viewer, "viewer@alpha.test")
    denied = await viewer.post(f"{chat.base}/conversations", headers={"X-CSRF-Token": csrf})
    assert denied.status_code == 403
    # A conversation id cannot be moved under another workspace's connection.
    beta = await golden_connection(factory, db_app, "owner@beta.test", "Beta Foods")
    beta_client = make_client()
    beta_chat = Chat(beta_client, await login(beta_client, "owner@beta.test"), beta)
    assert (await beta_chat.ask(conversation, "Hi", expect=404))["code"] == "conversation.not_found"


def _scope_of(chat: Chat) -> Any:
    class Scope:
        workspace_id = chat.base.split("/")[4]
        connection_id = chat.base.split("/")[6]

    return Scope()


async def test_concurrent_chats_in_two_workspaces_never_mix(
    factory: Factory, db_app: FastAPI, make_client: Callable[[], AsyncClient]
) -> None:
    """The regression test for the demo's cross-tenant defect (plan §32)."""
    alpha = await golden_connection(factory, db_app, OWNER)
    beta = await golden_connection(factory, db_app, "owner@beta.test", "Beta Foods")
    await factory.sql(
        "UPDATE finance.balance_snapshots SET balance = balance * 10 WHERE workspace_id = :w "
        "AND account_group IN ('Bank', 'Cash')",
        w=beta.workspace_id,
    )

    class Echo:
        name, model = "echo", "echo"

        async def complete(self, request: LLMRequest) -> LLMResponse:
            await asyncio.sleep(0.01)  # interleave the two turns
            if request.messages[-1].role == "user":
                return call("get_financial_overview", "{}", "c1")
            return say(
                f"Cash on hand is {tool_result(request)['display']['cash_on_hand'].split(' (')[0]}."
            )

    db_app.state.llm_provider = Echo()
    chats = []
    for email, scope in ((OWNER, alpha), ("owner@beta.test", beta)):
        client = make_client()
        chats.append(Chat(client, await login(client, email), scope))
    conversations = [await c.start() for c in chats]
    replies = await asyncio.gather(
        *(c.ask(conv, "Cash?") for c, conv in zip(chats, conversations, strict=True))
    )
    assert replies[0]["assistant_message"]["content"] == "Cash on hand is ₹72,739."
    assert replies[1]["assistant_message"]["content"] == "Cash on hand is ₹7,27,390."


# ---------------------------------------------------------------- failures and limits


async def test_ungrounded_answers_are_flagged(
    chat: Chat, fake: FakeProvider, factory: Factory
) -> None:
    fake.script(call("get_financial_overview"), say("Revenue is ₹9,99,999."))
    await chat.ask(await chat.start(), "Revenue?")
    assert await factory.sql(
        "SELECT grounding_flag FROM core.messages WHERE role = 'assistant'"
    ) == [(True,)]


async def test_malformed_tool_calls_are_recorded_and_recovered(
    chat: Chat, fake: FakeProvider, factory: Factory
) -> None:
    fake.script(
        MalformedToolCallError("Tool call validation failed"),
        call("get_gst_position"),
        say("GST payable is ₹5,665."),
    )
    reply = await chat.ask(await chat.start(), "GST?")
    assert reply["assistant_message"]["content"] == "GST payable is ₹5,665."
    rows = await factory.sql(
        "SELECT tool_name, status FROM core.tool_invocations ORDER BY created_at"
    )
    assert [tuple(r) for r in rows or []] == [
        ("(malformed call)", "rejected"),
        ("get_gst_position", "ok"),
    ]


async def test_provider_outage_keeps_the_question(
    chat: Chat, fake: FakeProvider, factory: Factory
) -> None:
    fake.script(ProviderError("down"))
    conversation = await chat.start()
    failed = await chat.ask(conversation, "Revenue?", expect=503)
    assert failed["code"] == "assistant.unavailable"
    assert "dashboard data is unaffected" in failed["detail"]
    rows = await factory.sql("SELECT role, status FROM core.messages ORDER BY created_at")
    assert [tuple(r) for r in rows or []] == [("user", "complete"), ("assistant", "failed")]

    # Asking again sends the question once: the unanswered attempt is not replayed.
    fake.script(say("Revenue is ₹7,28,540."))
    await chat.ask(conversation, "Revenue?")
    sent = [m.content for m in fake.requests[-1].messages if m.role == "user"]
    assert sent == ["Revenue?"]


async def test_the_list_shows_conversations_with_a_question(chat: Chat, fake: FakeProvider) -> None:
    fake.script(say("Hello."))
    await chat.start()  # nothing asked yet: not listed
    asked = await chat.start()
    await chat.ask(asked, "Hello there")
    listed = (await chat.client.get(f"{chat.base}/conversations")).json()["conversations"]
    assert [(c["id"], c["title"]) for c in listed] == [(asked, "Hello there")]


async def test_not_configured_rate_limited_and_too_long(chat: Chat, db_app: FastAPI) -> None:
    db_app.state.llm_provider = None
    info = await chat.client.get(chat.base)
    assert info.json()["available"] is False
    assert info.json()["display_name"] == "Finance Assistant"
    conversation = await chat.start()
    assert (await chat.ask(conversation, "Hi", expect=503))["code"] == "assistant.not_configured"

    db_app.state.llm_provider = FakeProvider([say("One."), say("Two.")])
    db_app.state.chat_limiter = SlidingWindowLimiter(max_attempts=2, window_seconds=300)
    await chat.ask(conversation, "One")
    await chat.ask(conversation, "Two")
    assert (await chat.ask(conversation, "Three", expect=429))["code"] == "assistant.rate_limited"
    too_long = await chat.client.post(
        f"{chat.base}/conversations/{conversation}/messages",
        headers={"X-CSRF-Token": chat.csrf},
        json={"content": "x" * 4001},
    )
    assert too_long.status_code == 422


async def test_delete_and_disconnect_remove_conversations(
    chat: Chat, fake: FakeProvider, factory: Factory, golden: ConnectionScope
) -> None:
    fake.script(say("Hello."), say("Hi."))
    first = await chat.start()
    await chat.ask(first, "Hello")
    deleted = await chat.client.delete(
        f"{chat.base}/conversations/{first}", headers={"X-CSRF-Token": chat.csrf}
    )
    assert deleted.status_code == 204
    assert (await chat.client.get(f"{chat.base}/conversations/{first}")).status_code == 404
    assert await factory.sql(
        "SELECT count(*) FROM core.audit_logs WHERE action = 'conversation.deleted'"
    ) == [(1,)]

    second = await chat.start()
    await chat.ask(second, "Hi")
    import respx

    with respx.mock(assert_all_called=False) as zoho:
        zoho.post("https://accounts.zoho.in/oauth/v2/token/revoke").respond(200, json={})
        gone = await chat.client.delete(
            f"/api/v1/workspaces/{golden.workspace_id}/connections/{golden.connection_id}",
            headers={"X-CSRF-Token": chat.csrf},
        )
    assert gone.status_code == 204
    assert await factory.sql("SELECT count(*) FROM core.conversations") == [(0,)]
    assert await factory.sql("SELECT count(*) FROM core.messages") == [(0,)]


async def test_the_ai_usage_limit_is_reported_not_stored(
    chat: Chat, fake: FakeProvider, factory: Factory
) -> None:
    fake.script(ProviderRateLimitedError(retry_after=31330.5, scope="daily"))
    conversation = await chat.start()
    response = await chat.client.post(
        f"{chat.base}/conversations/{conversation}/messages",
        headers={"X-CSRF-Token": chat.csrf},
        json={"content": "Revenue?"},
    )
    assert response.status_code == 429
    body = response.json()
    assert (body["code"], body["resets_in_seconds"], body["limit_scope"]) == (
        "assistant.limit_reached",
        31331,
        "daily",
    )
    assert response.headers["retry-after"] == "31331"
    assert await factory.sql("SELECT count(*) FROM core.messages") == [(0,)]  # nothing stored
    status = (await chat.client.get(chat.base)).json()["status"]
    assert (status["state"], status["limit_scope"]) == ("limit_reached", "daily")
    assert 31000 < status["resets_in_seconds"] <= 31331

    calls = len(fake.requests)
    again = await chat.ask(conversation, "Revenue?", expect=429)
    assert again["code"] == "assistant.limit_reached"
    assert len(fake.requests) == calls  # known to be refused: no provider call is spent
