#!/usr/bin/env python3
"""Print the Zoho Books authorization URL for this environment."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clario.config import get_settings  # noqa: E402
from clario.zoho.oauth import ZohoOAuth  # noqa: E402


def main() -> int:
    url, state = ZohoOAuth(get_settings()).authorization_url()
    print(url)
    print(f"state={state}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
