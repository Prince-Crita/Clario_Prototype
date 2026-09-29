"""Multi-tenant domain services."""

from clario.tenancy.service import (
    ForbiddenError,
    NotFoundError,
    TenancyError,
    add_member,
    authenticate_user,
    build_tenant_oauth,
    create_tenant,
    list_user_tenants,
    register_user,
    require_membership,
    settings_for_connection,
)

__all__ = [
    "ForbiddenError",
    "NotFoundError",
    "TenancyError",
    "add_member",
    "authenticate_user",
    "build_tenant_oauth",
    "create_tenant",
    "list_user_tenants",
    "register_user",
    "require_membership",
    "settings_for_connection",
]
