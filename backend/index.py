"""Vercel entrypoint: exposes the Clario API as `app`.

Vercel's FastAPI runtime looks for a top-level `app` in `index.py`. The package lives under `src/`
(not installed as a distribution on Vercel), so that directory goes on the path first. Everything
else is the normal application factory: configuration comes from the environment variables set on
the Vercel project (see docs/DEPLOY_VERCEL_NEON.md); there is no .env file in the bundle.

Not used locally: `clario serve` runs the same factory under uvicorn.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from clario.main import create_app

app = create_app()
