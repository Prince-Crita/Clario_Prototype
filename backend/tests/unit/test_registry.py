from __future__ import annotations

import pytest

from clario.api.registry import build_registry
from clario.integrations.zoho_books.plugin import plugin as zoho_books
from clario.platform.integrations.contract import (
    Availability,
    DomainModule,
    IntegrationManifest,
    IntegrationPlugin,
)
from clario.platform.integrations.registry import Registry, RegistryError
from tests.support import FakeConnector as FakePlugin

FINANCE = DomainModule(key="finance", name="Finance", description="")


def manifest(
    key: str, availability: Availability = Availability.AVAILABLE, domain: str = "finance"
) -> IntegrationManifest:
    return IntegrationManifest(
        key=key, name=key.title(), vendor="V", domain=domain, summary="s", availability=availability
    )


def test_the_real_composition_root_is_valid() -> None:
    registry = build_registry()
    keys = [m.key for m in registry.manifests]
    assert keys == ["zoho-books", "veloce-inventory", "city-threads-inventory", "lead-management"]
    assert registry.plugin("zoho-books") is not None
    assert registry.plugin("veloce-inventory") is None  # catalog-only: no code
    assert registry.domain_name("finance") == "Finance"
    assert registry.domain_name("inventory") == "Inventory"  # not installed yet, still displayable


@pytest.mark.parametrize(
    ("plugins", "catalog", "fragment"),
    [
        ([manifest("a")], [manifest("a", Availability.COMING_SOON)], "duplicate"),
        ([], [manifest("a")], "no connector code"),
        ([manifest("a", Availability.COMING_SOON)], [], "has connector code"),
        ([manifest("a", domain="inventory")], [], "not installed"),
        ([manifest("settings")], [], "reserved"),
        ([manifest("Bad_Key")], [], "lowercase"),
    ],
)
def test_invalid_registries_fail_fast(
    plugins: list[IntegrationManifest], catalog: list[IntegrationManifest], fragment: str
) -> None:
    with pytest.raises(RegistryError, match=fragment):
        Registry(domains=[FINANCE], plugins=[FakePlugin(m) for m in plugins], catalog_only=catalog)


def test_manifests_are_sorted_by_order_then_name() -> None:
    registry = Registry(
        domains=[FINANCE],
        plugins=[FakePlugin(manifest("b"))],
        catalog_only=[
            manifest("a", Availability.COMING_SOON),
            manifest("c", Availability.COMING_SOON),
        ],
    )
    assert [m.key for m in registry.manifests] == ["a", "b", "c"]


def test_connectors_satisfy_the_plugin_contract() -> None:
    """Static check (mypy) plus a runtime check that every installed connector is complete."""
    installed: list[IntegrationPlugin] = [zoho_books]
    for plugin in installed:
        for name in ("consent_redirect", "exchange", "list_accounts", "account_profile", "revoke"):
            assert callable(getattr(plugin, name)), f"{plugin.manifest.key} lacks {name}"
    assert zoho_books.manifest.regions[0].code == "in"  # India is the default data center
    assert zoho_books.manifest.account_noun == "organisation"
