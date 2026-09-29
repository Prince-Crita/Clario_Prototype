"""Application factory.

`create_app()` wires settings, logging, the database, middleware, error rendering and routers.
Run with `clario serve` (uvicorn factory mode). Tests call `create_app(settings)` directly.
The app never creates or alters tables — schema changes go through Alembic (`clario db upgrade`).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from clario import __version__
from clario.ai.providers.factory import get_provider
from clario.ai.providers.status import ProviderStatus
from clario.api.errors import install_error_handlers
from clario.api.middleware import RequestContextMiddleware
from clario.api.registry import build_registry
from clario.api.router import API_PREFIX, build_api_router
from clario.api.security import CsrfOriginMiddleware
from clario.core.db import Database
from clario.core.logs import configure_logging
from clario.platform.identity.ratelimit import SlidingWindowLimiter
from clario.platform.integrations import repository as integration_repo
from clario.platform.sync.service import SyncRunner
from clario.settings import Settings, get_settings

logger = logging.getLogger("clario")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.effective_log_format)

    # The engine connects lazily, so creating it here is cheap and keeps the app usable without
    # running lifespan (OpenAPI export, tests). Lifespan only disposes the pool on shutdown.
    database = Database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

    registry = build_registry()  # raises RegistryError on inconsistent plug-ins: fail at boot
    sync = SyncRunner(database, settings, registry)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            async with database.sessions() as session:
                await integration_repo.upsert_catalog(session, registry.manifests)
                await session.commit()
        except Exception:
            logger.exception("Integration catalog sync failed; readiness will report the database")
        logger.info(
            "Clario API starting", extra={"env": settings.app_env.value, "version": __version__}
        )
        try:
            yield
        finally:
            await sync.shutdown()  # cancelled runs are recorded as failed
            await database.dispose()
            logger.info("Clario API stopped")

    docs_enabled = not settings.is_production
    app = FastAPI(
        title="Clario API",
        version=__version__,
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs_enabled else None,
        docs_url=f"{API_PREFIX}/docs" if docs_enabled else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.registry = registry
    app.state.sync = sync
    app.state.llm_provider = get_provider(settings)  # None when no AI key is configured
    app.state.provider_status = ProviderStatus()  # the provider's last reported usage limit
    # Assistant messages per user: 20 per 5 minutes (plan §26).
    app.state.chat_limiter = SlidingWindowLimiter(max_attempts=20, window_seconds=300)
    # Sign-in attempts per client IP: 20 per 5 minutes (per-account lockout is the main control).
    app.state.login_limiter = SlidingWindowLimiter(max_attempts=20, window_seconds=300)
    # Order: middleware added last runs first. Request context must wrap everything (request ids).
    app.add_middleware(CsrfOriginMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(build_api_router(registry))
    return app
