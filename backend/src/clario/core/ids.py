"""Time-ordered UUIDv7 identifiers (RFC 9562) for primary keys.

PostgreSQL 16 has no native `uuidv7()`, so keys are generated in the application. Time ordering
keeps B-tree index inserts local, unlike random UUIDv4.
"""

from __future__ import annotations

import os
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = 0
_counter = 0


def uuid7() -> uuid.UUID:
    """Return a UUIDv7, monotonic within this process (even for ids in the same millisecond)."""
    global _last_ms, _counter
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms > _last_ms:
            _last_ms = now_ms
            # Random counter start, leaving room to count up within the millisecond.
            _counter = int.from_bytes(os.urandom(2), "big") & 0x3FF
        else:
            _counter += 1
            if _counter > 0xFFF:  # 12-bit counter exhausted: borrow the next millisecond
                _last_ms += 1
                _counter = 0
        ms, counter = _last_ms, _counter

    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version 7
    value |= counter << 64  # rand_a used as a monotonic counter
    value |= 0b10 << 62  # RFC 4122 variant
    value |= rand_b
    return uuid.UUID(int=value)
