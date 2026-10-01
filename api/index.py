"""Vercel serverless entrypoint: the Clario API (FastAPI) as the function behind `/api/*`.

This is the ONLY Python entrypoint of the deployment. The root `vercel.json` turns off Vercel's
Python framework auto-detection (which would otherwise scan the repository and trip over
`reference/demo/` and `backend/tests/`) and routes every `/api/*` request here.

The package lives in `backend/src`, so that goes on the path first. Configuration comes from the
Vercel project's environment variables; there is no .env file in the deployment.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

# A serverless function may be frozen once its response is sent, so the Zoho import has to finish
# inside the request (see Settings.sync_inline). A project variable of the same name still wins.
os.environ.setdefault("SYNC_INLINE", "true")

from clario.main import create_app  # noqa: E402

app = create_app()
