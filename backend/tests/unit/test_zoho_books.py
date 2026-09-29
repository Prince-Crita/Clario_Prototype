"""Zoho Books connector units: client behaviour, organisation mapping, allow-lists."""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
import respx

from clario.core.errors import RateLimitedError, UpstreamError, ValidationFailedError
from clario.integrations.zoho_books import client as client_module
from clario.integrations.zoho_books.client import ZohoBooksClient
from clario.integrations.zoho_books.organizations import to_account, to_profile
from clario.integrations.zoho_books.plugin import _missing_scopes, plugin
from clario.integrations.zoho_books.regions import allowed_api_domain, by_accounts_server
from tests.support import make_settings

API = "https://www.zohoapis.in"


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "RETRY_DELAY_SECONDS", 0)


@respx.mock
async def test_amounts_are_parsed_as_decimals_never_floats() -> None:
    respx.get(f"{API}/books/v3/invoices").mock(
        return_value=httpx.Response(200, text='{"code": 0, "invoices": [{"total": 3000.10}]}')
    )
    async with ZohoBooksClient(API, "tok") as zoho:
        payload = await zoho.get("invoices")
    assert payload["invoices"][0]["total"] == Decimal("3000.10")


@respx.mock
async def test_transport_errors_are_retried() -> None:
    route = respx.get(f"{API}/books/v3/organizations").mock(
        side_effect=[
            httpx.RemoteProtocolError("Server disconnected"),
            httpx.Response(200, json={"code": 0}),
        ]
    )
    async with ZohoBooksClient(API, "tok") as zoho:
        assert await zoho.get("organizations") == {"code": 0}
    assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize(
    ("response", "error", "code"),
    [
        (
            httpx.Response(401, json={"code": 57, "message": "not authorized"}),
            UpstreamError,
            "zoho.unauthorized",
        ),
        (httpx.Response(429, json={"code": 44}), RateLimitedError, "zoho.rate_limited"),
        (
            httpx.Response(200, json={"code": 1002, "message": "no org"}),
            UpstreamError,
            "zoho.error",
        ),
        (httpx.Response(500, text="oops"), UpstreamError, "zoho.error"),
    ],
)
async def test_failures_become_typed_errors(
    response: httpx.Response, error: type[Exception], code: str
) -> None:
    respx.get(f"{API}/books/v3/organizations").mock(return_value=response)
    async with ZohoBooksClient(API, "tok") as zoho:
        with pytest.raises(error) as caught:
            await zoho.get("organizations")
    assert getattr(caught.value, "code", None) == code
    assert "no org" not in str(caught.value)  # Zoho's message is logged, not shown


def test_organisation_profile_reads_the_month_name() -> None:
    profile = to_profile(
        {
            "organization_id": "60089553909",
            "name": "Crita‑TEST",  # non-breaking hyphen, as Zoho sends it
            "currency_code": "INR",
            "time_zone": "Asia/Calcutta",
            "fiscal_year_start_month": "april",
        }
    )
    assert (profile.name, profile.currency, profile.fiscal_year_start_month) == (
        "Crita-TEST",
        "INR",
        4,
    )
    assert (
        to_profile({"organization_id": "1", "fiscal_year_start_month": 3}).fiscal_year_start_month
        is None
    )


def test_unsupported_organisations_are_not_selectable() -> None:
    assert to_account({"organization_id": "1", "isOrgNotSupported": True}).selectable is False
    assert to_account({"organization_id": "2", "name": "A"}).selectable is True


def test_data_center_allow_lists() -> None:
    assert by_accounts_server("https://ACCOUNTS.zoho.in/") is not None
    assert by_accounts_server("https://accounts.zoho.in.evil.example") is None
    assert allowed_api_domain("https://www.zohoapis.eu") == "https://www.zohoapis.eu"
    assert allowed_api_domain("https://zohoapis.in@evil.example") is None


def test_scope_check_is_case_insensitive_and_tolerates_an_absent_list() -> None:
    required = ["ZohoBooks.settings.READ", "ZohoBooks.reports.READ"]
    assert _missing_scopes(required, ("zohobooks.settings.read", "ZohoBooks.reports.READ")) == []
    assert _missing_scopes(required, ("ZohoBooks.settings.READ",)) == ["ZohoBooks.reports.READ"]
    assert _missing_scopes(required, ()) == []


def test_consent_url_uses_the_default_region_and_needs_configuration() -> None:
    consent = plugin.consent_redirect(make_settings(), state="s" * 43, region=None)
    url = urlsplit(consent.url)
    assert (consent.region, url.netloc, url.path) == ("in", "accounts.zoho.in", "/oauth/v2/auth")
    assert dict(parse_qsl(url.query))["state"] == "s" * 43
    with pytest.raises(ValidationFailedError):
        plugin.consent_redirect(make_settings(), state="s", region="mars")
    unconfigured = make_settings(zoho_client_id="")
    with pytest.raises(Exception, match="not configured"):
        plugin.consent_redirect(unconfigured, state="s", region=None)
