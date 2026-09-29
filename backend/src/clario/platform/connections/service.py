"""Connection lifecycle (plan §15.3, §17): connect → consent → callback → choose account →
connected; reconnect; disconnect.

Security properties (plan §17, §29):
  * The consent `state` is 32 random bytes, stored only as its SHA-256, bound to the workspace and
    the user who started, valid for 10 minutes and consumed atomically (single use). Consumption is
    committed before anything else, so a later failure cannot make it reusable.
  * The callback requires the same signed-in user, re-checks their membership and permission, and
    never renders anything: every outcome is a redirect to a path built here from trusted values.
  * Failure details go to the logs; the browser only receives a closed set of codes.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.dates import utc_now
from clario.core.errors import ClarioError, ConflictError, NotFoundError, ValidationFailedError
from clario.platform.access.deps import load_workspace_scope
from clario.platform.access.permissions import Permission
from clario.platform.access.scopes import ConnectionScope, WorkspaceScope
from clario.platform.audit.service import AuditAction, record
from clario.platform.connections import repository as repo
from clario.platform.connections import vault
from clario.platform.connections.models import Connection, ConnectionStatus, OAuthState
from clario.platform.conversations import repository as conversation_repo
from clario.platform.integrations import service as catalog
from clario.platform.integrations.contract import (
    ConnectFailedError,
    ConnectFailure,
    ConnectionContext,
    ExternalAccount,
    Grant,
    IntegrationPlugin,
)
from clario.platform.integrations.registry import Registry
from clario.platform.sync import repository as sync_repo
from clario.platform.web import ClientInfo
from clario.platform.workspaces import repository as workspace_repo
from clario.settings import Settings

logger = logging.getLogger(__name__)

STATE_TTL = timedelta(minutes=10)
STATE_RETENTION = timedelta(days=1)  # expired states are kept a day for a helpful error message
MAX_STATE_LENGTH = 256
CONNECTION_NOT_FOUND = "Connection not found."


def _hash_state(state: str) -> bytes:
    return hashlib.sha256(state.encode()).digest()


def narrow(scope: WorkspaceScope, connection: Connection, domain: str) -> ConnectionScope:
    """The only place a ConnectionScope is built — always from a connection read with `scope`."""
    assert connection.workspace_id == scope.workspace_id
    return ConnectionScope(
        workspace_id=scope.workspace_id,
        user_id=scope.user_id,
        role=scope.role,
        permissions=scope.permissions,
        timezone=scope.timezone,
        base_currency=scope.base_currency,
        fiscal_year_start_month=scope.fiscal_year_start_month,
        connection_id=connection.id,
        integration_key=connection.integration_key,
        domain=domain,
    )


async def connection_scope(
    session: AsyncSession, registry: Registry, scope: WorkspaceScope, connection_id: uuid.UUID
) -> ConnectionScope:
    connection = await repo.get_live(session, scope, connection_id)
    manifest = registry.manifest(connection.integration_key) if connection else None
    if connection is None or manifest is None:
        raise NotFoundError(CONNECTION_NOT_FOUND, code="connection.not_found")
    return narrow(scope, connection, manifest.domain)


async def get_connection(session: AsyncSession, scope: ConnectionScope) -> Connection:
    connection = await repo.get_live(session, scope, scope.connection_id)
    if connection is None:
        raise NotFoundError(CONNECTION_NOT_FOUND, code="connection.not_found")
    return connection


def connection_profile(connection: Connection, scope: WorkspaceScope) -> tuple[ZoneInfo, int]:
    """Time zone and fiscal-year start month of the connected account (its books decide what
    "today" and "this fiscal year" mean), falling back to the workspace's."""
    settings = connection.settings or {}
    try:
        tz = ZoneInfo(str(settings["timezone"])) if settings.get("timezone") else scope.timezone
    except (KeyError, ValueError):
        tz = scope.timezone
    month = settings.get("fiscal_year_start_month")
    fy = month if isinstance(month, int) and 1 <= month <= 12 else scope.fiscal_year_start_month
    return tz, fy


def _plugin(registry: Registry, scope: ConnectionScope) -> IntegrationPlugin:
    plugin = registry.plugin(scope.integration_key)
    if plugin is None:  # the connector was removed from the code
        raise ConflictError(
            "This integration is no longer available.", code="integration.not_available"
        )
    return plugin


def _audit(
    session: AsyncSession,
    action: AuditAction,
    scope: WorkspaceScope,
    connection_id: uuid.UUID | None,
    client: ClientInfo | None,
    **details: object,
) -> None:
    record(
        session,
        action,
        actor_user_id=scope.user_id,
        workspace_id=scope.workspace_id,
        target_type="connection",
        target_id=connection_id,
        client=client,
        details=details,
    )


# ---------------------------------------------------------------- connect


async def start_connect(
    session: AsyncSession,
    settings: Settings,
    registry: Registry,
    scope: WorkspaceScope,
    key: str,
    *,
    region: str | None,
    client: ClientInfo,
) -> str:
    """Run the connect gate, record a single-use state, and return the provider consent URL."""
    _, plugin = await catalog.connectable(session, registry, scope, key)
    state = secrets.token_urlsafe(32)
    consent = plugin.consent_redirect(settings, state=state, region=region)

    connection = await repo.live_connection_for(session, scope, key)
    reconnect = connection is not None and connection.external_account_id is not None
    if connection is None:
        connection = await repo.ensure_pending(session, scope, key, consent.region)
    now = utc_now()
    await repo.purge_states_before(session, now - STATE_RETENTION)
    repo.add_state(
        session,
        OAuthState(
            state_hash=_hash_state(state),
            workspace_id=scope.workspace_id,
            user_id=scope.user_id,
            integration_key=key,
            connection_id=connection.id,
            region=consent.region,
            expires_at=now + STATE_TTL,
        ),
    )
    _audit(
        session,
        AuditAction.INTEGRATION_CONNECT_STARTED,
        scope,
        connection.id,
        client,
        integration=key,
        region=consent.region,
        reconnect=reconnect,
    )
    return consent.url


async def complete_connect(
    session: AsyncSession,
    settings: Settings,
    registry: Registry,
    *,
    key: str,
    params: Mapping[str, str],
    user_id: uuid.UUID | None,
    client: ClientInfo,
) -> str:
    """Handle the provider's redirect. Always returns a redirect target; never raises."""
    app = settings.app_base_url.rstrip("/")
    neutral = f"{app}/w"
    plugin = registry.plugin(key)
    manifest = registry.manifest(key)
    raw_state = params.get("state", "")
    if plugin is None or manifest is None or not raw_state or len(raw_state) > MAX_STATE_LENGTH:
        return neutral

    state_hash = _hash_state(raw_state)
    state = await repo.consume_state(session, state_hash, key, utc_now())
    if state is None:
        return await _stale_state_target(session, state_hash, key, user_id, neutral, app)
    await session.commit()  # single use, whatever happens next

    if user_id is None:
        return f"{app}/login"
    if user_id != state.user_id:
        logger.warning("OAuth callback completed by a different user than the one who started it")
        return neutral
    try:
        scope = await load_workspace_scope(session, state.workspace_id, user_id)
    except ClarioError:
        return neutral
    flow = _Callback(
        session=session,
        settings=settings,
        plugin=plugin,
        scope=scope,
        key=key,
        connection_id=state.connection_id,
        client=client,
        base=f"{app}/w/{await workspace_repo.slug_for(session, scope)}/{key}",
    )

    if not scope.can(Permission.INTEGRATIONS_MANAGE):
        return flow.fail(ConnectFailure.FORBIDDEN)
    connection = (
        await repo.get_live(session, scope, state.connection_id) if state.connection_id else None
    )
    if connection is None:
        return flow.fail(ConnectFailure.STATE_INVALID, "connection no longer live")
    if "error" in params:
        return flow.fail(ConnectFailure.ACCESS_DENIED, params["error"][:64])
    try:
        grant = await plugin.exchange(settings, params, region=state.region)
    except ConnectFailedError as exc:
        return flow.fail(exc.failure, exc.log_detail)
    except ClarioError as exc:  # e.g. the server lost its configuration mid-flow
        return flow.fail(ConnectFailure.PROVIDER_ERROR, exc.code)

    cscope = narrow(scope, connection, manifest.domain)
    if connection.external_account_id is None:
        return await flow.authorised(cscope, connection, grant)
    return await flow.reconnected(cscope, connection, grant)


@dataclass(slots=True)
class _Callback:
    """The steps of one callback after the state and the user have been verified."""

    session: AsyncSession
    settings: Settings
    plugin: IntegrationPlugin
    scope: WorkspaceScope
    key: str
    connection_id: uuid.UUID | None
    client: ClientInfo
    base: str  # {APP_BASE_URL}/w/{slug}/{integration}

    def fail(self, failure: ConnectFailure, detail: str = "") -> str:
        logger.info(
            "Integration authorisation failed",
            extra={"integration": self.key, "failure": failure.value, "detail": detail},
        )
        _audit(
            self.session,
            AuditAction.INTEGRATION_CONNECT_FAILED,
            self.scope,
            self.connection_id,
            self.client,
            integration=self.key,
            failure=failure.value,
        )
        return f"{self.base}?{urlencode({'error': failure.value})}"

    async def authorised(
        self, cscope: ConnectionScope, connection: Connection, grant: Grant
    ) -> str:
        """First connection: keep the credentials; the user chooses an account next."""
        await vault.store(
            self.session, self.settings, cscope, grant.secret, granted_scopes=grant.granted_scopes
        )
        connection.region = grant.region
        connection.last_error_code = None
        _audit(
            self.session,
            AuditAction.INTEGRATION_AUTHORIZED,
            cscope,
            cscope.connection_id,
            self.client,
            integration=self.key,
            region=grant.region,
        )
        return f"{self.base}/setup"

    async def reconnected(
        self, cscope: ConnectionScope, connection: Connection, grant: Grant
    ) -> str:
        """Reconnect: accept the new credentials only if they still reach the chosen account."""
        savepoint = await self.session.begin_nested()
        try:
            await vault.store(
                self.session,
                self.settings,
                cscope,
                grant.secret,
                granted_scopes=grant.granted_scopes,
            )
            context = ConnectionContext(scope=cscope, session=self.session, settings=self.settings)
            visible = {a.id for a in await self.plugin.list_accounts(context)}
        except ClarioError as exc:
            await savepoint.rollback()
            await self._revoke_quietly(grant)
            return self.fail(ConnectFailure.PROVIDER_ERROR, exc.code)
        if connection.external_account_id not in visible:
            await savepoint.rollback()
            await self._revoke_quietly(grant)
            return self.fail(ConnectFailure.ACCOUNT_MISMATCH)
        await savepoint.commit()
        connection.status = ConnectionStatus.CONNECTED
        connection.region = grant.region
        connection.last_verified_at = utc_now()
        connection.last_error_code = None
        connection.last_error_at = None
        _audit(
            self.session,
            AuditAction.INTEGRATION_RECONNECTED,
            cscope,
            cscope.connection_id,
            self.client,
            integration=self.key,
        )
        return f"{self.base}?{urlencode({'reconnected': '1'})}"

    async def _revoke_quietly(self, grant: Grant) -> None:
        try:
            await self.plugin.revoke(self.settings, grant.secret)
        except Exception:
            logger.warning("Could not revoke unused credentials", extra={"integration": self.key})


async def _stale_state_target(
    session: AsyncSession,
    state_hash: bytes,
    key: str,
    user_id: uuid.UUID | None,
    neutral: str,
    app: str,
) -> str:
    """An expired or reused state: explain on the right page if it is the caller's own."""
    stale = await repo.find_state(session, state_hash, key)
    if stale is None or user_id is None or stale.user_id != user_id:
        return neutral
    try:
        scope = await load_workspace_scope(session, stale.workspace_id, user_id)
    except ClarioError:
        return neutral
    slug = await workspace_repo.slug_for(session, scope)
    return f"{app}/w/{slug}/{key}?{urlencode({'error': ConnectFailure.STATE_INVALID.value})}"


# ---------------------------------------------------------------- accounts


async def list_accounts(
    session: AsyncSession, settings: Settings, registry: Registry, scope: ConnectionScope
) -> list[ExternalAccount]:
    await get_connection(session, scope)
    context = ConnectionContext(scope=scope, session=session, settings=settings)
    return await _plugin(registry, scope).list_accounts(context)


async def select_account(
    session: AsyncSession,
    settings: Settings,
    registry: Registry,
    scope: ConnectionScope,
    account_id: str,
    client: ClientInfo,
) -> Connection:
    """Bind the connection to one external account; it becomes `connected`."""
    connection = await get_connection(session, scope)
    if connection.external_account_id is not None:
        raise ConflictError(
            f"This connection already uses {connection.external_account_name}. "
            "Disconnect it first to use a different one.",
            code="connection.account_locked",
        )
    plugin = _plugin(registry, scope)
    context = ConnectionContext(scope=scope, session=session, settings=settings)
    accounts = await plugin.list_accounts(context)
    if not any(a.id == account_id and a.selectable for a in accounts):
        raise ValidationFailedError(
            "That account is not available to the signed-in login.",
            code="connection.unknown_account",
        )
    profile = await plugin.account_profile(context, account_id)
    now = utc_now()
    connection.external_account_id = profile.id
    connection.external_account_name = profile.name
    connection.settings = {
        **dict(profile.extra),
        "currency": profile.currency,
        "timezone": profile.timezone,
        "fiscal_year_start_month": profile.fiscal_year_start_month,
    }
    connection.status = ConnectionStatus.CONNECTED
    connection.connected_by = scope.user_id
    connection.connected_at = now
    connection.last_verified_at = now
    connection.last_error_code = None
    connection.last_error_at = None
    _audit(
        session,
        AuditAction.INTEGRATION_CONNECTED,
        scope,
        scope.connection_id,
        client,
        integration=scope.integration_key,
        account_id=profile.id,
        account_name=profile.name,
    )
    # The route starts the initial import once this transaction has committed.
    return connection


# ---------------------------------------------------------------- disconnect


async def disconnect(
    session: AsyncSession,
    settings: Settings,
    registry: Registry,
    scope: ConnectionScope,
    client: ClientInfo,
) -> None:
    """Revoke at the provider (best effort), delete the credentials, purge the mirrored data,
    soft-delete, audit. The exclusive row lock waits for a dataset being written by a sync."""
    connection = await repo.lock_live(session, scope)
    if connection is None:
        raise NotFoundError(CONNECTION_NOT_FOUND, code="connection.not_found")
    plugin = registry.plugin(scope.integration_key)
    secret = await vault.load_optional(session, settings, scope)
    revoked = False
    if plugin is not None and secret is not None:
        try:
            await plugin.revoke(settings, secret)
            revoked = True
        except Exception:
            logger.warning(
                "Could not revoke credentials at the provider; deleting them anyway",
                extra={"integration": scope.integration_key},
            )
    await repo.delete_credential(session, scope)
    await repo.delete_states_for(session, scope)
    domain = registry.domain(scope.domain)
    for dataset in reversed(domain.datasets if domain else ()):  # references point backwards
        await dataset.purge(session, scope)
    await sync_repo.delete_datasets(session, scope)
    await conversation_repo.purge_connection(session, scope)  # they hold this data too
    connection.status = ConnectionStatus.DISCONNECTED
    connection.deleted_at = utc_now()
    _audit(
        session,
        AuditAction.INTEGRATION_DISCONNECTED,
        scope,
        scope.connection_id,
        client,
        integration=scope.integration_key,
        account_id=connection.external_account_id,
        revoked_at_provider=revoked,
    )


# ---------------------------------------------------------------- operator tooling (CLI only)


async def operator_scope(
    session: AsyncSession, registry: Registry, workspace_slug: str, key: str
) -> ConnectionScope:
    """The live connection of a workspace, scoped as its first owner (for `clario` commands)."""
    workspace = await workspace_repo.get_by_slug(session, workspace_slug)
    owner = await workspace_repo.first_owner(session, workspace.id) if workspace else None
    if workspace is None or owner is None:
        raise NotFoundError(
            f"No workspace {workspace_slug!r} with an owner.", code="workspace.not_found"
        )
    scope = await load_workspace_scope(session, workspace.id, owner)
    connection = await repo.live_connection_for(session, scope, key)
    if connection is None:
        raise NotFoundError(
            f"{workspace_slug} has no {key} connection.", code="connection.not_found"
        )
    return await connection_scope(session, registry, scope, connection.id)
