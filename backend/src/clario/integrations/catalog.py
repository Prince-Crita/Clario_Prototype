"""Catalog-only integrations: cards without code (plan §15.2).

Visible only in workspaces where Crita enables them (`clario admin set-integration-visibility`).
Never connectable.
"""

from __future__ import annotations

from clario.platform.integrations.contract import Availability, IntegrationManifest

COMING_SOON = (
    IntegrationManifest(
        key="veloce-inventory",
        name="Veloce Inventory",
        vendor="Crita",
        domain="inventory",
        summary="Stock levels, movements and valuation from Veloce.",
        availability=Availability.COMING_SOON,
        sort_order=20,
    ),
    IntegrationManifest(
        key="city-threads-inventory",
        name="City Threads Inventory",
        vendor="Crita",
        domain="inventory",
        summary="Stock, orders and fulfilment from the City Threads inventory system.",
        availability=Availability.COMING_SOON,
        sort_order=30,
    ),
    IntegrationManifest(
        key="lead-management",
        name="Lead Management",
        vendor="Crita",
        domain="leads",
        summary="Leads, pipeline stages and conversion from Crita Lead Management.",
        availability=Availability.COMING_SOON,
        sort_order=40,
    ),
)
