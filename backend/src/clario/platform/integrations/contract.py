"""Plug-in contracts: domains and connectors (plan §15.1, ADR-001).

* A **DomainModule** defines *what the business data is* and what users can see and ask
  (Finance now; Inventory, Leads later).
* An **IntegrationPlugin** (connector) defines *how to get that data from one external system*
  (Zoho Books now; Veloce, City Threads, … later). Its manifest names the domain it feeds.
* Catalog-only manifests (availability `coming_soon`) have no code: they only render as cards.

Clario Core depends on these contracts, never on a concrete domain or connector.

Connecting (Phase 5) is split so the security-critical flow exists once, in core
(`platform/connections`): core runs the permission gate, creates and consumes the single-use OAuth
state, stores credentials encrypted, moves the connection through its lifecycle and audits it.
A connector only supplies the provider specifics: the consent URL, the code exchange, the list of
accounts (e.g. Zoho organisations) and their profile, and token revocation.

Syncing (Phase 6) is split the same way: core's sync engine (`platform/sync`) runs, locks, times
and records syncs; a domain declares its **datasets** (how to write one kind of record into its
mirror, and how to purge it); a connector provides a **data source** implementing the domain's port
(e.g. `FinanceSource`). The engine never knows what an invoice is.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from fastapi import APIRouter
    from sqlalchemy.ext.asyncio import AsyncSession

    from clario.platform.access.scopes import ConnectionScope
    from clario.settings import Settings

KEY_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Integration keys become URL segments (/w/:workspace/:integration): these are taken by the app.
RESERVED_KEYS = frozenset({"settings", "api", "admin", "new", "i", "w", "login", "home"})


class Availability(StrEnum):
    AVAILABLE = "available"
    COMING_SOON = "coming_soon"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class IngestContext:
    """One dataset write, inside its own transaction (built by the sync engine)."""

    session: AsyncSession
    scope: ConnectionScope
    source: object  # the connector's implementation of the domain's port
    run_id: uuid.UUID
    today: date  # in the connected account's time zone
    fiscal_year_start_month: int  # 1-12


@dataclass(frozen=True, slots=True)
class IngestResult:
    row_count: int
    window_start: date | None = None
    window_end: date | None = None


class Dataset(Protocol):
    """One kind of mirrored record (invoices, expenses, ...), declared by a domain."""

    @property
    def key(self) -> str: ...

    @property
    def label(self) -> str: ...

    async def ingest(self, context: IngestContext) -> IngestResult:
        """Fetch from the source and replace the connection's rows in the dataset's window."""
        ...

    async def purge(self, session: AsyncSession, scope: ConnectionScope) -> None:
        """Delete every row of this dataset for the connection (on disconnect)."""
        ...


@dataclass(frozen=True, slots=True)
class DomainModule:
    key: str  # "finance"
    name: str  # "Finance"
    description: str
    # Written in this order by the sync engine and purged in reverse (references point backwards).
    datasets: tuple[Dataset, ...] = ()
    # Development/test data instead of the connector's source, when the settings ask for it.
    fixture_source: Callable[[Settings], object | None] | None = None
    # The domain's API (dashboards), mounted under /api/v1 by the composition root.
    router: APIRouter | None = None
    # The domain's assistant (an `clario.ai.runtime.agent.AssistantSpec`; typed loosely because
    # the AI layer sits above platform in the layering).
    assistant: object | None = None


@dataclass(frozen=True, slots=True)
class Region:
    """A provider data center the client can choose (e.g. Zoho India vs Zoho EU)."""

    code: str  # "in"
    label: str  # "India (zoho.in)"


@dataclass(frozen=True, slots=True)
class IntegrationManifest:
    key: str  # "zoho-books" — stable; used in URLs and the database
    name: str  # "Zoho Books"
    vendor: str  # "Zoho"
    domain: str  # key of the DomainModule this integration feeds
    summary: str  # one sentence shown on the card
    availability: Availability
    sort_order: int = 100
    reads: tuple[str, ...] = field(
        default_factory=tuple
    )  # plain-language list of what Clario reads
    read_only: bool = True
    regions: tuple[Region, ...] = field(default_factory=tuple)  # first one is the default
    account_noun: str = "account"  # what one external account is called ("organisation")


# ---------------------------------------------------------------- connecting


class ConnectFailure(StrEnum):
    """Why an authorisation attempt failed. Sent to the browser as `?error=<value>` (no details:
    those go to the logs), so the set is closed and the UI has a message for each."""

    ACCESS_DENIED = "access_denied"  # the user declined consent at the provider
    STATE_INVALID = "state_invalid"  # unknown, expired or already used
    FORBIDDEN = "forbidden"  # no longer allowed to manage integrations here
    SERVER_REJECTED = "server_rejected"  # provider redirect named a server outside the allow-list
    EXCHANGE_FAILED = "exchange_failed"  # the provider refused the authorisation code
    MISSING_SCOPES = "missing_scopes"  # the user granted less than Clario needs
    ACCOUNT_MISMATCH = "account_mismatch"  # reconnect with a login that cannot see the account
    PROVIDER_ERROR = "provider_error"  # the provider failed while Clario was checking access


class ConnectFailedError(Exception):
    """Raised by a connector during `exchange`; core turns it into a redirect with the code."""

    def __init__(self, failure: ConnectFailure, log_detail: str = "") -> None:
        self.failure = failure
        self.log_detail = log_detail  # for logs only; never shown to users
        super().__init__(f"{failure.value}: {log_detail}")


@dataclass(frozen=True, slots=True)
class ConsentRedirect:
    url: str  # the provider's consent page, with Clario's state
    region: str | None  # the region actually used (the default when none was chosen)


@dataclass(frozen=True, slots=True)
class Grant:
    """Credentials from a completed authorisation. `secret` is encrypted by core; never logged."""

    secret: Mapping[str, Any]
    granted_scopes: tuple[str, ...]
    region: str | None


@dataclass(frozen=True, slots=True)
class ExternalAccount:
    """One account the credentials can see (a Zoho organisation), offered for selection."""

    id: str
    name: str
    detail: str = ""  # a short secondary line, e.g. "INR · Asia/Kolkata"
    is_default: bool = False
    selectable: bool = True


@dataclass(frozen=True, slots=True)
class AccountProfile:
    """The chosen account's non-secret settings, stored on the connection."""

    id: str
    name: str
    currency: str | None = None  # ISO 4217, e.g. "INR"
    timezone: str | None = None  # IANA, e.g. "Asia/Kolkata"
    fiscal_year_start_month: int | None = None  # 1–12
    extra: Mapping[str, Any] = field(default_factory=dict)  # connector-specific, non-secret


@dataclass(frozen=True, slots=True)
class ConnectionContext:
    """What a connector receives to act on one connection — built by core after all checks."""

    scope: ConnectionScope
    session: AsyncSession
    settings: Settings


class IntegrationPlugin(Protocol):
    """A connector with code (plan §15.1)."""

    @property
    def manifest(self) -> IntegrationManifest: ...

    def consent_redirect(
        self, settings: Settings, *, state: str, region: str | None
    ) -> ConsentRedirect:
        """The provider consent URL. Raises a ClarioError for a bad region or missing config."""
        ...

    async def exchange(
        self, settings: Settings, callback: Mapping[str, str], *, region: str | None
    ) -> Grant:
        """Turn the provider's redirect parameters into credentials, or raise ConnectFailedError."""
        ...

    async def list_accounts(self, context: ConnectionContext) -> list[ExternalAccount]: ...

    async def account_profile(
        self, context: ConnectionContext, account_id: str
    ) -> AccountProfile: ...

    async def revoke(self, settings: Settings, secret: Mapping[str, Any]) -> None:
        """Best effort: invalidate the credentials at the provider (on disconnect)."""
        ...

    def data_source(self, context: ConnectionContext) -> object:
        """The connector's implementation of its domain's source port (e.g. FinanceSource)."""
        ...
