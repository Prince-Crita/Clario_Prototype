"""`AgentContext` (plan §18.2): everything an assistant turn knows, built by the SERVER.

The scope (workspace, user, connection, domain) comes from the authenticated route, never from
model output; tools receive this object and cannot be given another tenant's identifiers.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from clario.platform.access.scopes import ConnectionScope


@dataclass(frozen=True, slots=True)
class OtherModule:
    """Another Clario module in this workspace, named so the assistant can redirect (§21.3)."""

    name: str  # "Veloce Inventory"
    domain_name: str  # "Inventory"
    available: bool  # False for coming-soon cards


@dataclass(frozen=True, slots=True)
class AgentContext:
    scope: ConnectionScope
    session: AsyncSession
    conversation_id: uuid.UUID | None
    workspace_name: str
    system_name: str  # "Zoho Books"
    organisation: str  # the connected account, e.g. the Zoho organisation name
    currency: str
    timezone: str
    today: date
    fiscal_year_start_month: int
    fiscal_year: str  # "FY 2026-27"
    other_modules: tuple[OtherModule, ...]
    clock: Callable[[], datetime]
