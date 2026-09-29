#!/usr/bin/env python3
"""Prove OAuth → organization → invoices → customers → payments → expenses → reports.

Run without starting the AI agent:

    python scripts/zoho_smoke.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clario.scripts_api import run_smoke  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_smoke()))
