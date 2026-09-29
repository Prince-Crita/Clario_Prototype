"""Auth, tenant, and Zoho OAuth API routes for multi-tenant Clario."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from clario.api.deps import AuthContext, get_auth_context, get_current_user, require_tenant
from clario.config import get_settings
from clario.db.models import MembershipRole, User
from clario.db.session import get_db
from clario.logging import get_logger
from clario.security.crypto import create_access_token
from clario.tenancy.service import (
    TenancyError,
    add_member,
    authenticate_user,
    build_tenant_oauth,
    consume_oauth_state,
    create_oauth_state,
    create_tenant,
    list_user_tenants,
    register_user,
    require_membership,
    write_audit,
)
from clario.zoho.client import ZohoBooksClient
from clario.zoho.errors import ZohoAuthError, ZohoError

router = APIRouter(prefix="/api")
logger = get_logger("clario.api.tenancy")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = ""
    tenant_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    tenant_id: str | None = None


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = MembershipRole.MEMBER


class SelectOrgRequest(BaseModel):
    organization_id: str


# Zoho Books data centers → accounts + Books API base URLs.
# Each workspace can store its own OAuth client id/secret (+ tokens).
# Platform ZOHO_CLIENT_* in env is only a fallback (e.g. Crita's own workspace).
ZOHO_DATA_CENTERS: dict[str, tuple[str, str]] = {
    "in": ("https://accounts.zoho.in", "https://www.zohoapis.in/books/v3"),
    "com": ("https://accounts.zoho.com", "https://www.zohoapis.com/books/v3"),
    "eu": ("https://accounts.zoho.eu", "https://www.zohoapis.eu/books/v3"),
    "au": ("https://accounts.zoho.com.au", "https://www.zohoapis.com.au/books/v3"),
    "jp": ("https://accounts.zoho.jp", "https://www.zohoapis.jp/books/v3"),
    "ca": ("https://accounts.zohocloud.ca", "https://www.zohoapis.ca/books/v3"),
}


class ZohoSettingsRequest(BaseModel):
    """Per-tenant Zoho connection settings (multi-tenant)."""

    data_center: str = Field(default="in", description="Zoho DC: in, com, eu, au, jp, ca")
    organization_id: str = ""
    client_id: str = Field(
        default="",
        description="Zoho API Console Client ID for this workspace. Empty = leave unchanged.",
    )
    client_secret: str = Field(
        default="",
        description="Zoho API Console Client Secret. Empty = leave existing secret unchanged.",
    )
    refresh_token: str = Field(
        default="",
        description="Optional Zoho refresh token for this workspace. Prefer OAuth connect.",
    )


def _data_center_from_urls(accounts_url: str) -> str:
    host = (accounts_url or "").lower()
    for code, (accounts, _) in ZOHO_DATA_CENTERS.items():
        if accounts.split("//", 1)[-1] in host:
            return code
    return "in"


def _mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 4:
        return "••••"
    return f"••••••••{secret[-4:]}"


def _tenant_public(tenant, membership=None) -> dict:
    conn = tenant.zoho_connection
    settings = get_settings()
    secret = ""
    if conn and conn.encrypted_oauth_client_secret:
        from clario.security.crypto import decrypt_secret

        try:
            secret = decrypt_secret(conn.encrypted_oauth_client_secret)
        except Exception:  # noqa: BLE001
            secret = ""
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "role": membership.role if membership else None,
        "zoho": {
            "is_connected": bool(conn and conn.is_connected),
            "organization_id": conn.organization_id if conn else "",
            "organization_name": conn.organization_name if conn else "",
            "currency_code": conn.currency_code if conn else "",
            "accounts_url": conn.accounts_url if conn else "",
            "api_base_url": conn.api_base_url if conn else "",
            "data_center": _data_center_from_urls(conn.accounts_url if conn else ""),
            "has_refresh_token": bool(conn and conn.encrypted_refresh_token),
            "client_id": (conn.oauth_client_id if conn else "") or "",
            "client_secret_configured": bool(secret),
            "client_secret_masked": _mask_secret(secret),
            "uses_platform_oauth_app": bool(
                conn
                and not (conn.oauth_client_id or "").strip()
                and settings.zoho_client_id
                and settings.zoho_client_secret
            ),
            "redirect_uri": settings.zoho_redirect_uri,
        },
    }


@router.post("/auth/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        user, tenant = await register_user(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            tenant_name=payload.tenant_name,
        )
    except TenancyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = create_access_token(user_id=user.id, email=user.email, tenant_id=tenant.id)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        tenant_id=tenant.id,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        user = await authenticate_user(db, payload.email, payload.password)
    except TenancyError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    tenants = await list_user_tenants(db, user.id)
    tenant_id = tenants[0][0].id if tenants else None
    token = create_access_token(user_id=user.id, email=user.email, tenant_id=tenant_id)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        tenant_id=tenant_id,
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    tenants = await list_user_tenants(db, user.id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "tenants": [_tenant_public(t, m) for t, m in tenants],
    }


@router.get("/tenants")
async def tenants(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    rows = await list_user_tenants(db, user.id)
    return {"tenants": [_tenant_public(t, m) for t, m in rows]}


@router.post("/tenants")
async def create_workspace(
    payload: CreateTenantRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant = await create_tenant(db, name=payload.name, owner=user)
    await db.refresh(tenant, attribute_names=["zoho_connection"])
    return _tenant_public(tenant, membership=None)


@router.post("/tenants/{tenant_id}/members")
async def invite_member(
    tenant_id: str,
    payload: AddMemberRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        membership = await add_member(
            db,
            tenant_id=tenant_id,
            email=payload.email,
            role=payload.role,
            actor_user_id=user.id,
        )
    except TenancyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"tenant_id": tenant_id, "user_id": membership.user_id, "role": membership.role}


@router.get("/tenants/current")
async def current_tenant(auth: AuthContext = Depends(require_tenant)) -> dict:
    return _tenant_public(auth.tenant, auth.membership)


@router.post("/tenants/current/zoho/settings")
async def update_zoho_settings(
    payload: ZohoSettingsRequest,
    auth: AuthContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Save per-tenant Zoho OAuth app + data center / org / optional refresh token.

    Each workspace should store its own Zoho API Console client id/secret.
    Platform ``ZOHO_CLIENT_ID`` / ``ZOHO_CLIENT_SECRET`` in env are a fallback only.
    """
    assert auth.tenant is not None
    if auth.membership and auth.membership.role not in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
    }:
        raise HTTPException(status_code=403, detail="Admin role required to update Zoho settings.")

    dc = payload.data_center.strip().lower()
    if dc not in ZOHO_DATA_CENTERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown data_center. Use one of: {', '.join(sorted(ZOHO_DATA_CENTERS))}",
        )
    accounts_url, api_base_url = ZOHO_DATA_CENTERS[dc]

    connection = auth.tenant.zoho_connection
    if connection is None:
        raise HTTPException(status_code=400, detail="Tenant Zoho connection row is missing.")

    connection.accounts_url = accounts_url
    connection.api_base_url = api_base_url
    if payload.organization_id.strip():
        connection.organization_id = payload.organization_id.strip()

    if payload.client_id.strip():
        connection.oauth_client_id = payload.client_id.strip()
    if payload.client_secret.strip():
        from clario.security.crypto import encrypt_secret

        connection.encrypted_oauth_client_secret = encrypt_secret(payload.client_secret.strip())

    refresh = payload.refresh_token.strip()
    if refresh:
        from clario.tenancy.service import connection_has_oauth_app

        if not connection_has_oauth_app(connection):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Save this workspace's Zoho Client ID and Client Secret first "
                    "(or configure platform ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET)."
                ),
            )
        oauth = build_tenant_oauth(connection)
        try:
            await oauth.refresh_access_token(refresh)
            connection.connected_by_user_id = auth.user.id
            connection.last_verified_at = datetime.now(timezone.utc)
            from clario.tenancy.service import settings_for_connection

            client = ZohoBooksClient(settings_for_connection(connection), oauth=oauth)
            try:
                orgs = await client.list_organizations()
            finally:
                await client.aclose()
            if connection.organization_id:
                match = next(
                    (o for o in orgs if o.organization_id == connection.organization_id),
                    None,
                )
                if match:
                    connection.organization_name = match.name
                    connection.currency_code = match.currency_code
            elif len(orgs) == 1:
                connection.organization_id = orgs[0].organization_id
                connection.organization_name = orgs[0].name
                connection.currency_code = orgs[0].currency_code
        except (ZohoAuthError, ZohoError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    await write_audit(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        action="zoho.settings.updated",
        resource_type="zoho_connection",
        resource_id=connection.id,
        metadata={
            "data_center": dc,
            "organization_id": connection.organization_id,
            "client_id_updated": bool(payload.client_id.strip()),
            "client_secret_updated": bool(payload.client_secret.strip()),
            "refresh_token_provided": bool(refresh),
        },
    )
    return _tenant_public(auth.tenant, auth.membership)


@router.get("/oauth/zoho/start")
async def oauth_start(
    request: Request,
    auth: AuthContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
    redirect_after: str = Query(default="/"),
):
    assert auth.tenant is not None
    connection = auth.tenant.zoho_connection
    if connection is None:
        raise HTTPException(status_code=400, detail="Tenant Zoho connection row is missing.")

    from clario.tenancy.service import connection_has_oauth_app

    if not connection_has_oauth_app(connection):
        raise HTTPException(
            status_code=400,
            detail=(
                "Add this workspace's Zoho Client ID and Client Secret under Zoho Books settings "
                "before connecting (each organization uses its own Zoho API Console app)."
            ),
        )

    oauth = build_tenant_oauth(connection)
    try:
        oauth.settings.require_zoho_oauth_app()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    oauth_state = await create_oauth_state(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        redirect_after=redirect_after,
    )
    url, _ = oauth.authorization_url(state=oauth_state.state)
    await write_audit(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        action="zoho.oauth.started",
        resource_type="tenant",
        resource_id=auth.tenant.id,
        ip_address=request.client.host if request.client else "",
    )
    return {"authorization_url": url, "state": oauth_state.state}


@router.get("/oauth/zoho/callback", response_model=None)
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Zoho authorization denied: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing authorization code or state.")
    try:
        oauth_state = await consume_oauth_state(db, state)
    except TenancyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tenant, _ = await require_membership(
        db, tenant_id=oauth_state.tenant_id, user_id=oauth_state.user_id
    )
    connection = tenant.zoho_connection
    if connection is None:
        raise HTTPException(status_code=400, detail="Zoho connection missing for tenant.")

    oauth = build_tenant_oauth(connection)
    try:
        await oauth.exchange_code(code)
    except ZohoAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from clario.tenancy.service import settings_for_connection

    client = ZohoBooksClient(settings_for_connection(connection), oauth=oauth)
    org_error = ""
    names = ""
    try:
        orgs = await client.list_organizations()
        names = ", ".join(f"{org.name} ({org.organization_id})" for org in orgs) or "none"
        if orgs and not connection.organization_id:
            chosen = next((o for o in orgs if o.is_default_org), orgs[0])
            connection.organization_id = chosen.organization_id
            connection.organization_name = chosen.name
            connection.currency_code = chosen.currency_code
        connection.is_connected = True
        connection.connected_by_user_id = oauth_state.user_id
        connection.last_verified_at = datetime.now(timezone.utc)
    except ZohoError as exc:
        org_error = str(exc)
        orgs = []
    finally:
        await client.aclose()

    await write_audit(
        db,
        tenant_id=tenant.id,
        user_id=oauth_state.user_id,
        action="zoho.oauth.connected",
        resource_type="zoho_connection",
        resource_id=connection.id,
        metadata={"organization_id": connection.organization_id},
        ip_address=request.client.host if request.client else "",
    )

    body = f"""
    <html><body style="font-family: system-ui; max-width: 40rem; margin: 3rem auto;">
      <h1>Zoho Books connected</h1>
      <p>Workspace: <strong>{tenant.name}</strong></p>
      <p>Tokens are encrypted and stored for this tenant only.</p>
      <p>Organizations: {names}</p>
      {"<p>Could not list organizations: " + org_error + "</p>" if org_error else ""}
      <p><a href="{oauth_state.redirect_after or "/"}">Back to Clario</a></p>
    </body></html>
    """
    return HTMLResponse(body)


@router.post("/tenants/current/zoho/organization")
async def select_organization(
    payload: SelectOrgRequest,
    auth: AuthContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assert auth.tenant is not None
    connection = auth.tenant.zoho_connection
    if connection is None or not connection.is_connected:
        raise HTTPException(status_code=400, detail="Connect Zoho Books first.")
    oauth = build_tenant_oauth(connection)
    from clario.tenancy.service import settings_for_connection

    client = ZohoBooksClient(settings_for_connection(connection), oauth=oauth)
    try:
        orgs = await client.list_organizations()
    finally:
        await client.aclose()
    match = next((o for o in orgs if o.organization_id == payload.organization_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Organization not found for this Zoho account.")
    connection.organization_id = match.organization_id
    connection.organization_name = match.name
    connection.currency_code = match.currency_code
    await write_audit(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        action="zoho.organization.selected",
        resource_type="zoho_connection",
        resource_id=connection.id,
        metadata={"organization_id": match.organization_id, "name": match.name},
    )
    return _tenant_public(auth.tenant, auth.membership)


@router.delete("/tenants/current/zoho")
async def disconnect_zoho(
    auth: AuthContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assert auth.tenant is not None
    if auth.membership and auth.membership.role not in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
    }:
        raise HTTPException(status_code=403, detail="Admin role required to disconnect Zoho.")
    connection = auth.tenant.zoho_connection
    if connection:
        store = build_tenant_oauth(connection).store
        store.clear()
        connection.organization_id = ""
        connection.organization_name = ""
        connection.is_connected = False
    await write_audit(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        action="zoho.disconnected",
        resource_type="tenant",
        resource_id=auth.tenant.id,
    )
    return {"status": "disconnected"}
