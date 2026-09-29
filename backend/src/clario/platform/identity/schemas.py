"""Identity API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from clario.platform.workspaces.schemas import WorkspaceSummary


class LoginRequest(BaseModel):
    # Deliberately not format-validated: any input gets the same generic 401 as a wrong password.
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_platform_admin: bool


class SessionOut(BaseModel):
    """What the SPA needs after sign-in or on reload."""

    user: UserOut
    workspaces: list[WorkspaceSummary]
    csrf_token: str = Field(description="Send as the X-CSRF-Token header on every non-GET request")
    expires_at: datetime | None = None
