"""Imports every ORM module so `Base.metadata` is complete for Alembic autogenerate.

Add each module's `models` here when it gains tables (e.g. `clario.platform.identity.models`).
"""

from __future__ import annotations

from clario.core.db import Base
from clario.domains.finance import models as finance_models
from clario.platform.audit import models as audit_models
from clario.platform.connections import models as connection_models
from clario.platform.conversations import models as conversation_models
from clario.platform.identity import models as identity_models
from clario.platform.integrations import models as integration_models
from clario.platform.sync import models as sync_models
from clario.platform.workspaces import models as workspace_models

metadata = Base.metadata
__all__ = [
    "audit_models",
    "connection_models",
    "conversation_models",
    "finance_models",
    "identity_models",
    "integration_models",
    "metadata",
    "sync_models",
    "workspace_models",
]
