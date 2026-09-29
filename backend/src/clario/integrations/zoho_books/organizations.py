"""Zoho Books organisations: the accounts a connection can be bound to (plan §16.4, §17).

Listing organisations reads only their names and basic settings, never books data. The chosen
organisation's profile comes from the detail call, which gives `fiscal_year_start_month` as a month
NAME ("april"); the list call gives a 0-based number (verified in Phase 0), so the detail is used.
"""

from __future__ import annotations

from typing import Any

from clario.core.errors import ValidationFailedError
from clario.core.text import normalise_typography
from clario.integrations.zoho_books.client import ZohoBooksClient
from clario.integrations.zoho_books.tokens import valid_secret
from clario.platform.integrations.contract import AccountProfile, ConnectionContext, ExternalAccount

MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        start=1,
    )
}


def _text(value: Any) -> str:
    return normalise_typography(str(value or "")).strip()


def to_account(org: dict[str, Any]) -> ExternalAccount:
    detail = " · ".join(
        p for p in (_text(org.get("currency_code")), _text(org.get("time_zone"))) if p
    )
    return ExternalAccount(
        id=_text(org.get("organization_id")),
        name=_text(org.get("name")) or "Unnamed organisation",
        detail=detail,
        is_default=bool(org.get("is_default_org")),
        selectable=not org.get("isOrgNotSupported", False),
    )


def to_profile(org: dict[str, Any]) -> AccountProfile:
    month = MONTHS.get(_text(org.get("fiscal_year_start_month")).lower())
    return AccountProfile(
        id=_text(org.get("organization_id")),
        name=_text(org.get("name")) or "Unnamed organisation",
        currency=_text(org.get("currency_code")) or None,
        timezone=_text(org.get("time_zone")) or None,
        fiscal_year_start_month=month,
        extra={"country": _text(org.get("country")) or None},
    )


async def list_organizations(context: ConnectionContext) -> list[ExternalAccount]:
    secret = await valid_secret(context)
    async with ZohoBooksClient(secret.api_domain, secret.access_token) as client:
        payload = await client.get("organizations")
    orgs = payload.get("organizations") or []
    return [to_account(o) for o in orgs if isinstance(o, dict) and o.get("organization_id")]


async def organization_profile(context: ConnectionContext, organization_id: str) -> AccountProfile:
    if not organization_id.isdigit():  # also keeps the id from altering the request path
        raise ValidationFailedError("Unknown organisation.", code="connection.unknown_account")
    secret = await valid_secret(context)
    async with ZohoBooksClient(secret.api_domain, secret.access_token) as client:
        payload = await client.get(f"organizations/{organization_id}")
    org = payload.get("organization")
    if not isinstance(org, dict) or _text(org.get("organization_id")) != organization_id:
        raise ValidationFailedError("Unknown organisation.", code="connection.unknown_account")
    return to_profile(org)
