"""The registry of installed domains, connectors and catalog-only entries (plan §15.2).

Built once at startup from `clario.api.registry` (the composition root) and validated so that a
mis-declared plug-in fails fast at boot rather than at a customer's click.
"""

from __future__ import annotations

from collections.abc import Iterable

from clario.platform.integrations.contract import (
    KEY_PATTERN,
    RESERVED_KEYS,
    Availability,
    DomainModule,
    IntegrationManifest,
    IntegrationPlugin,
)


class RegistryError(Exception):
    """The installed plug-ins are inconsistent; the app must not start."""


class Registry:
    def __init__(
        self,
        *,
        domains: Iterable[DomainModule],
        plugins: Iterable[IntegrationPlugin],
        catalog_only: Iterable[IntegrationManifest] = (),
    ) -> None:
        self._domains = {d.key: d for d in domains}
        self._plugins = {p.manifest.key: p for p in plugins}
        manifests = [p.manifest for p in self._plugins.values()] + list(catalog_only)
        self._manifests = {m.key: m for m in manifests}
        self._validate(manifests)

    def _validate(self, manifests: list[IntegrationManifest]) -> None:
        problems = []
        for domain in self._domains.values():
            dataset_keys = [d.key for d in domain.datasets]
            for key in {k for k in dataset_keys if dataset_keys.count(k) > 1}:
                problems.append(f"domain {domain.key!r}: duplicate dataset {key!r}")
        keys = [m.key for m in manifests]
        for key in {k for k in keys if keys.count(k) > 1}:
            problems.append(f"duplicate integration key {key!r}")
        for m in manifests:
            if not KEY_PATTERN.match(m.key):
                problems.append(f"{m.key!r}: keys are lowercase words joined by single hyphens")
            if m.key in RESERVED_KEYS:
                problems.append(f"{m.key!r}: reserved (clashes with an app route)")
            has_code = m.key in self._plugins
            if m.availability is Availability.AVAILABLE:
                if not has_code:
                    problems.append(f"{m.key!r}: available but no connector code is installed")
                if m.domain not in self._domains:
                    problems.append(f"{m.key!r}: feeds domain {m.domain!r}, which is not installed")
            elif has_code:
                problems.append(
                    f"{m.key!r}: has connector code but is marked {m.availability.value}"
                )
        if problems:
            raise RegistryError("Invalid integration registry: " + "; ".join(sorted(problems)))

    # ---------------------------------------------------------------- lookups
    @property
    def manifests(self) -> list[IntegrationManifest]:
        return sorted(self._manifests.values(), key=lambda m: (m.sort_order, m.name))

    def manifest(self, key: str) -> IntegrationManifest | None:
        return self._manifests.get(key)

    def plugin(self, key: str) -> IntegrationPlugin | None:
        return self._plugins.get(key)

    @property
    def domains(self) -> list[DomainModule]:
        return list(self._domains.values())

    def domain(self, key: str) -> DomainModule | None:
        return self._domains.get(key)

    def domain_name(self, key: str) -> str:
        """Display name even for domains not installed yet (catalog-only cards)."""
        domain = self._domains.get(key)
        return domain.name if domain else key.replace("-", " ").title()
