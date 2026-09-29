"""Connection routes (plan §11.2, §17).

The OAuth callback is shared by every OAuth connector: `/oauth/{integration}/callback`, which for
Zoho Books is exactly the registered `ZOHO_REDIRECT_URI` path. Connector code never handles the
callback itself; it only exchanges the code (see `IntegrationPlugin.exchange`).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Path, Request, Response, status
from fastapi.responses import RedirectResponse

from clario.core.errors import AuthenticationError
from clario.platform.connections import service, views
from clario.platform.connections.deps import ManageConnection, ViewConnection
from clario.platform.connections.schemas import (
    ConnectionOut,
    ExternalAccountList,
    ExternalAccountOut,
    SelectAccountRequest,
)
from clario.platform.identity import service as identity
from clario.platform.identity.tokens import cookie_name
from clario.platform.integrations.deps import RegistryDep
from clario.platform.sync.models import SyncTrigger
from clario.platform.sync.service import SyncRunner
from clario.platform.web import ClientInfoDep, SessionDep, SettingsDep

router = APIRouter(tags=["connections"])
BASE = "/workspaces/{workspace_id}/connections/{connection_id}"
MAX_PARAM_LENGTH = 2048


async def _out(session: SessionDep, scope: ViewConnection) -> ConnectionOut:
    connection = await service.get_connection(session, scope)
    return (await views.describe(session, scope, [connection]))[connection.id]


@router.get(BASE, response_model=ConnectionOut, summary="One connection")
async def get_connection(scope: ViewConnection, session: SessionDep) -> ConnectionOut:
    return await _out(session, scope)


@router.delete(
    BASE,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect: revoke access, delete credentials, remove the connection",
)
async def disconnect(
    scope: ManageConnection,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    client: ClientInfoDep,
) -> Response:
    await service.disconnect(session, settings, registry, scope, client)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    f"{BASE}/accounts",
    response_model=ExternalAccountList,
    summary="Accounts the authorised login can see (e.g. Zoho organisations)",
)
async def list_accounts(
    scope: ManageConnection, session: SessionDep, settings: SettingsDep, registry: RegistryDep
) -> ExternalAccountList:
    accounts = await service.list_accounts(session, settings, registry, scope)
    return ExternalAccountList(
        accounts=[
            ExternalAccountOut(
                id=a.id,
                name=a.name,
                detail=a.detail,
                is_default=a.is_default,
                selectable=a.selectable,
            )
            for a in accounts
        ]
    )


@router.post(
    f"{BASE}/account",
    response_model=ConnectionOut,
    summary="Choose the account this connection reads",
    responses={409: {"description": "An account is already chosen"}},
)
async def select_account(
    body: SelectAccountRequest,
    scope: ManageConnection,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    client: ClientInfoDep,
    request: Request,
    background: BackgroundTasks,
) -> ConnectionOut:
    await service.select_account(session, settings, registry, scope, body.account_id, client)
    # Commit now: the background import must see the connection as connected, and FastAPI does
    # not guarantee the request's unit of work commits before background tasks run.
    await session.commit()
    runner: SyncRunner = request.app.state.sync
    background.add_task(runner.start_quietly, scope, SyncTrigger.INITIAL, scope.user_id)
    return await _out(session, scope)


@router.get(
    "/oauth/{integration}/callback",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Provider redirect target (always answers with a redirect into the app)",
)
async def oauth_callback(
    integration: Annotated[str, Path(max_length=64)],
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    client: ClientInfoDep,
) -> RedirectResponse:
    params = {
        k: v for k, v in request.query_params.items() if len(k) <= 64 and len(v) <= MAX_PARAM_LENGTH
    }
    try:
        auth = await identity.authenticate(
            session, settings, request.cookies.get(cookie_name(settings.session_cookie_secure))
        )
        user_id = auth.user_id
    except AuthenticationError:
        user_id = None
    target = await service.complete_connect(
        session, settings, registry, key=integration, params=params, user_id=user_id, client=client
    )
    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)
