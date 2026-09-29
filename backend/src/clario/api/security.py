"""CSRF and Origin protection for state-changing API requests (plan §12).

For POST/PUT/PATCH/DELETE under /api:
  1. Origin check — when the browser sends `Origin`, it must be the app origin (APP_BASE_URL) or
     the API's own origin. Blocks cross-site form posts, including login CSRF.
  2. CSRF token — when a session cookie is present, `X-CSRF-Token` must equal the HMAC bound to that
     session. Requests without a session cookie carry no ambient authority, so they need no token.
     Sign-in is exempt from (2): a browser may still hold a stale (expired/revoked) cookie and could
     otherwise never sign in again; sign-in is protected by the Origin check instead.
Combined with SameSite=Lax httpOnly cookies this is defence in depth, not a single control.
"""

from __future__ import annotations

from http.cookies import SimpleCookie
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

from clario.api.errors import problem
from clario.platform.identity.tokens import CSRF_HEADER, cookie_name, csrf_valid
from clario.settings import Settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_TOKEN_EXEMPT_PATHS = frozenset({"/api/v1/auth/login"})


def _origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


class CsrfOriginMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.app_origin = _origin_of(settings.app_base_url)
        self.cookie = cookie_name(settings.session_cookie_secure)
        self.secret = settings.session_secret.get_secret_value()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] in SAFE_METHODS
            or not str(scope.get("path", "")).startswith("/api/")
        ):
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
        }
        origin = headers.get("origin")
        if origin is not None:
            own = f"{scope.get('scheme', 'http')}://{headers.get('host', '')}".lower()
            if origin.lower() not in {self.app_origin, own}:
                await problem(403, "auth.origin_rejected", "Request origin is not allowed")(
                    scope, receive, send
                )
                return

        jar: SimpleCookie = SimpleCookie()
        try:
            jar.load(headers.get("cookie", ""))
        except Exception:
            jar = SimpleCookie()
        session_cookie = jar.get(self.cookie)
        if (
            session_cookie is not None
            and scope["path"] not in CSRF_TOKEN_EXEMPT_PATHS
            and not csrf_valid(session_cookie.value, headers.get(CSRF_HEADER.lower()), self.secret)
        ):
            await problem(
                403,
                "auth.csrf_failed",
                "Security token missing or invalid",
                "Reload the page and try again.",
            )(scope, receive, send)
            return

        await self.app(scope, receive, send)
