from __future__ import annotations

import os

import pytest

from clario.config import get_settings


def _ready() -> bool:
    settings = get_settings()
    return settings.zoho_ready()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_zoho_organization_and_core_apis():
    if not _ready():
        pytest.skip("Zoho credentials are not configured")
    from clario.zoho.client import ZohoBooksClient

    client = ZohoBooksClient()
    try:
        orgs = await client.list_organizations()
        assert orgs
        org = await client.get_current_organization()
        assert org.organization_id
        assert org.currency_code
        invoices = await client.list_invoices()
        customers = await client.list_customers()
        payments = await client.list_payments()
        expenses = await client.list_expenses()
        assert isinstance(invoices, list)
        assert isinstance(customers, list)
        assert isinstance(payments, list)
        assert isinstance(expenses, list)
    finally:
        await client.aclose()


@pytest.mark.agent
@pytest.mark.asyncio
async def test_live_agent_uses_a_tool_for_receivables():
    if not os.getenv("GOOGLE_API_KEY") and not get_settings().google_api_key:
        pytest.skip("GOOGLE_API_KEY is not configured")
    if not _ready():
        pytest.skip("Zoho credentials are not configured")
    from clario.agent.runner import ClarioRunner

    runner = ClarioRunner()
    result = await runner.ask("Which customers owe us the most?")
    assert result["answer"]
    names = {call["tool"] for call in result["tool_calls"]}
    assert "get_customer_balances" in names or "get_business_summary" in names
    assert "₹" in result["answer"] or "INR" in result["answer"] or any(char.isdigit() for char in result["answer"])
