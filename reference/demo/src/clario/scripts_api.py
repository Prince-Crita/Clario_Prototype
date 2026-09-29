"""Live Zoho smoke checks used by `clario smoke` and scripts/zoho_smoke.py."""

from __future__ import annotations

import json
from typing import Any

from clario.config import get_settings
from clario.logging import get_logger
from clario.zoho.client import ZohoBooksClient
from clario.zoho.errors import ZohoError

logger = get_logger("clario.smoke")


async def run_smoke() -> int:
    settings = get_settings()
    if not settings.zoho_ready():
        print("Zoho is not authorized. Copy .env.example to .env, then visit /oauth/zoho/start.")
        return 1
    client = ZohoBooksClient(settings)
    results: list[tuple[str, str, Any]] = []
    try:
        orgs = await client.list_organizations()
        results.append(("organizations", "ok", [org.model_dump(mode="json") for org in orgs]))
        org = await client.get_current_organization()
        results.append(
            (
                "current_organization",
                "ok",
                {
                    "organization_id": org.organization_id,
                    "name": org.name,
                    "currency_code": org.currency_code,
                    "api_base": settings.zoho_api_base_url,
                },
            )
        )
        checks = [
            ("invoices", client.list_invoices),
            ("customers", client.list_customers),
            ("payments", client.list_payments),
            ("expenses", client.list_expenses),
            ("items", client.list_items),
        ]
        for name, loader in checks:
            try:
                rows = await loader()
                results.append((name, "ok", {"count": len(rows), "sample": rows[0].model_dump(mode="json") if rows else None}))
            except ZohoError as exc:
                results.append((name, "error", str(exc)))
        for report in ("profitandloss", "salesbycustomer", "salesbyitem"):
            try:
                payload = await client.get_report(report)
                results.append((f"report:{report}", "ok", {"keys": sorted(payload.keys())}))
            except ZohoError as exc:
                results.append((f"report:{report}", "error", str(exc)))
    finally:
        await client.aclose()

    failed = 0
    for name, status, detail in results:
        print(f"[{status}] {name}")
        print(json.dumps(detail, indent=2, default=str)[:2000])
        print()
        if status != "ok" and not name.startswith("report:"):
            failed += 1
    if failed:
        print(f"{failed} required check(s) failed.")
        return 1
    print("Zoho smoke checks passed.")
    return 0
