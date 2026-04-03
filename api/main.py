from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sherpa.config import get_settings

from api import services
from api.schemas import (
    AccountResponse,
    ScanResponse,
    SimulateResetBody,
    SimulationStatusResponse,
    TradeBody,
    TradeResponse,
)

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


@app.get("/api/health")
def api_health() -> dict:
    return {"ok": True, "service": "sherpa"}


@app.post("/api/universe/refresh")
async def api_universe_refresh() -> dict:
    n = await asyncio.to_thread(services.service_universe_refresh)
    return {"tickers_cached": n}


@app.get("/api/scan", response_model=ScanResponse)
async def api_scan(
    top: int = Query(25, ge=1, le=503),
    skip_news: bool = False,
) -> ScanResponse:
    try:
        return await asyncio.to_thread(
            services.service_scan, top=top, skip_news=skip_news
        )
    except Exception as e:
        logger.exception("scan failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/simulate/reset")
async def api_simulate_reset(body: SimulateResetBody) -> dict:
    path = await asyncio.to_thread(
        services.service_simulate_reset,
        profile=body.profile,
        cash=body.cash,
    )
    return {"ok": True, "path": path, "profile": body.profile.strip() or "default"}


@app.get("/api/simulate/status", response_model=SimulationStatusResponse)
async def api_simulate_status(
    profile: str = Query("default", max_length=64),
) -> SimulationStatusResponse:
    try:
        data = await asyncio.to_thread(services.service_simulation_status, profile=profile)
    except Exception as e:
        logger.exception("simulate/status failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="No simulation state for this profile. POST /api/simulate/reset first.",
        )
    return data


@app.get("/api/account/paper", response_model=AccountResponse)
async def api_account_paper(profile: str = Query("default", max_length=64)) -> AccountResponse:
    try:
        return await asyncio.to_thread(services.service_account_paper, profile=profile)
    except Exception as e:
        logger.exception("account/paper failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/trade/paper", response_model=TradeResponse)
async def api_trade_paper(body: TradeBody) -> TradeResponse:
    try:
        return await asyncio.to_thread(
            services.service_trade_paper,
            symbol=body.symbol,
            side=body.side,
            qty=body.qty,
            profile=body.profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
