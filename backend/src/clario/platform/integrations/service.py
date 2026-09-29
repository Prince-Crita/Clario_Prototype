"""Integration use cases: the workspace catalog, the connect gate, and operator visibility.

The connect gate is the single place that decides whether a workspace may start connecting an
integration. Order matters (plan §13.3): unknown or hidden → 404 (indistinguishable), coming soon /
retired → 409, missing permission → 403, and only then is the connector's code called
(by `platform.connections.service`, which owns the connection lifecycle).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from clario.platform.access.permissions import Permission
from clario.platform.access.scopes import WorkspaceScope
from clario.platform.audit.service import ActorType, AuditAction, record
from clario.platform.integrations import repository as repo
from clario.platform.integrations.contract import (
    Availability,
    IntegrationManifest,
    IntegrationPlugin,
)
from clario.platform.integrations.registry import Registry
from clario.platform.workspaces import repository as workspace_repo

NOT_FOUND = "Integration not found."


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    manifest: IntegrationManifest
    domain_name: str
    # "not_connected" | "coming_soon" here; the API overlays the live connection's status.
    connection_state: str


def _visible(manifest: IntegrationManifest, overrides: dict[str, bool]) -> bool:
    if manifest.availability is Availability.RETIRED:
        return False
    default = manifest.availability is Availability.AVAILABLE
    return overrides.get(manifest.key, default)


async def workspace_catalog(
    session: AsyncSession, registry: Registry, scope: WorkspaceScope
) -> list[CatalogEntry]:
    overrides = await repo.visibility_overrides(session, scope)
    return [
        CatalogEntry(
            manifest=m,
            domain_name=registry.domain_name(m.domain),
            connection_state="coming_soon"
            if m.availability is Availability.COMING_SOON
            else "not_connected",
        )
        for m in registry.manifests
        if _visible(m, overrides)
    ]


async def catalog_entry(
    session: AsyncSession, registry: Registry, scope: WorkspaceScope, key: str
) -> CatalogEntry:
    manifest = await visible_manifest(session, registry, scope, key)
    coming_soon = manifest.availability is Availability.COMING_SOON
    return CatalogEntry(
        manifest=manifest,
        domain_name=registry.domain_name(manifest.domain),
        connection_state="coming_soon" if coming_soon else "not_connected",
    )


async def visible_manifest(
    session: AsyncSession, registry: Registry, scope: WorkspaceScope, key: str
) -> IntegrationManifest:
    manifest = registry.manifest(key)
    if manifest is None or not _visible(manifest, await repo.visibility_overrides(session, scope)):
        raise NotFoundError(NOT_FOUND, code="integration.not_found")
    return manifest


async def connectable(
    session: AsyncSession, registry: Registry, scope: WorkspaceScope, key: str
) -> tuple[IntegrationManifest, IntegrationPlugin]:
    """The connect gate. Returns the manifest and connector only if every check passes."""
    manifest = await visible_manifest(session, registry, scope, key)
    plugin = registry.plugin(key)
    if manifest.availability is not Availability.AVAILABLE or plugin is None:
        raise ConflictError(
            f"{manifest.name} is not available yet.", code="integration.not_available"
        )
    if not scope.can(Permission.INTEGRATIONS_MANAGE):
        raise PermissionDeniedError(
            f"Only workspace owners and admins can connect {manifest.name}.",
            code="auth.forbidden",
            extra={"required": Permission.INTEGRATIONS_MANAGE.value},
        )
    return manifest, plugin


async def set_workspace_visibility(
    session: AsyncSession, registry: Registry, *, workspace_slug: str, key: str, visible: bool
) -> IntegrationManifest:
    """Operator action (CLI): show or hide one integration card for one workspace."""
    manifest = registry.manifest(key)
    if manifest is None:
        raise NotFoundError(f"No integration with key {key!r}.", code="integration.not_found")
    workspace = await workspace_repo.get_by_slug(session, workspace_slug)
    if workspace is None:
        raise NotFoundError(
            f"No workspace with slug {workspace_slug!r}.", code="workspace.not_found"
        )
    # The CLI may run before the API has ever started: make sure the catalog row (FK target) exists.
    await repo.upsert_catalog(session, registry.manifests)
    await repo.set_visibility(session, workspace.id, key, visible)
    record(
        session,
        AuditAction.INTEGRATION_VISIBILITY_CHANGED,
        actor_type=ActorType.SYSTEM,
        workspace_id=workspace.id,
        target_type="integration",
        target_id=key,
        details={"visible": visible},
    )
    return manifest
