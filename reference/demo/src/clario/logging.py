"""Structured logging that never prints OAuth secrets."""

from __future__ import annotations

import logging
import re
from typing import Any

_SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "client_id",
    "code",
    "authorization",
    "token",
    "google_api_key",
    "api_key",
}

_TOKEN_RE = re.compile(r"(Zoho-oauthtoken\s+)\S+", re.IGNORECASE)


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def redact(value: Any) -> str:
    text = str(value)
    text = _TOKEN_RE.sub(r"\1[REDACTED]", text)
    return text


def redact_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in _SECRET_KEYS:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = value
    return redacted


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("clario")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        handler.addFilter(SecretFilter())
        logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
    return logger


def get_logger(name: str = "clario") -> logging.Logger:
    return logging.getLogger(name)
