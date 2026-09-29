#!/usr/bin/env bash
# Restart Clario (stops whatever is on CLARIO_PORT, then starts again so .env reloads).
# Usage from repo root:
#   ./scripts/restart.sh
# or:
#   .venv/bin/python -m clario restart

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
else
  echo "No Python found. Create .venv or install Python 3.11+." >&2
  exit 1
fi

exec "$PY" -m clario restart
