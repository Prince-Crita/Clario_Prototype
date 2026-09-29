"""Composition root for plug-ins — the ONLY file that lists domains and connectors (plan §15.2).

Adding a connector for an existing domain: add its plugin to INTEGRATIONS (and remove its
catalog-only entry, if any). Nothing else in Clario Core changes.
"""

from __future__ import annotations

from clario.domains.finance.module import module as finance
from clario.integrations.catalog import COMING_SOON
from clario.integrations.zoho_books.plugin import plugin as zoho_books
from clario.platform.integrations.registry import Registry

DOMAINS = [finance]
INTEGRATIONS = [zoho_books]
CATALOG_ONLY = list(COMING_SOON)


def build_registry() -> Registry:
    return Registry(domains=DOMAINS, plugins=INTEGRATIONS, catalog_only=CATALOG_ONLY)
