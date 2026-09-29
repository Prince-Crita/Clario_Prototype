"""Operational endpoints (plan §11.2 "Ops"). They expose no tenant data and need no auth.

* `GET /api/v1/health`        liveness — the process is up.
* `GET /api/v1/health/ready`  readiness — dependencies (database) are reachable.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from clario import __version__
from clario.core.errors import ServiceUnavailableError
from clario.platform.web import DatabaseDep

router = APIRouter(prefix="/health", tags=["ops"])


class Liveness(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__


class Readiness(BaseModel):
    status: Literal["ready"] = "ready"
    checks: dict[str, Literal["ok"]]


@router.get("", response_model=Liveness, summary="Liveness probe")
async def liveness() -> Liveness:
    return Liveness()


@router.get(
    "/ready",
    response_model=Readiness,
    summary="Readiness probe",
    responses={503: {"description": "A dependency is unavailable"}},
)
async def readiness(database: DatabaseDep) -> Readiness:
    if not await database.ping():
        raise ServiceUnavailableError(
            "The database is not reachable.", code="health.database_unavailable"
        )
    return Readiness(checks={"database": "ok"})
