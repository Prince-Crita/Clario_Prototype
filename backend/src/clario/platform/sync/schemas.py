"""Freshness API contracts (plan §11.2, §31)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SyncRunOut(BaseModel):
    id: uuid.UUID
    trigger: Literal["initial", "manual", "stale", "scheduled"]
    status: Literal["running", "succeeded", "partial", "failed"]
    started_at: datetime
    finished_at: datetime | None
    api_calls: int
    error_code: str | None


class DatasetStatusOut(BaseModel):
    key: str
    label: str
    status: Literal["ok", "failed", "never"]
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    row_count: int | None
    window_start: date | None
    window_end: date | None
    error_code: str | None


class SyncStatus(BaseModel):
    state: Literal["idle", "running"]
    as_of: datetime | None = Field(
        description="Oldest successful refresh among the datasets; null until all have data"
    )
    run: SyncRunOut | None = Field(description="The run in progress, else the latest one")
    datasets: list[DatasetStatusOut]


class SyncRequest(BaseModel):
    mode: Literal["manual", "if_stale"] = Field(
        default="manual",
        description="manual: 'Refresh now' (cooldown applies); if_stale: only when data is stale",
    )
