"""FastAPI dependencies for auth and tenant context."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from clario.db.models import ApiKey, Membership, Tenant, TenantStatus, User
from clario.db.session import get_db
from clario.security.crypto import decode_access_token, verify_api_key
from clario.tenancy.service import ForbiddenError, NotFoundError, require_membership

bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    tenant: Tenant | None = None
    membership: Membership | None = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    token = credentials.credentials
    if token.startswith("clr_"):
        return await _user_from_api_key(db, token)
    try:
        payload = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc
    user = await db.scalar(select(User).where(User.id == payload.get("sub"), User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


async def _user_from_api_key(db: AsyncSession, raw_key: str) -> User:
    prefix = raw_key[:12]
    keys = (
        await db.scalars(
            select(ApiKey).where(
                ApiKey.key_prefix == prefix,
                ApiKey.is_active.is_(True),
                ApiKey.revoked_at.is_(None),
            )
        )
    ).all()
    for key in keys:
        if verify_api_key(raw_key, key.key_hash):
            # API keys authenticate as the creating user when present; otherwise a synthetic check fails.
            if key.created_by_user_id:
                user = await db.scalar(select(User).where(User.id == key.created_by_user_id))
                if user and user.is_active:
                    return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")


async def get_auth_context(
    user: User = Depends(get_current_user),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if not x_tenant_id:
        return AuthContext(user=user)
    try:
        tenant, membership = await require_membership(db, tenant_id=x_tenant_id, user_id=user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return AuthContext(user=user, tenant=tenant, membership=membership)


async def require_tenant(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if auth.tenant is None or auth.membership is None:
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-Id header is required for this endpoint.",
        )
    return auth


async def load_tenant_with_zoho(db: AsyncSession, tenant_id: str) -> Tenant:
    tenant = await db.scalar(
        select(Tenant)
        .where(Tenant.id == tenant_id, Tenant.status == TenantStatus.ACTIVE)
        .options(selectinload(Tenant.zoho_connection))
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return tenant
