"""Connection API contracts. Nothing here ever carries a secret."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ConnectionStatusOut = Literal["pending", "connected", "needs_reauth", "error"]


class ConnectionAccount(BaseModel):
    """The external account the connection reads (e.g. a Zoho Books organisation)."""

    id: str
    name: str
    currency: str | None = None
    timezone: str | None = None
    fiscal_year_start_month: int | None = None


class ConnectionOut(BaseModel):
    id: uuid.UUID
    integration_key: str
    status: ConnectionStatusOut
    authorised: bool = Field(description="Credentials are stored (consent was given)")
    account: ConnectionAccount | None
    region: str | None
    connected_at: datetime | None
    connected_by: str | None = Field(description="Name of the person who connected it")
    last_verified_at: datetime | None
    last_error_code: str | None


class ExternalAccountOut(BaseModel):
    id: str
    name: str
    detail: str
    is_default: bool
    selectable: bool


class ExternalAccountList(BaseModel):
    accounts: list[ExternalAccountOut]


class SelectAccountRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=128)


class ConnectRequest(BaseModel):
    region: str | None = Field(
        default=None, max_length=16, description="Provider data center; the default if omitted"
    )
