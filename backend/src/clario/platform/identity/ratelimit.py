"""Best-effort per-IP limiter for sign-in attempts (plan §12, "Brute force").

In-process sliding window: each worker counts separately, which is acceptable because the
per-account lockout (stored in the database) is the authoritative control. A shared store is only
needed if Clario runs many workers behind a public load balancer.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> bool:
        """Record an attempt; return False when the key is over its limit."""
        moment = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= moment - self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_attempts:
                return False
            hits.append(moment)
            if len(self._hits) > 10_000:  # bound memory under abuse
                for stale in [k for k, v in self._hits.items() if not v]:
                    del self._hits[stale]
            return True
