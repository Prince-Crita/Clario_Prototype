"""The AI provider's availability, as its own responses last reported it (never assumed).

  available       the last response succeeded and none of the limits it reported is exhausted
  limit_reached   a response said to wait (a 429's retry-after, or an exhausted limit in the
                  headers): questions fail fast until then, so no call is spent on a refusal
  unconfirmed     nothing is known yet in this process, or a wait has passed without a new
                  response. The next question is sent, and its real response decides.

A reset time passing does NOT make the provider "available": Groq's retry-after covers one request
of the refused size, while a question makes several calls against a rolling daily budget, so only
a real response can confirm. Kept per process on a monotonic clock.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from clario.ai.providers.base import LimitScope

UNKNOWN_RESET_SECONDS = 60.0  # a 429 without any reset time: hold off briefly, show no countdown
State = Literal["available", "limit_reached", "unconfirmed"]


@dataclass(frozen=True, slots=True)
class UsageLimit:
    resets_in_seconds: int | None
    scope: LimitScope | None


class ProviderStatus:
    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        self._state: State = "unconfirmed"
        self._until = 0.0
        self._known = False
        self._scope: LimitScope | None = None

    def record_limit(self, retry_after: float | None, scope: LimitScope | None) -> None:
        self._state = "limit_reached"
        self._known = retry_after is not None
        wait = retry_after if retry_after is not None else UNKNOWN_RESET_SECONDS
        self._until = self._now() + max(wait, 0.0)
        self._scope = scope

    def record_success(self, wait_before_next: float | None) -> None:
        """A real answer: available, unless its own headers say a limit is now exhausted."""
        if wait_before_next is not None and wait_before_next > 0:
            self.record_limit(wait_before_next, None)
        else:
            self._state = "available"

    def state(self) -> State:
        if self._state == "limit_reached" and self._now() >= self._until:
            self._state = "unconfirmed"  # the wait is over; the next real response decides
        return self._state

    def limit(self) -> UsageLimit | None:
        """The limit in force now, if any."""
        if self.state() != "limit_reached":
            return None
        left = self._until - self._now()
        return UsageLimit(math.ceil(left) if self._known else None, self._scope)
