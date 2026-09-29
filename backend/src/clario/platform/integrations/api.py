"""Integration catalog routes (plan §11.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path

from clario.platform.access.deps import require
from clario.platform.access.permissions import Permission
from clario.platform.access.scopes import WorkspaceScope
from clario.platform.connections import repository as connection_repo
from clario.platform.connections import service as connections
from clario.platform.connections import views
from clario.platform.connections.models import Connection
from clario.platform.connections.schemas import ConnectionOut, ConnectRequest
from clario.platform.integrations import service
from clario.platform.integrations.deps import RegistryDep
from clario.platform.integrations.schemas import (
    ConnectResponse,
    IntegrationList,
    IntegrationTile,
    RegionOut,
)
from clario.platform.web import ClientInfoDep, SessionDep, SettingsDep

router = APIRouter(prefix="/workspaces/{workspace_id}/integrations", tags=["integrations"])
CanView = Annotated[WorkspaceScope, Depends(require(Permission.WORKSPACE_VIEW))]
IntegrationKey = Annotated[str, Path(max_length=64, description="Integration key, e.g. zoho-books")]


def _tile(
    entry: service.CatalogEntry, scope: WorkspaceScope, connection: ConnectionOut | None
) -> IntegrationTile:
    m = entry.manifest
    return IntegrationTile(
        key=m.key,
        name=m.name,
        vendor=m.vendor,
        domain=m.domain,
        domain_name=entry.domain_name,
        summary=m.summary,
        reads=list(m.reads),
        read_only=m.read_only,
        availability=m.availability.value,  # retired integrations are never listed
        connection_state=connection.status if connection else entry.connection_state,
        connection=connection,
        regions=[RegionOut(code=r.code, label=r.label) for r in m.regions],
        account_noun=m.account_noun,
        can_manage=scope.can(Permission.INTEGRATIONS_MANAGE),
    )


async def _connections_by_key(
    session: SessionDep, scope: WorkspaceScope, live: dict[str, Connection]
) -> dict[str, ConnectionOut]:
    described = await views.describe(session, scope, live.values())
    return {key: described[c.id] for key, c in live.items()}


@router.get("", response_model=IntegrationList, summary="Integrations for this workspace")
async def list_integrations(
    scope: CanView, session: SessionDep, registry: RegistryDep
) -> IntegrationList:
    entries = await service.workspace_catalog(session, registry, scope)
    by_key = await _connections_by_key(
        session, scope, await connection_repo.live_connections(session, scope)
    )
    return IntegrationList(
        integrations=[_tile(e, scope, by_key.get(e.manifest.key)) for e in entries]
    )


@router.get("/{integration}", response_model=IntegrationTile, summary="One integration")
async def get_integration(
    integration: IntegrationKey, scope: CanView, session: SessionDep, registry: RegistryDep
) -> IntegrationTile:
    entry = await service.catalog_entry(session, registry, scope, integration)
    live = await connection_repo.live_connection_for(session, scope, integration)
    by_key = await _connections_by_key(session, scope, {integration: live} if live else {})
    return _tile(entry, scope, by_key.get(integration))


@router.post(
    "/{integration}/connect",
    response_model=ConnectResponse,
    summary="Start connecting (or reconnecting) an integration",
    responses={
        403: {"description": "Requires integrations.manage"},
        404: {"description": "Unknown or not visible to this workspace"},
        409: {"description": "Not available yet (coming soon)"},
    },
)
async def connect(
    integration: IntegrationKey,
    scope: CanView,
    session: SessionDep,
    settings: SettingsDep,
    client: ClientInfoDep,
    registry: RegistryDep,
    body: Annotated[ConnectRequest | None, Body()] = None,
) -> ConnectResponse:
    url = await connections.start_connect(
        session,
        settings,
        registry,
        scope,
        integration,
        region=body.region if body else None,
        client=client,
    )
    return ConnectResponse(redirect_url=url)
