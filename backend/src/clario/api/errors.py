"""Render every error as RFC 9457 `application/problem+json` (plan §11.1).

Shape: {type, title, status, detail, code, request_id, [errors]}. Unexpected exceptions are logged
with a traceback and returned as a generic 500 — internal messages never reach the client.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from clario.core.errors import ClarioError
from clario.core.logs import request_id_var

logger = logging.getLogger("clario.api.errors")
PROBLEM_JSON = "application/problem+json"

_HTTP_CODES = {
    400: "bad_request",
    401: "auth.required",
    403: "auth.forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
}


def problem(
    status: int, code: str, title: str, detail: str | None = None, **extra: Any
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail or title,
        "code": code,
        "request_id": request_id_var.get(),
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


async def _clario_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ClarioError)
    if exc.status_code >= 500:
        logger.error("request failed", extra={"error_code": exc.code, "detail": exc.detail})
    response = problem(exc.status_code, exc.code, exc.title, exc.detail, **exc.extra)
    if isinstance(exc.extra.get("resets_in_seconds"), int):  # e.g. the AI usage limit
        response.headers["Retry-After"] = str(exc.extra["resets_in_seconds"])
    return response


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {
            "field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"),
            "message": err.get("msg", ""),
        }
        for err in exc.errors()
    ]
    return problem(422, "validation_failed", "Some fields are not valid", errors=errors)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    detail = exc.detail if isinstance(exc.detail, str) else None
    return problem(exc.status_code, code, detail or "Request failed", detail)


async def _unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=exc)
    return problem(500, "internal_error", "Something went wrong", "An unexpected error occurred.")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ClarioError, _clario_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unhandled_error)
