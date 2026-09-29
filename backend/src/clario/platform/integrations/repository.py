"""All SQL for the catalog and workspace visibility."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from clario.platform.access.scopes import WorkspaceScope
from clario.platform.integrations.contract import Availability, IntegrationManifest
from clario.platform.integrations.models import IntegrationRecord, WorkspaceIntegration


async def upsert_catalog(session: AsyncSession, manifests: Iterable[IntegrationManifest]) -> None:
    """Insert or update every manifest; mark keys no longer in code as retired. Idempotent."""
    manifests = list(manifests)
    for m in manifests:
        values = {
            "key": m.key,
            "name": m.name,
            "vendor": m.vendor,
            "domain": m.domain,
            "summary": m.summary,
            "availability": m.availability.value,
            "sort_order": m.sort_order,
        }
        statement = insert(IntegrationRecord).values(**values)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[IntegrationRecord.key],
                set_={k: statement.excluded[k] for k in values if k != "key"},
            )
        )
    await session.execute(
        update(IntegrationRecord)
        .where(IntegrationRecord.key.not_in([m.key for m in manifests]))
        .values(availability=Availability.RETIRED.value)
    )


async def visibility_overrides(session: AsyncSession, scope: WorkspaceScope) -> dict[str, bool]:
    rows = await session.execute(
        select(WorkspaceIntegration.integration_key, WorkspaceIntegration.is_visible).where(
            WorkspaceIntegration.workspace_id == scope.workspace_id
        )
    )
    return {row.integration_key: row.is_visible for row in rows}


async def set_visibility(
    session: AsyncSession, workspace_id: uuid.UUID, integration_key: str, visible: bool
) -> None:
    statement = insert(WorkspaceIntegration).values(
        workspace_id=workspace_id, integration_key=integration_key, is_visible=visible
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[
                WorkspaceIntegration.workspace_id,
                WorkspaceIntegration.integration_key,
            ],
            set_={"is_visible": statement.excluded.is_visible},
        )
    )
