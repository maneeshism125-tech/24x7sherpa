from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.admin_routes import router as admin_router
from api.auth_startup import run_auth_startup
from api.protected_routes import router as protected_router
from api.public_routes import router as public_router
from sherpa.config import get_settings

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "web" / "dist"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if os.environ.get("SHERPA_SKIP_CHDIR") != "1":
        try:
            os.chdir(REPO_ROOT)
        except OSError:
            pass
    s = get_settings()
    logger.info("Sherpa API data_dir=%s cwd=%s", s.data_dir.resolve(), Path.cwd())
    try:
        run_auth_startup(s)
    except Exception:
        logger.exception("Auth startup failed")
        raise
    yield


app = FastAPI(
    title="Sherpa Trader",
    description="S&P 500 research, paper simulation, and signals",
    version="0.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(protected_router)
app.include_router(admin_router)


def _mount_frontend() -> None:
    assets = DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False, response_model=None)
    async def spa_index():
        index = DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {
                "message": "API is running. Build the UI: cd web && npm install && npm run build",
                "docs": "/docs",
                "health": "/api/health",
            }
        )


_mount_frontend()
