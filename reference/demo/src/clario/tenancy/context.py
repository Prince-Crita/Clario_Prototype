"""Request-scoped tenant binding for ADK tools."""

from __future__ import annotations

from contextvars import ContextVar

from clario.db.models import Tenant, ZohoConnection
from clario.services.analysis import AnalysisService
from clario.tenancy.service import build_tenant_oauth, settings_for_connection
from clario.tools import zoho_tools
from clario.zoho.client import ZohoBooksClient, set_client_factory

_current_tenant: ContextVar[Tenant | None] = ContextVar("clario_tenant", default=None)


def get_current_tenant() -> Tenant | None:
    return _current_tenant.get()


def bind_tenant_client(tenant: Tenant) -> AnalysisService:
    connection = tenant.zoho_connection
    if connection is None or not connection.is_connected:
        raise RuntimeError("Zoho Books is not connected for this workspace.")

    settings = settings_for_connection(connection)
    oauth = build_tenant_oauth(connection)

    def factory() -> ZohoBooksClient:
        return ZohoBooksClient(settings=settings, oauth=oauth)

    set_client_factory(factory)
    service = AnalysisService(client=factory())
    zoho_tools.set_analysis_service(service)
    _current_tenant.set(tenant)
    return service


def clear_tenant_client() -> None:
    set_client_factory(None)
    zoho_tools.set_analysis_service(None)
    _current_tenant.set(None)
