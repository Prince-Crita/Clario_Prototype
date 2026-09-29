"""The finance acceptance test (plan §24.4): the golden dataset, synced through the real engine and
served by the real API as of 25 Sep 2026, reproduces EVERY figure in the director's PDFs.

PDF references: `crita-live-pl.pdf` (Overview, pages 1-4) and `crita-live-pl1.pdf` (Trends).
Amounts are compared exactly; percentages as the PDF displays them (0 dp, half-up).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from clario.core.money import round_half_up
from clario.platform.access.permissions import Role
from clario.platform.access.scopes import ConnectionScope
from clario.platform.sync.models import SyncTrigger
from clario.platform.sync.service import SyncRunner
from tests.support import Factory, login, zoho_connection

pytestmark = pytest.mark.db

OWNER = "director@alpha.test"
NOW = datetime(2026, 9, 25, 10, 26, tzinfo=UTC)  # "Updated 25 Sept · 03:56 pm" IST
A, B, C, D_ = "Client A Enviro Pvt Ltd", "Client B Threads", "Client C Coffee Pvt Ltd", "Client D"


def d(value: Any) -> Decimal:
    return Decimal(str(value))


def pct(value: Any) -> Decimal:
    return round_half_up(d(value), 0)


@pytest.fixture
async def golden(factory: Factory, db_app: FastAPI) -> ConnectionScope:
    await factory.user(OWNER)
    workspace = await factory.workspace("Alpha Traders", OWNER)
    scope = await zoho_connection(factory, db_app.state.settings, workspace, OWNER)
    db_app.state.settings.finance_fixture_source = True  # the golden dataset instead of Zoho
    runner: SyncRunner = db_app.state.sync
    runner.clock = lambda: NOW
    outcome = await runner.trigger(scope, SyncTrigger.SCHEDULED)
    assert outcome.started
    await runner.wait_idle()
    return scope


@pytest.fixture
async def api(
    golden: ConnectionScope, make_client: Callable[[], AsyncClient]
) -> Callable[[str], Any]:
    client = make_client()
    await login(client, OWNER)
    base = f"/api/v1/workspaces/{golden.workspace_id}/connections/{golden.connection_id}/finance"

    async def get(path: str) -> Any:
        response = await client.get(f"{base}{path}")
        assert response.status_code == 200, response.text
        return response.json()

    return get


# ---------------------------------------------------------------- Overview (crita-live-pl.pdf)


async def test_kpi_band(api: Callable[[str], Any]) -> None:
    overview = await api("/overview")
    kpis = {k["key"]: k for k in overview["kpis"]}
    assert d(kpis["revenue"]["value"]) == d(728_540)  # REVENUE (ACCRUAL) ₹7,28,540
    assert kpis["revenue"]["basis"] == "accrual"
    assert kpis["revenue"]["window"]["label"] == "FY 2026-27 to date"

    collected = kpis["cash_collected"]
    assert d(collected["value"]) == d(837_581)  # CASH COLLECTED ₹8,37,581
    assert d(collected["related"]["amount"]) == d(895_675)  # of ₹8,95,675 billed
    assert pct(collected["ratio"]) == 94  # 94%

    costs = kpis["total_costs"]
    assert d(costs["value"]) == d(1_376_568)  # TOTAL COSTS ₹13,76,568
    assert pct(costs["change"]["percent"]) == -7  # ▼ 7% MoM

    net = kpis["net_pnl"]
    assert d(net["value"]) == d(-648_028)  # NET P&L −₹6,48,028
    assert pct(net["ratio"]) == -89  # −89% margin

    assert d(kpis["cash_on_hand"]["value"]) == d(72_739)  # CASH ON HAND ₹72,739
    assert d(kpis["receivables"]["value"]) == d(58_094)  # RECEIVABLES ₹58,094
    assert kpis["receivables"]["count"] == 9  # 9 overdue
    assert overview["meta"]["fiscal_year"] == "FY 2026-27"
    assert overview["meta"]["today"] == "2026-09-25"


async def test_pnl_statement(api: Callable[[str], Any]) -> None:
    statement = (await api("/overview"))["pnl"]
    assert d(statement["revenue"]) == d(728_540)
    assert d(statement["cogs"]) == d(336_078)
    assert d(statement["operating_expenses"]) == d(1_040_490)
    assert d(statement["net_pnl"]) == d(-648_028)
    assert pct(statement["gross_margin"]) == 54  # Gross margin 54%
    assert d(statement["latest_month_spend"]) == d(241_549)  # payroll ~₹2,41,549/mo (Q3)
    assert statement["largest_cost"] == {
        "name": "Salaries and Employee Wages",
        "amount": "758800.0000",
    }


MONTHS = [  # MONTH-ON-MONTH P&L (crita-live-pl1.pdf): billed, collected, expenses, net cash
    ("2026-03-01", 36_000, 0, 26_900, -26_900),
    ("2026-04-01", 0, 0, 9_656, -9_656),
    ("2026-05-01", 238_675, 120_675, 155_020, -34_345),
    ("2026-06-01", 134_520, 140_520, 201_721, -61_201),
    ("2026-07-01", 138_650, 248_501, 227_126, 21_375),
    ("2026-08-01", 193_520, 177_885, 258_715, -80_830),
    ("2026-09-01", 154_310, 150_000, 241_549, -91_549),
]


def rows(months: list[dict[str, Any]]) -> list[tuple[str, Decimal, Decimal, Decimal, Decimal]]:
    return [
        (m["month"], d(m["billed"]), d(m["collected"]), d(m["expenses"]), d(m["net_cash"]))
        for m in months
    ]


async def test_revenue_vs_cost_by_month(api: Callable[[str], Any]) -> None:
    expected = [(m, d(b), d(c), d(e), d(n)) for m, b, c, e, n in MONTHS]
    assert rows((await api("/overview"))["months"]) == expected


async def test_action_items(api: Callable[[str], Any]) -> None:
    items = (await api("/overview"))["actions"]
    overdue = [i for i in items if i["kind"] == "overdue_invoice"]
    assert [
        (i["reference"], d(i["amount"]), i["days_overdue"], i["due_date"]) for i in overdue
    ] == [
        ("INV-000002", d(13_000), 185, "2026-03-24"),
        ("INV-000001", d(17_000), 185, "2026-03-24"),
        ("INV-00010", d(4_019), 77, "2026-07-10"),
        ("INV-00012", d(2_065), 59, "2026-07-28"),
        ("INV-00016", d(7_412), 38, "2026-08-18"),
        ("INV-00022", d(2_064), 16, "2026-09-09"),
        ("INV-00023", d(2_064), 14, "2026-09-11"),
        ("INV-00021", d(1_770), 11, "2026-09-14"),
        ("INV-00024", d(8_700), 9, "2026-09-16"),
    ]
    assert overdue[0]["title"] == "INV-000002 · Client D: ₹13,000 overdue 185 days"
    gst_item = next(i for i in items if i["kind"] == "gst_payable")
    assert gst_item["title"] == "GST payable ₹5,665"
    assert "Output GST ₹1,31,137 − input credit ₹1,25,472" in gst_item["detail"]
    loss = next(i for i in items if i["kind"] == "accrual_loss")
    assert loss["title"] == "Accrual loss of ₹6,48,028 this fiscal year"
    assert "Revenue ₹7,28,540 against total costs ₹13,76,568" in loss["detail"]
    assert "₹7,58,800" in loss["detail"]  # payroll ₹7,58,800
    assert [i["kind"] for i in items][-2:] == ["gst_payable", "accrual_loss"]


async def test_revenue_by_client_and_expense_mix(api: Callable[[str], Any]) -> None:
    overview = await api("/overview")
    assert [
        (c["party_name"], d(c["billed"]), c["has_overdue"]) for c in overview["revenue_by_client"]
    ] == [
        (A, d(696_246), True),
        (B, d(159_300), False),
        (C, d(27_129), True),
        (D_, d(13_000), True),
    ]
    assert [e["name"] for e in overview["expense_mix"]] == [  # legend order of the donut
        "Salaries and Employee Wages",
        "Director Remuneration",
        "Software subscription A/C",
        "Proffessional expense",
        "Staff Welfare",
        "Consultant Expense",
        "Office Supplies",
    ]
    assert sum(d(e["amount"]) for e in overview["expense_mix"]) == d(1_040_490)
    totals = overview["register_totals"]
    assert (totals["count"], d(totals["billed"]), d(totals["balance"])) == (
        16,
        d(895_675),
        d(58_094),
    )


# ---------------------------------------------------------------- Trends (crita-live-pl1.pdf)


async def test_trends(api: Callable[[str], Any]) -> None:
    trends = await api("/trends")
    assert rows(trends["months"]) == [(m, d(b), d(c), d(e), d(n)) for m, b, c, e, n in MONTHS]
    total = trends["totals"]
    assert (
        d(total["billed"]),
        d(total["collected"]),
        d(total["expenses"]),
        d(total["net_cash"]),
    ) == (
        d(895_675),
        d(837_581),
        d(1_120_687),
        d(-283_106),
    )
    assert trends["top_categories"] == [
        "Salaries and Employee Wages",
        "Director Remuneration",
        "Software subscription A/C",
        "Proffessional expense",
        "Construction expense",
    ]
    for month, expected in zip(trends["expense_trend"], MONTHS, strict=True):
        assert sum(d(v) for v in month["amounts"].values()) + d(month["other"]) == d(expected[3])
    weeks = trends["weekly"]
    assert (len(weeks), weeks[0]["start"], weeks[-1]["start"]) == (10, "2026-07-20", "2026-09-21")
    sept_7 = next(w for w in weeks if w["start"] == "2026-09-07")
    assert (d(sept_7["cash_in"]), d(sept_7["cash_out"])) == (d(150_000), d(223_549))
    days = trends["daily"]
    assert (len(days), days[0]["start"], days[-1]["start"]) == (30, "2026-08-27", "2026-09-25")


# ---------------------------------------------------------------- Receivables, GST, balances


async def test_receivables(api: Callable[[str], Any]) -> None:
    receivables = await api("/receivables")
    assert (
        d(receivables["outstanding"]),
        d(receivables["overdue"]),
        receivables["overdue_count"],
    ) == (
        d(58_094),
        d(58_094),
        9,
    )
    assert [(b["key"], d(b["amount"]), b["count"]) for b in receivables["ageing"]] == [
        ("not_due", d(0), 0),
        ("1_30", d(14_598), 4),
        ("31_60", d(9_477), 2),
        ("61_90", d(4_019), 1),
        ("over_90", d(30_000), 2),
    ]
    assert [(c["party_name"], d(c["outstanding"])) for c in receivables["by_client"]] == [
        (A, d(23_965)),
        (C, d(21_129)),
        (D_, d(13_000)),
    ]
    assert receivables["invoices"][0]["invoice_number"] in {"INV-000001", "INV-000002"}
    assert all(i["status"] == "overdue" for i in receivables["invoices"])


async def test_gst_and_balance_sheet(api: Callable[[str], Any]) -> None:
    position = await api("/gst")
    assert (d(position["output_tax"]), d(position["input_tax"]), d(position["net_payable"])) == (
        d(131_137),
        d(125_472),
        d(5_665),
    )
    assert position["pending_definition"] is True
    balances = await api("/balance-sheet")
    assert d(balances["cash_on_hand"]) == d(72_739)
    assert balances["as_of"] == "2026-09-25"


async def test_invoice_register(api: Callable[[str], Any]) -> None:
    first = await api("/invoices?limit=5")
    assert [i["invoice_number"] for i in first["items"]] == [
        "INV-00024",
        "INV-00023",
        "INV-00022",
        "INV-00021",
        "INV-00020",
    ]
    assert first["items"][4]["status"] == "paid"
    seen = [i["invoice_number"] for i in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        page = await api(f"/invoices?limit=5&cursor={cursor}")
        seen += [i["invoice_number"] for i in page["items"]]
        cursor = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 16
    overdue = await api("/invoices?status=overdue&limit=200")
    assert len(overdue["items"]) == 9
    client_a = await api("/invoices?party=client%20a")
    assert {i["party_name"] for i in client_a["items"]} == {A}
    assert len(client_a["items"]) == 10


# ---------------------------------------------------------------- access


async def test_viewers_can_read_the_dashboards(
    golden: ConnectionScope, factory: Factory, make_client: Callable[[], AsyncClient]
) -> None:
    await factory.user("viewer@alpha.test")
    await factory.role("alpha-traders", "viewer@alpha.test", Role.VIEWER)
    client = make_client()
    await login(client, "viewer@alpha.test")
    base = f"/api/v1/workspaces/{golden.workspace_id}/connections/{golden.connection_id}/finance"
    for tab in ("/overview", "/trends", "/receivables", "/gst", "/balance-sheet", "/invoices"):
        assert (await client.get(f"{base}{tab}")).status_code == 200, tab


async def test_freshness_is_reported(api: Callable[[str], Any], golden: ConnectionScope) -> None:
    meta = (await api("/overview"))["meta"]
    assert meta["freshness"]["sync_state"] == "idle"
    assert datetime.fromisoformat(meta["freshness"]["as_of"]) == NOW
    assert meta["freshness"]["data_version"] is not None
    assert meta["organisation"] == "Crita Creative LLP (TEST trial)"
    assert date.fromisoformat(meta["today"]) == date(2026, 9, 25)
