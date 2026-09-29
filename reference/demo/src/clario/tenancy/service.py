"""Tenant-aware business services."""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from clario.config import Settings, get_settings
from clario.db.models import (
    AuditEvent,
    Conversation,
    Membership,
    MembershipRole,
    Message,
    OAuthState,
    Tenant,
    TenantStatus,
    User,
    ZohoConnection,
)
from clario.security.crypto import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_password,
)
from clario.zoho.oauth import TokenSet, ZohoOAuth


class TenancyError(Exception):
    pass


class NotFoundError(TenancyError):
    pass


class ForbiddenError(TenancyError):
    pass


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or secrets.token_hex(4)


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str = "",
    tenant_name: str | None = None,
) -> tuple[User, Tenant]:
    email_norm = email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == email_norm))
    if existing:
        raise TenancyError("An account with this email already exists.")
    if len(password) < 8:
        raise TenancyError("Password must be at least 8 characters.")

    user = User(
        email=email_norm,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
    )
    db.add(user)
    await db.flush()

    name = (tenant_name or f"{full_name or email_norm.split('@')[0]}'s workspace").strip()
    tenant = await create_tenant(db, name=name, owner=user)
    await write_audit(
        db,
        tenant_id=tenant.id,
        user_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=user.id,
    )
    return user, tenant


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise TenancyError("Invalid email or password.")
    return user


async def create_tenant(db: AsyncSession, *, name: str, owner: User) -> Tenant:
    base = slugify(name)
    slug = base
    n = 1
    while await db.scalar(select(Tenant.id).where(Tenant.slug == slug)):
        n += 1
        slug = f"{base}-{n}"

    tenant = Tenant(name=name.strip(), slug=slug, status=TenantStatus.ACTIVE)
    db.add(tenant)
    await db.flush()
    membership = Membership(
        tenant_id=tenant.id,
        user_id=owner.id,
        role=MembershipRole.OWNER,
    )
    db.add(membership)
    settings = get_settings()
    connection = ZohoConnection(
        tenant_id=tenant.id,
        accounts_url=settings.zoho_accounts_url,
        api_base_url=settings.zoho_api_base_url,
        scopes=",".join(settings.scopes),
        is_connected=False,
    )
    db.add(connection)
    await write_audit(
        db,
        tenant_id=tenant.id,
        user_id=owner.id,
        action="tenant.created",
        resource_type="tenant",
        resource_id=tenant.id,
        metadata={"name": tenant.name, "slug": tenant.slug},
    )
    return tenant


async def list_user_tenants(db: AsyncSession, user_id: str) -> list[tuple[Tenant, Membership]]:
    rows = await db.execute(
        select(Tenant, Membership)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
            Tenant.status == TenantStatus.ACTIVE,
        )
        .options(selectinload(Tenant.zoho_connection))
        .order_by(Tenant.name)
    )
    return list(rows.all())


async def get_membership(
    db: AsyncSession, *, tenant_id: str, user_id: str
) -> Membership | None:
    return await db.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
        )
    )


async def require_membership(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    roles: set[str] | None = None,
) -> tuple[Tenant, Membership]:
    tenant = await db.scalar(
        select(Tenant)
        .where(Tenant.id == tenant_id, Tenant.status == TenantStatus.ACTIVE)
        .options(selectinload(Tenant.zoho_connection))
    )
    if tenant is None:
        raise NotFoundError("Tenant not found.")
    membership = await get_membership(db, tenant_id=tenant_id, user_id=user_id)
    if membership is None:
        raise ForbiddenError("You are not a member of this workspace.")
    if roles and membership.role not in roles:
        raise ForbiddenError("Insufficient role for this action.")
    return tenant, membership


async def add_member(
    db: AsyncSession,
    *,
    tenant_id: str,
    email: str,
    role: str = MembershipRole.MEMBER,
    actor_user_id: str,
) -> Membership:
    await require_membership(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        roles={MembershipRole.OWNER, MembershipRole.ADMIN},
    )
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise NotFoundError("User must register before being added to a workspace.")
    existing = await get_membership(db, tenant_id=tenant_id, user_id=user.id)
    if existing:
        existing.role = role
        existing.is_active = True
        return existing
    membership = Membership(tenant_id=tenant_id, user_id=user.id, role=role)
    db.add(membership)
    await write_audit(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        action="membership.added",
        resource_type="user",
        resource_id=user.id,
        metadata={"role": role, "email": user.email},
    )
    return membership


async def create_oauth_state(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    redirect_after: str = "/",
) -> OAuthState:
    state = OAuthState(
        state=secrets.token_urlsafe(24),
        tenant_id=tenant_id,
        user_id=user_id,
        redirect_after=redirect_after,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(state)
    await db.flush()
    return state


async def consume_oauth_state(db: AsyncSession, state_value: str) -> OAuthState:
    row = await db.scalar(select(OAuthState).where(OAuthState.state == state_value))
    if row is None:
        raise TenancyError("Invalid or expired OAuth state.")
    if row.expires_at.tzinfo is None:
        expires_at = row.expires_at.replace(tzinfo=timezone.utc)
    else:
        expires_at = row.expires_at
    if expires_at < datetime.now(timezone.utc):
        await db.delete(row)
        raise TenancyError("OAuth state expired. Start Zoho authorization again.")
    await db.delete(row)
    await db.flush()
    return row


class DatabaseTokenStore:
    """In-memory token store that mirrors encrypted tokens into ZohoConnection."""

    def __init__(self, connection: ZohoConnection) -> None:
        self.connection = connection
        self._tokens = self._load_from_connection()

    def _load_from_connection(self) -> TokenSet | None:
        refresh = decrypt_secret(self.connection.encrypted_refresh_token)
        access = decrypt_secret(self.connection.encrypted_access_token)
        if not refresh and not access:
            return None
        expires = 0.0
        if self.connection.access_token_expires_at:
            expires = self.connection.access_token_expires_at.timestamp()
        return TokenSet(
            access_token=access,
            refresh_token=refresh or None,
            expires_at=expires,
            api_domain=self.connection.api_domain or None,
        )

    def load(self) -> TokenSet | None:
        return self._tokens

    def save(self, tokens: TokenSet) -> None:
        self._tokens = tokens
        self.connection.encrypted_access_token = encrypt_secret(tokens.access_token)
        if tokens.refresh_token:
            self.connection.encrypted_refresh_token = encrypt_secret(tokens.refresh_token)
        self.connection.access_token_expires_at = datetime.fromtimestamp(
            tokens.expires_at, tz=timezone.utc
        )
        self.connection.api_domain = tokens.api_domain or ""
        self.connection.is_connected = bool(tokens.refresh_token)
        self.connection.updated_at = datetime.now(timezone.utc)

    def clear(self) -> None:
        self._tokens = None
        self.connection.encrypted_access_token = ""
        self.connection.encrypted_refresh_token = ""
        self.connection.access_token_expires_at = None
        self.connection.is_connected = False


def settings_for_connection(connection: ZohoConnection) -> Settings:
    """Build Settings for a tenant Zoho connection.

    Prefer workspace OAuth client id/secret when set; otherwise fall back to
    platform ``ZOHO_CLIENT_ID`` / ``ZOHO_CLIENT_SECRET`` from env.
    Redirect URI always comes from the platform (Clario's callback URL).
    """
    base = get_settings()
    tenant_client_id = (connection.oauth_client_id or "").strip()
    tenant_secret = decrypt_secret(connection.encrypted_oauth_client_secret)
    return base.model_copy(
        update={
            "zoho_accounts_url": connection.accounts_url.rstrip("/"),
            "zoho_api_base_url": connection.api_base_url.rstrip("/"),
            "zoho_organization_id": connection.organization_id,
            "zoho_refresh_token": "",
            "zoho_scopes": connection.scopes or base.zoho_scopes,
            "zoho_client_id": tenant_client_id or base.zoho_client_id,
            "zoho_client_secret": tenant_secret or base.zoho_client_secret,
        }
    )


def build_tenant_oauth(connection: ZohoConnection) -> ZohoOAuth:
    return ZohoOAuth(settings_for_connection(connection), DatabaseTokenStore(connection))


def connection_has_oauth_app(connection: ZohoConnection) -> bool:
    settings = settings_for_connection(connection)
    return bool(settings.zoho_client_id and settings.zoho_client_secret)


async def ensure_conversation(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    conversation_id: str | None = None,
    adk_session_id: str | None = None,
) -> Conversation:
    if conversation_id:
        convo = await db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id,
                Conversation.user_id == user_id,
            )
        )
        if convo:
            return convo
    if adk_session_id:
        convo = await db.scalar(
            select(Conversation).where(
                Conversation.adk_session_id == adk_session_id,
                Conversation.tenant_id == tenant_id,
            )
        )
        if convo:
            return convo

    import uuid

    sid = adk_session_id or str(uuid.uuid4())
    convo = Conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        adk_session_id=sid,
        title="",
    )
    db.add(convo)
    await db.flush()
    return convo


async def add_message(
    db: AsyncSession,
    *,
    conversation: Conversation,
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        tenant_id=conversation.tenant_id,
        role=role,
        content=content,
        tool_calls_json=json.dumps(tool_calls or []),
    )
    db.add(message)
    if role == "user" and not conversation.title:
        conversation.title = content.strip()[:80]
    conversation.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return message


async def list_conversations(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    limit: int = 50,
) -> list[Conversation]:
    rows = await db.scalars(
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
            Conversation.is_active.is_(True),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    return list(rows.all())


async def get_conversation(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    conversation_id: str,
) -> Conversation | None:
    return await db.scalar(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
            Conversation.is_active.is_(True),
        )
        .options(selectinload(Conversation.messages))
    )


async def archive_conversation(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    conversation_id: str,
) -> Conversation | None:
    convo = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
            Conversation.is_active.is_(True),
        )
    )
    if convo is None:
        return None
    convo.is_active = False
    await db.flush()
    return convo


async def write_audit(
    db: AsyncSession,
    *,
    action: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    resource_type: str = "",
    resource_id: str = "",
    metadata: dict[str, Any] | None = None,
    ip_address: str = "",
) -> AuditEvent:
    event = AuditEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=json.dumps(metadata or {}),
        ip_address=ip_address,
    )
    db.add(event)
    return event
