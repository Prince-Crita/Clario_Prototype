"""Request-scoped middleware (pure ASGI, no BaseHTTPMiddleware overhead).

`RequestContextMiddleware` assigns a request id (accepting a well-formed inbound `X-Request-ID`
from the reverse proxy), exposes it on the response, and writes one structured access-log line.
Query strings are never logged: OAuth callbacks carry authorization codes in them.
"""

from __future__ import annotations

import logging
import re
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from clario.core.ids import uuid7
from clario.core.logs import request_id_var

access_logger = logging.getLogger("clario.access")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
HEADER = b"x-request-id"


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = dict(scope.get("headers") or []).get(HEADER, b"").decode("latin-1")
        request_id = inbound if _VALID_REQUEST_ID.match(inbound) else str(uuid7())
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [h for h in message.get("headers", []) if h[0].lower() != HEADER]
                headers.append((HEADER, request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            access_logger.info(
                "%s %s %s",
                scope.get("method"),
                scope.get("path"),
                status_code,
                extra={"duration_ms": round((time.perf_counter() - started) * 1000, 1)},
            )
            request_id_var.reset(token)
