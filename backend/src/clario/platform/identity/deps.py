"""FastAPI dependency: the signed-in user for this request (plan §12)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from clario.platform.identity import service
from clario.platform.identity.service import AuthContext
from clario.platform.identity.tokens import cookie_name
from clario.platform.web import SessionDep, SettingsDep


async def current_auth(request: Request, session: SessionDep, settings: SettingsDep) -> AuthContext:
    token = request.cookies.get(cookie_name(settings.session_cookie_secure))
    return await service.authenticate(session, settings, token)


AuthDep = Annotated[AuthContext, Depends(current_auth)]
