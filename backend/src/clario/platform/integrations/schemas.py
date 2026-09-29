"""Integration API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from clario.platform.connections.schemas import ConnectionOut

ConnectionState = Literal[
    "not_connected", "pending", "connected", "needs_reauth", "error", "coming_soon"
]


class RegionOut(BaseModel):
    code: str
    label: str


class IntegrationTile(BaseModel):
    key: str
    name: str
    vendor: str
    domain: str
    domain_name: str
    summary: str
    reads: list[str] = Field(description="Plain-language list of the data Clario reads")
    read_only: bool
    availability: Literal["available", "coming_soon"]
    connection_state: ConnectionState
    connection: ConnectionOut | None = Field(description="The live connection, if any")
    regions: list[RegionOut] = Field(description="Data centers to choose from; first is default")
    account_noun: str = Field(description='What one external account is called ("organisation")')
    can_manage: bool = Field(description="Whether the caller may connect/disconnect it")


class IntegrationList(BaseModel):
    integrations: list[IntegrationTile]


class ConnectResponse(BaseModel):
    redirect_url: str = Field(
        description="Send the browser here to continue (e.g. provider consent)"
    )
