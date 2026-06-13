"""Dev server entrypoint for `sherpa-web`. Set PORT=8000 SHERPA_WEB_RELOAD=0 for production."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    import uvicorn

    repo = Path(__file__).resolve().parent.parent
    if os.environ.get("SHERPA_SKIP_CHDIR") != "1":
        try:
            os.chdir(repo)
        except OSError:
            pass

    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("SHERPA_WEB_RELOAD", "1") == "1"
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=reload)
