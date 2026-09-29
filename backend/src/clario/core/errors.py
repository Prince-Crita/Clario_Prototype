"""Single error hierarchy for Clario (plan §10.2, §11.1).

Every expected failure is a `ClarioError` with a stable machine `code`
(e.g. `connection.needs_reauth`) and an HTTP status. The API layer renders them as RFC 9457
`application/problem+json`. `detail` is shown to users, so it must never contain secrets,
tokens or internal paths.
"""

from __future__ import annotations

from typing import Any, ClassVar


class ClarioError(Exception):
    status_code: ClassVar[int] = 500
    default_code: ClassVar[str] = "internal_error"
    title: ClassVar[str] = "Something went wrong"

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail or self.title
        self.code = code or self.default_code
        self.extra = extra or {}
        super().__init__(self.detail)


class BadRequestError(ClarioError):
    status_code = 400
    default_code = "bad_request"
    title = "The request is not valid"


class AuthenticationError(ClarioError):
    status_code = 401
    default_code = "auth.required"
    title = "Sign in to continue"


class PermissionDeniedError(ClarioError):
    status_code = 403
    default_code = "auth.forbidden"
    title = "You do not have permission to do this"


class NotFoundError(ClarioError):
    """Also used for resources in other workspaces, so their ids cannot be probed (plan §13.3)."""

    status_code = 404
    default_code = "not_found"
    title = "Not found"


class ConflictError(ClarioError):
    status_code = 409
    default_code = "conflict"
    title = "This conflicts with the current state"


class ValidationFailedError(ClarioError):
    status_code = 422
    default_code = "validation_failed"
    title = "Some fields are not valid"


class RateLimitedError(ClarioError):
    status_code = 429
    default_code = "rate_limited"
    title = "Too many requests — try again shortly"


class UpstreamError(ClarioError):
    """A connected system (Zoho, the LLM provider, …) failed."""

    status_code = 502
    default_code = "upstream.error"
    title = "A connected service returned an error"


class ServiceUnavailableError(ClarioError):
    status_code = 503
    default_code = "service_unavailable"
    title = "The service is temporarily unavailable"
