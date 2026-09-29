"""Zoho Books REST client (plan §16.4).

* Base URL `{api_domain}/books/v3`, where `api_domain` has passed the allow-list; every call is
  scoped to one `organization_id`.
* Amounts arrive as JSON floats: responses are parsed with `parse_float=Decimal`.
* GETs are retried on transport errors (Zoho sometimes drops connections mid-request).
* Lists are read `per_page=200`; reaching `ZOHO_MAX_PAGES` with more pages left FAILS with
  `zoho.too_many_records` instead of returning a silently truncated list.
* Calls are counted, `x-rate-limit-*` headers are kept (the sync stores the daily budget), and at
  most `ZOHO_REQUESTS_PER_MINUTE` requests are sent in any 60 seconds.
* Failures become typed Clario errors; Zoho's message is logged, never shown.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from datetime import timedelta
from decimal import Decimal
from types import TracebackType
from typing import Any, Self

import httpx

from clario.core.dates import utc_now
from clario.core.errors import RateLimitedError, UpstreamError

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(45.0)
ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.0
PER_PAGE = 200


class ZohoBooksClient:
    def __init__(
        self,
        api_domain: str,
        access_token: str,
        *,
        organization_id: str | None = None,
        max_pages: int = 100,
        requests_per_minute: int = 60,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=f"{api_domain}/books/v3",
            timeout=TIMEOUT,
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        )
        self._organization_id = organization_id
        self._max_pages = max_pages
        self._per_minute = requests_per_minute
        self._sent: deque[float] = deque()
        self.calls = 0
        self.rate_limit: dict[str, Any] | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        if self._organization_id:
            query["organization_id"] = self._organization_id
        response = await self._send(path, query)
        try:
            payload = json.loads(response.content, parse_float=Decimal)
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            payload = {}
        self._raise_for(response, payload, path)
        return payload

    async def paginate(
        self, path: str, list_key: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """Every record of a list endpoint, or `zoho.too_many_records` — never a partial list."""
        rows: list[dict[str, Any]] = []
        for page in range(1, self._max_pages + 1):
            payload = await self.get(
                path, {**(params or {}), "page": str(page), "per_page": str(PER_PAGE)}
            )
            batch = payload.get(list_key)
            if not isinstance(batch, list):
                raise UpstreamError(
                    "Zoho Books returned an unexpected response.", code="zoho.unexpected_data"
                )
            rows.extend(r for r in batch if isinstance(r, dict))
            if not (payload.get("page_context") or {}).get("has_more_page"):
                return rows
        logger.warning("Zoho list exceeds the page ceiling", extra={"path": path})
        raise UpstreamError(
            f"There are more {list_key} than Clario is set to read "
            f"({self._max_pages * PER_PAGE:,}). Contact Crita support.",
            code="zoho.too_many_records",
        )

    async def _throttle(self) -> None:
        now = time.monotonic()
        while self._sent and now - self._sent[0] >= 60:
            self._sent.popleft()
        if len(self._sent) >= self._per_minute:
            await asyncio.sleep(60 - (now - self._sent[0]))
        self._sent.append(time.monotonic())

    async def _send(self, path: str, params: dict[str, str]) -> httpx.Response:
        for attempt in range(1, ATTEMPTS + 1):
            await self._throttle()
            try:
                response = await self._http.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == ATTEMPTS:
                    logger.warning(
                        "Zoho Books unreachable", extra={"path": path, "error": type(exc).__name__}
                    )
                    raise UpstreamError(
                        "Zoho Books could not be reached. Try again.", code="zoho.unavailable"
                    ) from None
                await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)
                continue
            self.calls += 1
            self._read_rate_limit(response)
            return response
        raise AssertionError("unreachable")

    def _read_rate_limit(self, response: httpx.Response) -> None:
        headers = response.headers
        try:
            limit = int(headers["x-rate-limit-limit"])
            remaining = int(headers["x-rate-limit-remaining"])
        except (KeyError, ValueError):
            return
        reading: dict[str, Any] = {"limit": limit, "remaining": remaining}
        reset = headers.get("x-rate-limit-reset", "")
        if reset.isdigit():  # seconds until the daily budget renews (verified in Phase 0)
            reading["reset_at"] = (utc_now() + timedelta(seconds=int(reset))).isoformat()
        self.rate_limit = reading

    @staticmethod
    def _raise_for(response: httpx.Response, payload: dict[str, Any], path: str) -> None:
        status, code = response.status_code, payload.get("code")
        if status == 200 and code in (0, None):
            return
        logger.warning(
            "Zoho Books request failed",
            extra={
                "path": path,
                "status": status,
                "zoho_code": code,
                "zoho_message": str(payload.get("message", ""))[:200],
            },
        )
        if status == 401:
            raise UpstreamError(
                "Zoho Books did not accept Clario's access.", code="zoho.unauthorized"
            )
        if status == 429:
            raise RateLimitedError(
                "Zoho Books' request limit was reached. Try again later.", code="zoho.rate_limited"
            )
        raise UpstreamError("Zoho Books returned an error. Try again.", code="zoho.error")
