"""Zoho data centers (plan §16.1, §39).

The allow-list is also a security control: Clario only ever sends the client secret to an
accounts server listed here, and only sends access tokens to an API domain listed here, even though
Zoho names both at runtime (`accounts-server` on the redirect, `api_domain` in the token response).
India is first: Crita and its current clients are India-based (only India is verified, plan R3).
"""

from __future__ import annotations

from dataclasses import dataclass

from clario.platform.integrations.contract import Region


@dataclass(frozen=True, slots=True)
class DataCenter:
    code: str
    label: str
    accounts_server: str
    api_domain: str


DATA_CENTERS: dict[str, DataCenter] = {
    dc.code: dc
    for dc in (
        DataCenter("in", "India (zoho.in)", "https://accounts.zoho.in", "https://www.zohoapis.in"),
        DataCenter(
            "com",
            "United States (zoho.com)",
            "https://accounts.zoho.com",
            "https://www.zohoapis.com",
        ),
        DataCenter("eu", "Europe (zoho.eu)", "https://accounts.zoho.eu", "https://www.zohoapis.eu"),
        DataCenter(
            "au",
            "Australia (zoho.com.au)",
            "https://accounts.zoho.com.au",
            "https://www.zohoapis.com.au",
        ),
        DataCenter("jp", "Japan (zoho.jp)", "https://accounts.zoho.jp", "https://www.zohoapis.jp"),
        DataCenter(
            "ca",
            "Canada (zohocloud.ca)",
            "https://accounts.zohocloud.ca",
            "https://www.zohoapis.ca",
        ),
    )
}
REGIONS = tuple(Region(code=dc.code, label=dc.label) for dc in DATA_CENTERS.values())


def _norm(url: str) -> str:
    return url.strip().rstrip("/").lower()


def by_accounts_server(url: str) -> DataCenter | None:
    return next((dc for dc in DATA_CENTERS.values() if dc.accounts_server == _norm(url)), None)


def allowed_api_domain(url: str) -> str | None:
    """The canonical API domain if `url` is an allow-listed one, else None."""
    return next(
        (dc.api_domain for dc in DATA_CENTERS.values() if dc.api_domain == _norm(url)), None
    )
