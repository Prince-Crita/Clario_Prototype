"""Zoho Books integration errors."""

from __future__ import annotations


class ZohoError(Exception):
    """Base error for the Zoho Books integration."""


class ZohoAuthError(ZohoError):
    """OAuth or access-token failure."""


class ZohoConfigError(ZohoError):
    """Missing or invalid local configuration."""


class ZohoAPIError(ZohoError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: int | str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.path = path


class ZohoRateLimitError(ZohoAPIError):
    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ZohoValidationError(ZohoError):
    """A Zoho response could not be normalized."""
