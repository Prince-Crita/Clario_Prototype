"""Tools, results and the toolset (plan §19): the only way an assistant reaches data.

Dispatch enforces, in code (§19.2):
  1. the tool must be in THIS toolset (a domain's) — anything else is `rejected`;
  2. arguments are validated by the tool's Pydantic model with extra fields forbidden, and no
     argument model may declare an identity field (workspace, connection, user, organisation);
  3. the context's permissions must include the tool's permission;
  4. the handler receives the server-built AgentContext;
  5. a timeout, and every failure mapped to a safe result (internal messages never reach the model).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from clario.ai.context import AgentContext
from clario.ai.providers.base import ToolSpec
from clario.core.errors import ClarioError
from clario.platform.access.permissions import Permission

logger = logging.getLogger(__name__)

IDENTITY_FIELDS = frozenset(
    {"workspace", "workspace_id", "connection", "connection_id", "user", "user_id", "tenant",
     "tenant_id", "organization_id", "organisation_id", "org_id", "scope"}
)  # fmt: skip
MAX_RESULT_CHARS = 6000  # what the model sees of one result (it is stored in full)

Status = Literal["ok", "no_data", "error"]


class ToolArgs(BaseModel):
    """Base for tool arguments: unknown fields are an error, never silently dropped."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The contract of every tool result (plan §19.3). `display` holds pre-formatted figures the
    model copies verbatim; `sources` and `as_of` feed the "Based on …" line."""

    status: Status
    data: Mapping[str, Any] = field(default_factory=dict)
    display: Mapping[str, str] = field(default_factory=dict)
    basis: str | None = None
    period: Mapping[str, str] | None = None
    as_of: str | None = None
    currency: str | None = None
    sources: tuple[str, ...] = ()
    code: str | None = None  # for no_data / error
    message: str | None = None  # safe explanation for the model

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status}
        for key in ("code", "message", "basis", "period", "as_of", "currency"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        if self.data:
            out["data"] = self.data
        if self.display:
            out["display"] = self.display
        if self.sources:
            out["sources"] = list(self.sources)
        return out

    def for_model(self) -> str:
        text = json.dumps(self.as_dict(), ensure_ascii=False, separators=(",", ":"), default=str)
        if len(text) <= MAX_RESULT_CHARS:
            return text
        return text[: MAX_RESULT_CHARS - 40] + '…","truncated":true}'


def no_data(code: str, message: str, **extra: Any) -> ToolResult:
    return ToolResult(status="no_data", code=code, message=message, **extra)


def error(code: str, message: str) -> ToolResult:
    return ToolResult(status="error", code=code, message=message)


Handler = Callable[[AgentContext, Any], Awaitable[ToolResult]]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str  # written for the model
    args_model: type[ToolArgs]
    permission: Permission
    handler: Handler
    label: str = ""  # human name for the sources line, e.g. "Receivables"

    def spec(self) -> ToolSpec:
        return ToolSpec(
            self.name, self.description, _clean_schema(self.args_model.model_json_schema())
        )


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Drop Pydantic titles (noise for the model) and close the object."""

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    cleaned: dict[str, Any] = walk(schema)
    cleaned["additionalProperties"] = False
    cleaned.setdefault("properties", {})
    return cleaned


DispatchStatus = Literal["ok", "no_data", "error", "rejected"]


@dataclass(frozen=True, slots=True)
class Dispatched:
    name: str
    arguments: dict[str, Any] | None
    result: ToolResult
    status: DispatchStatus
    duration_ms: int


class ToolsetError(Exception):
    """A toolset is mis-declared (e.g. an argument could carry a tenant identifier)."""


class Toolset:
    def __init__(self, tools: Sequence[Tool], *, timeout_seconds: float = 15.0) -> None:
        self._tools = {t.name: t for t in tools}
        self._timeout = timeout_seconds
        for tool in tools:
            if tool.args_model.model_config.get("extra") != "forbid":
                raise ToolsetError(f"{tool.name}: arguments must forbid extra fields")
            leaked = IDENTITY_FIELDS & set(tool.args_model.model_fields)
            if leaked:
                raise ToolsetError(
                    f"{tool.name}: identity fields are not allowed ({sorted(leaked)})"
                )

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    @property
    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self._tools.values()]

    def label(self, name: str) -> str:
        tool = self._tools.get(name)
        return tool.label or name if tool else name

    async def dispatch(self, ctx: AgentContext, name: str, raw_arguments: str) -> Dispatched:
        started = time.perf_counter()

        def done(
            status: DispatchStatus, result: ToolResult, args: dict[str, Any] | None
        ) -> Dispatched:
            return Dispatched(
                name, args, result, status, int((time.perf_counter() - started) * 1000)
            )

        tool = self._tools.get(name)
        if tool is None:
            return done(
                "rejected",
                error(
                    "tool.unavailable",
                    f"There is no tool named {name!r}. Use one of: {', '.join(self.names)}.",
                ),
                None,
            )
        try:
            parsed = json.loads(raw_arguments or "{}")
            if not isinstance(parsed, dict):
                raise ValueError
        except ValueError:
            return done(
                "rejected",
                error("tool.invalid_arguments", "Arguments must be a JSON object."),
                None,
            )
        try:
            args = tool.args_model.model_validate(parsed)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}"
                for e in exc.errors()
            )
            return done("rejected", error("tool.invalid_arguments", problems[:500]), parsed)
        if not ctx.scope.can(tool.permission):
            return done(
                "rejected",
                error("tool.forbidden", "You do not have permission to see this data."),
                parsed,
            )
        try:
            result = await asyncio.wait_for(tool.handler(ctx, args), timeout=self._timeout)
        except TimeoutError:
            return done("error", error("tool.timeout", "The data took too long to load."), parsed)
        except ClarioError as exc:
            return done("error", error(exc.code, exc.detail), parsed)
        except Exception:
            logger.exception("Tool failed", extra={"tool": name})
            return done("error", error("tool.failed", "The data could not be loaded."), parsed)
        return done(result.status, result, parsed)
