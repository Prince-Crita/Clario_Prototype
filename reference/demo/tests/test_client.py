from __future__ import annotations

import httpx
import pytest
import respx

from clario.zoho.client import ZohoBooksClient
from clario.zoho.errors import ZohoAPIError, ZohoRateLimitError, ZohoValidationError
from clario.zoho.oauth import TokenSet, TokenStore, ZohoOAuth


def _oauth(settings):
    store = TokenStore(settings.token_path, settings.zoho_refresh_token)
    store.save(
        TokenSet(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=9_999_999_999,
        )
    )
    return ZohoOAuth(settings, store)


def _client(settings) -> ZohoBooksClient:
    return ZohoBooksClient(settings, oauth=_oauth(settings))


INVOICE_PAGE_1 = {
    "code": 0,
    "message": "success",
    "invoices": [
        {
            "invoice_id": "1",
            "invoice_number": "INV-1",
            "customer_name": "Acme",
            "customer_id": "c1",
            "status": "sent",
            "date": "2026-09-01",
            "due_date": "2026-09-15",
            "total": 100,
            "balance": 100,
            "currency_code": "INR",
        }
    ],
    "page_context": {"page": 1, "per_page": 200, "has_more_page": True},
}

INVOICE_PAGE_2 = {
    "code": 0,
    "message": "success",
    "invoices": [
        {
            "invoice_id": "2",
            "invoice_number": "INV-2",
            "customer_name": "Globex",
            "customer_id": "c2",
            "status": "paid",
            "date": "2026-09-02",
            "due_date": "2026-09-16",
            "total": 50,
            "balance": 0,
            "currency_code": "INR",
        }
    ],
    "page_context": {"page": 2, "per_page": 200, "has_more_page": False},
}


@pytest.mark.asyncio
async def test_list_invoices_paginates(settings):
    client = _client(settings)
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.zohoapis.in/books/v3/invoices").mock(
            side_effect=[
                httpx.Response(200, json=INVOICE_PAGE_1),
                httpx.Response(200, json=INVOICE_PAGE_2),
            ]
        )
        invoices = await client.list_invoices()
    assert [inv.invoice_number for inv in invoices] == ["INV-1", "INV-2"]
    await client.aclose()


@pytest.mark.asyncio
async def test_organizations_customers_payments_expenses_items(settings):
    client = _client(settings)
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.zohoapis.in/books/v3/organizations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "organizations": [
                        {
                            "organization_id": "org-1",
                            "name": "Demo Co",
                            "currency_code": "INR",
                            "is_org_active": True,
                            "is_default_org": True,
                        }
                    ],
                },
            )
        )
        router.get("https://www.zohoapis.in/books/v3/contacts").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "contacts": [{"contact_id": "c1", "contact_name": "Acme", "outstanding_receivable_amount": 10}],
                    "page_context": {"has_more_page": False},
                },
            )
        )
        router.get("https://www.zohoapis.in/books/v3/customerpayments").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "customerpayments": [{"payment_id": "p1", "amount": 10, "date": "2026-09-01"}],
                    "page_context": {"has_more_page": False},
                },
            )
        )
        router.get("https://www.zohoapis.in/books/v3/expenses").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "expenses": [{"expense_id": "e1", "total": 8, "account_name": "Travel", "date": "2026-09-01"}],
                    "page_context": {"has_more_page": False},
                },
            )
        )
        router.get("https://www.zohoapis.in/books/v3/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": 0,
                    "items": [{"item_id": "i1", "name": "Widget", "rate": 1}],
                    "page_context": {"has_more_page": False},
                },
            )
        )
        orgs = await client.list_organizations()
        customers = await client.list_customers()
        payments = await client.list_payments()
        expenses = await client.list_expenses()
        items = await client.list_items()
    assert orgs[0].name == "Demo Co"
    assert customers[0].name == "Acme"
    assert payments[0].payment_id == "p1"
    assert expenses[0].category == "Travel"
    assert items[0].name == "Widget"
    await client.aclose()


@pytest.mark.asyncio
async def test_report_allowlist_and_fetch(settings):
    client = _client(settings)
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.zohoapis.in/books/v3/reports/profitandloss").mock(
            return_value=httpx.Response(200, json={"code": 0, "total": 100})
        )
        payload = await client.get_report("profit_and_loss", start_date="2026-09-01", end_date="2026-09-22")
    assert payload["total"] == 100
    with pytest.raises(ZohoValidationError):
        await client.get_report("not-a-report")
    await client.aclose()


@pytest.mark.asyncio
async def test_401_refreshes_token(settings):
    client = _client(settings)
    with respx.mock() as router:
        router.post("https://accounts.zoho.in/oauth/v2/token").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "new-access", "expires_in": 3600},
            )
        )
        route = router.get("https://www.zohoapis.in/books/v3/invoices")
        route.side_effect = [
            httpx.Response(401, json={"code": 57, "message": "Invalid OAuth token"}),
            httpx.Response(200, json={"code": 0, "invoices": [], "page_context": {"has_more_page": False}}),
        ]
        invoices = await client.list_invoices()
    assert invoices == []
    await client.aclose()


@pytest.mark.asyncio
async def test_rate_limit_exhausted(settings):
    settings.max_retries = 0
    client = _client(settings)
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.zohoapis.in/books/v3/invoices").mock(
            return_value=httpx.Response(429, json={"code": 44, "message": "rate limited"}, headers={"Retry-After": "1"})
        )
        with pytest.raises(ZohoRateLimitError):
            await client.list_invoices()
    await client.aclose()


@pytest.mark.asyncio
async def test_wrong_organization_and_malformed_payload(settings):
    client = _client(settings)
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.zohoapis.in/books/v3/invoices").mock(
            return_value=httpx.Response(200, json={"code": 6041, "message": "Invalid organization"})
        )
        with pytest.raises(ZohoAPIError, match="Invalid organization"):
            await client.list_invoices()
    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.zohoapis.in/books/v3/invoices").mock(
            return_value=httpx.Response(200, json={"code": 0, "not_invoices": []})
        )
        with pytest.raises(ZohoValidationError):
            await client.list_invoices()
    await client.aclose()
