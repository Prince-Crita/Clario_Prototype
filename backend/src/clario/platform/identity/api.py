"""Authentication routes (plan §11.2, §12).

POST /auth/login     → sets the session cookie, returns the session (incl. CSRF token)
GET  /auth/session   → current session (SPA bootstrap); 401 when signed out
POST /auth/logout    → revokes this session, clears the cookie
POST /auth/password  → change password; signs out every other session
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request, Response, status

from clario.platform.access.permissions import Role
from clario.platform.identity import service
from clario.platform.identity.deps import AuthDep
from clario.platform.identity.ratelimit import SlidingWindowLimiter
from clario.platform.identity.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    SessionOut,
    UserOut,
)
from clario.platform.identity.service import AuthContext
from clario.platform.identity.tokens import cookie_name, csrf_token_for
from clario.platform.web import ClientInfoDep, SessionDep, SettingsDep
from clario.platform.workspaces import repository as workspace_repo
from clario.platform.workspaces.schemas import WorkspaceSummary
from clario.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])


async def _session_out(
    session: SessionDep, settings: Settings, auth: AuthContext, expires_at: datetime | None = None
) -> SessionOut:
    rows = await workspace_repo.list_for_user(session, auth.user_id)
    return SessionOut(
        user=UserOut(
            id=auth.user_id,
            email=auth.email,
            full_name=auth.full_name,
            is_platform_admin=auth.is_platform_admin,
        ),
        workspaces=[
            WorkspaceSummary(id=w.id, slug=w.slug, name=w.name, status=w.status, role=Role(m.role))
            for w, m in rows
        ],
        csrf_token=csrf_token_for(auth.token_hash, settings.session_secret.get_secret_value()),
        expires_at=expires_at,
    )


@router.post(
    "/login",
    response_model=SessionOut,
    summary="Sign in",
    responses={
        401: {"description": "Incorrect email or password"},
        429: {"description": "Too many attempts"},
    },
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    client: ClientInfoDep,
) -> SessionOut:
    limiter: SlidingWindowLimiter = request.app.state.login_limiter
    result = await service.login(
        session,
        settings,
        email=payload.email,
        password=payload.password,
        client=client,
        ip_limiter=limiter,
    )
    response.set_cookie(
        cookie_name(settings.session_cookie_secure),
        result.token,
        expires=result.expires_at,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return await _session_out(session, settings, result.auth, result.expires_at)


@router.get("/session", response_model=SessionOut, summary="Current session")
async def current_session(auth: AuthDep, session: SessionDep, settings: SettingsDep) -> SessionOut:
    return await _session_out(session, settings, auth)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(
    auth: AuthDep,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    client: ClientInfoDep,
) -> None:
    await service.logout(session, auth, client)
    response.delete_cookie(
        cookie_name(settings.session_cookie_secure),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change my password")
async def change_password(
    payload: ChangePasswordRequest, auth: AuthDep, session: SessionDep, client: ClientInfoDep
) -> None:
    await service.change_password(
        session,
        auth,
        current_password=payload.current_password,
        new_password=payload.new_password,
        client=client,
    )
