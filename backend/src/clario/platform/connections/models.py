"""Connection tables in `core` (plan §14.2, §15.3, §17).

* `integration_connections` — one workspace's link to one external account (e.g. a Zoho Books
  organisation). `(id, workspace_id)` is unique so tenant data can use composite foreign keys.
* `connection_credentials` — the encrypted secret, in its own table so it is never loaded with
  connection listings. Only core encrypts and decrypts it.
* `oauth_states` — single-use consent attempts. Only the SHA-256 of the state is stored.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clario.core.db import Base, SoftDelete, Timestamps, UUIDPrimaryKey

SCHEMA = "core"


class ConnectionStatus(StrEnum):
    PENDING = "pending"  # consent started or granted; no account chosen yet
    CONNECTED = "connected"
    NEEDS_REAUTH = "needs_reauth"  # the provider stopped accepting the credentials
    ERROR = "error"
    DISCONNECTED = "disconnected"  # soft-deleted; kept for audit and lineage


class Connection(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'connected', 'needs_reauth', 'error', 'disconnected')",
            name="status",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_integration_connections_id_workspace_id"),
        Index(
            "uq_integration_connections_live",
            "workspace_id",
            "integration_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": SCHEMA},
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.workspaces.id", ondelete="CASCADE")
    )
    integration_key: Mapped[str] = mapped_column(ForeignKey("core.integrations.key"))
    status: Mapped[str] = mapped_column(String(16), default=ConnectionStatus.PENDING)
    external_account_id: Mapped[str | None] = mapped_column(String(128))
    external_account_name: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(16))
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    connected_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.users.id", ondelete="SET NULL")
    )
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CredentialKind(StrEnum):
    OAUTH2 = "oauth2"


class ConnectionCredential(Timestamps, Base):
    __tablename__ = "connection_credentials"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_connection_credentials_connection",
            ondelete="CASCADE",
        ),
        CheckConstraint("kind IN ('oauth2')", name="kind"),
        {"schema": SCHEMA},
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(String(16), default=CredentialKind.OAUTH2)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    key_id: Mapped[str] = mapped_column(String(16))  # fingerprint of the encrypting key
    granted_scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String(128)), default=list, server_default=text("'{}'")
    )


class OAuthState(UUIDPrimaryKey, Base):
    __tablename__ = "oauth_states"
    __table_args__ = (
        Index("ix_oauth_states_expires_at", "expires_at"),
        {"schema": SCHEMA},
    )

    state_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.workspaces.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id", ondelete="CASCADE"))
    integration_key: Mapped[str] = mapped_column(String(64))
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.integration_connections.id", ondelete="CASCADE")
    )
    region: Mapped[str | None] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
