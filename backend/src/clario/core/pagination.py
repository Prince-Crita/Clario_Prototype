"""Opaque cursor pagination (plan §11.1: `limit` + `cursor`, max 200).

A cursor is URL-safe base64 of a small JSON object chosen by the repository (typically the sort
key and id of the last row). Clients treat it as opaque; tampering yields a validation error.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from pydantic import BaseModel, Field

from clario.core.errors import ValidationFailedError

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = Field(
        default=None, description="Pass as `cursor` to get the next page"
    )


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if limit < 1:
        raise ValidationFailedError("limit must be at least 1", code="pagination.invalid_limit")
    return min(limit, MAX_LIMIT)


def encode_cursor(position: dict[str, Any]) -> str:
    raw = json.dumps(position, separators=(",", ":"), sort_keys=True, default=str).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise ValidationFailedError(
            "cursor is not valid", code="pagination.invalid_cursor"
        ) from None
    if not isinstance(value, dict):
        raise ValidationFailedError("cursor is not valid", code="pagination.invalid_cursor")
    return value
