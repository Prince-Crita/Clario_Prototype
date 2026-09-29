"""Read-only Zoho Books REST client.

Independent of Google ADK. Handles auth, token refresh, pagination,
timeouts, rate limits, and response validation.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, AsyncIterator, Callable

import httpx

from clario.config import Settings, get_settings
from clario.logging import get_logger
from clario.zoho.errors import ZohoAPIError, ZohoAuthError, ZohoRateLimitError, ZohoValidationError
from clario.zoho.models import Customer, Expense, Invoice, Item, Organization, Payment
from clario.zoho.normalize import (
    customer_from_zoho,
    expense_from_zoho,
    invoice_from_zoho,
    item_from_zoho,
    organization_from_zoho,
    payment_from_zoho,
)
from clario.zoho.oauth import ZohoOAuth

logger = get_logger("clario.zoho.client")

SUPPORTED_REPORTS = {
    "profitandloss": "profitandloss",
    "profit_and_loss": "profitandloss",
    "pnl": "profitandloss",
    "balancesheet": "balancesheet",
    "balance_sheet": "balancesheet",
    "cashflow": "cashflow",
    "cash_flow": "cashflow",
    "salesbycustomer": "salesbycustomer",
    "sales_by_customer": "salesbycustomer",
    "salesbyitem": "salesbyitem",
    "sales_by_item": "salesbyitem",
    "inventorysummary": "inventorysummary",
    "inventory_summary": "inventorysummary",
    "inventoryvaluation": "inventoryvaluation",
    "aging": "aging",
    "receivables_aging": "aging",
    "customerbalances": "customerbalances",
    "customer_balances": "customerbalances",
}


class ZohoBooksClient:
    def __init__(
        self,
        settings: Settings | None = None,
        oauth: ZohoOAuth | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.oauth = oauth or ZohoOAuth(self.settings)
        self._http = http
        self._owns_http = http is None
        self._org_id = self.settings.zoho_organization_id

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.settings.request_timeout_seconds)
        return self._http

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        include_org: bool = True,
        retry_on_auth: bool = True,
    ) -> dict[str, Any]:
        query = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        if include_org:
            org_id = await self.organization_id()
            query["organization_id"] = org_id
        url = f"{self.settings.zoho_api_base_url}/{path.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            token = await self.oauth.get_valid_access_token()
            headers = {"Authorization": f"Zoho-oauthtoken {token}"}
            client = await self._client()
            logger.info("Zoho %s %s attempt=%s", method, path, attempt + 1)
            try:
                response = await client.request(method, url, params=query, headers=headers)
            except httpx.TimeoutException as exc:
                last_error = ZohoAPIError(f"Zoho request timed out: {path}", path=path)
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            except httpx.HTTPError as exc:
                last_error = ZohoAPIError(f"Zoho request failed: {exc}", path=path)
                await asyncio.sleep(0.5 * (attempt + 1))
                continue

            if response.status_code in (401, 403) and retry_on_auth and attempt == 0:
                logger.info("Zoho auth error on %s; refreshing access token", path)
                await self.oauth.refresh_access_token()
                continue

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After") or (1.5 * (attempt + 1)))
                logger.warning("Zoho rate-limited path=%s retry_after=%s", path, retry_after)
                if attempt < self.settings.max_retries:
                    await asyncio.sleep(retry_after)
                    continue
                raise ZohoRateLimitError(
                    "Zoho Books rate limit exceeded. Try again shortly.",
                    status_code=429,
                    path=path,
                    retry_after=retry_after,
                )

            payload = _json_or_error(response, path)
            if response.status_code >= 400 or int(payload.get("code") or 0) != 0:
                message = payload.get("message") or f"HTTP {response.status_code}"
                raise ZohoAPIError(
                    f"Zoho API error on {path}: {message}",
                    status_code=response.status_code,
                    code=payload.get("code"),
                    path=path,
                )
            return payload

        assert last_error is not None
        raise last_error

    async def organization_id(self) -> str:
        if self._org_id:
            return self._org_id
        orgs = await self.list_organizations()
        if not orgs:
            raise ZohoAPIError("No Zoho Books organizations were returned.")
        chosen = next((org for org in orgs if org.is_default_org), orgs[0])
        self._org_id = chosen.organization_id
        logger.info("Using Zoho organization %s (%s)", chosen.organization_id, chosen.name)
        return self._org_id

    async def list_organizations(self) -> list[Organization]:
        payload = await self.request("GET", "organizations", include_org=False)
        rows = payload.get("organizations") or []
        return [organization_from_zoho(row) for row in rows]

    async def get_current_organization(self) -> Organization:
        org_id = await self.organization_id()
        orgs = await self.list_organizations()
        for org in orgs:
            if org.organization_id == org_id:
                return org
        raise ZohoAPIError(f"Configured organization {org_id} was not found.")

    async def iter_invoices(
        self,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        status: str | None = None,
        customer_id: str | None = None,
    ) -> AsyncIterator[Invoice]:
        params: dict[str, Any] = {
            "date_start": _iso(start_date),
            "date_end": _iso(end_date),
            "status": status,
            "customer_id": customer_id,
        }
        async for row in self._paginate("invoices", "invoices", params):
            yield invoice_from_zoho(row)

    async def list_invoices(self, **kwargs: Any) -> list[Invoice]:
        return [item async for item in self.iter_invoices(**kwargs)]

    async def iter_customers(self, *, customer_id: str | None = None) -> AsyncIterator[Customer]:
        params: dict[str, Any] = {"contact_type": "customer"}
        if customer_id:
            params["contact_id"] = customer_id
        async for row in self._paginate("contacts", "contacts", params):
            yield customer_from_zoho(row)

    async def list_customers(self, **kwargs: Any) -> list[Customer]:
        return [item async for item in self.iter_customers(**kwargs)]

    async def iter_payments(
        self,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        customer_id: str | None = None,
    ) -> AsyncIterator[Payment]:
        params: dict[str, Any] = {
            "date_start": _iso(start_date),
            "date_end": _iso(end_date),
            "customer_id": customer_id,
        }
        async for row in self._paginate("customerpayments", "customerpayments", params):
            yield payment_from_zoho(row)

    async def list_payments(self, **kwargs: Any) -> list[Payment]:
        return [item async for item in self.iter_payments(**kwargs)]

    async def iter_expenses(
        self,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
    ) -> AsyncIterator[Expense]:
        params: dict[str, Any] = {
            "date_start": _iso(start_date),
            "date_end": _iso(end_date),
        }
        async for row in self._paginate("expenses", "expenses", params):
            yield expense_from_zoho(row)

    async def list_expenses(self, **kwargs: Any) -> list[Expense]:
        return [item async for item in self.iter_expenses(**kwargs)]

    async def iter_items(self) -> AsyncIterator[Item]:
        async for row in self._paginate("items", "items", {}):
            yield item_from_zoho(row)

    async def list_items(self) -> list[Item]:
        return [item async for item in self.iter_items()]

    async def get_report(
        self,
        report_name: str,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved = SUPPORTED_REPORTS.get(report_name.lower().replace(" ", "").replace("-", "_"), None)
        if resolved is None and report_name.lower() in SUPPORTED_REPORTS.values():
            resolved = report_name.lower()
        if resolved is None:
            raise ZohoValidationError(
                f"Unsupported report '{report_name}'. "
                f"Allowed: {sorted(set(SUPPORTED_REPORTS.values()))}"
            )
        params: dict[str, Any] = {
            "from_date": _iso(start_date),
            "to_date": _iso(end_date),
            **(extra or {}),
        }
        return await self.request("GET", f"reports/{resolved}", params=params)

    async def _paginate(
        self,
        path: str,
        list_key: str,
        params: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        page = 1
        while page <= self.settings.max_pages:
            payload = await self.request(
                "GET",
                path,
                params={**params, "page": page, "per_page": self.settings.per_page},
            )
            rows = payload.get(list_key)
            if rows is None:
                raise ZohoValidationError(f"Zoho response for {path} did not include '{list_key}'.")
            for row in rows:
                yield row
            page_context = payload.get("page_context") or {}
            if isinstance(page_context, list):
                page_context = page_context[0] if page_context else {}
            if not page_context.get("has_more_page"):
                return
            page += 1
        logger.warning("Stopped pagination on %s after %s pages", path, self.settings.max_pages)


def _iso(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _json_or_error(response: httpx.Response, path: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ZohoAPIError(
            f"Zoho returned non-JSON for {path} (HTTP {response.status_code}).",
            status_code=response.status_code,
            path=path,
        ) from exc
    if not isinstance(payload, dict):
        raise ZohoValidationError(f"Zoho returned an unexpected JSON type for {path}.")
    return payload


_client_factory: Callable[[], ZohoBooksClient] | None = None


def set_client_factory(factory: Callable[[], ZohoBooksClient] | None) -> None:
    global _client_factory
    _client_factory = factory


def get_client() -> ZohoBooksClient:
    if _client_factory is not None:
        return _client_factory()
    return ZohoBooksClient()
