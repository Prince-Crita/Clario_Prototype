"""The plug-in registry as a request dependency (built once at app start, see `clario.main`)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from clario.platform.integrations.registry import Registry


def get_registry(request: Request) -> Registry:
    registry: Registry = request.app.state.registry
    return registry


RegistryDep = Annotated[Registry, Depends(get_registry)]
