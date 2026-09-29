"""Structured logging with secret redaction (plan §29).

* `request_id` is carried in a ContextVar and attached to every record.
* `RedactingFilter` scrubs credentials from messages, args and structured extras before any
  handler sees them: OAuth/Bearer tokens, Groq keys, Fernet tokens, and values of sensitive keys.
* `json` format in production (one object per line), readable `console` format elsewhere.
"""

from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Literal

request_id_var: ContextVar[str | None] = ContextVar("clario_request_id", default=None)

REDACTED = "[REDACTED]"
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "id_token",
        "token",
        "code",
        "client_secret",
        "secret",
        "password",
        "password_hash",
        "authorization",
        "cookie",
        "set-cookie",
        "api_key",
        "groq_api_key",
        "session_secret",
        "encryption_keys",
        "ciphertext",
    }
)
_PATTERNS = [
    re.compile(r"(Zoho-oauthtoken\s+)\S+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r"()gsk_[A-Za-z0-9]{8,}"),  # Groq API keys
    re.compile(r"()gAAAAA[A-Za-z0-9_\-=]{20,}"),  # Fernet tokens
    re.compile(
        r"((?:access_token|refresh_token|client_secret|code|password)=)[^&\s\"']+", re.IGNORECASE
    ),
]
# Attributes present on every LogRecord; anything else was passed via `extra=`.
# `color_message` is uvicorn's ANSI-coloured duplicate of the message; never emit it.
_STANDARD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "color_message",
}


def redact_text(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", text)
    return text


def redact(value: Any, key: str | None = None) -> Any:
    """Recursively redact a structure. Values under sensitive keys are replaced entirely."""
    if key is not None and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = None
        for attr in set(vars(record)) - _STANDARD_ATTRS:
            setattr(record, attr, redact(getattr(record, attr), attr))
        record.request_id = request_id_var.get()
        return True


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS and k != "request_id"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        payload.update(_extras(record))
        if record.exc_info:
            payload["exc"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        time = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")  # noqa: DTZ006 - local display
        rid = getattr(record, "request_id", None)
        extras = _extras(record)
        line = f"{time} {record.levelname:<7} {record.name}"
        line += f" [{rid[-8:]}]" if rid else ""  # UUIDv7 tail is random; the head is a timestamp
        line += f" {record.getMessage()}"
        if extras:
            line += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        if record.exc_info:
            line += "\n" + redact_text(self.formatException(record.exc_info))
        return line


def configure_logging(level: str = "INFO", fmt: Literal["json", "console"] = "console") -> None:
    """Configure the root logger once; uvicorn's loggers propagate into it."""
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter() if fmt == "json" else ConsoleFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    # Access logging is done by our request middleware (with request ids); silence uvicorn's.
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False
