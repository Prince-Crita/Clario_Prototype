"""Tiny .env loader shared by the Phase 0 scripts (no third-party dependency).

Loads `<repo>/.env` then `<repo>/.env.local` (overrides). Real environment variables win.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_env() -> dict[str, str]:
    merged = {**_parse(REPO_ROOT / ".env"), **_parse(REPO_ROOT / ".env.local")}
    overrides = {k: v for k, v in os.environ.items() if k in merged or k.startswith("ZOHO_SPIKE_")}
    return {**merged, **overrides}


def require(env: dict[str, str], *names: str) -> None:
    missing = [name for name in names if not env.get(name)]
    if missing:
        raise SystemExit(f"Missing in .env / .env.local: {', '.join(missing)}")
