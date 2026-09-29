"""Assembles every router under `/api/v1` (plan §11).

Feature routers are added here as their phases land (identity and workspaces in Phase 2, the
integration registry in Phase 4, …). This file and `orm_registry.py` are the only places that list
modules; adding a connector should not require touching anything else in core.
"""

from __future__ import annotations

from fastapi import APIRouter

from clario.ai.chat import api as assistant_api
from clario.api import health
from clario.platform.connections import api as connections_api
from clario.platform.identity import api as identity_api
from clario.platform.integrations import api as integrations_api
from clario.platform.integrations.registry import Registry
from clario.platform.sync import api as sync_api
from clario.platform.workspaces import api as workspaces_api

API_PREFIX = "/api/v1"


def build_api_router(registry: Registry) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    router.include_router(health.router)
    router.include_router(identity_api.router)
    router.include_router(workspaces_api.router)
    router.include_router(integrations_api.router)
    router.include_router(connections_api.router)
    router.include_router(sync_api.router)
    router.include_router(assistant_api.router)
    for domain in registry.domains:  # each domain's dashboards (e.g. /.../finance/overview)
        if domain.router is not None:
            router.include_router(domain.router)
    return router
