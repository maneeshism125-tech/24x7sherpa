from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api import services
from api.user_store import get_user_row
from sherpa.config import Settings
from api.deps import get_current_user, settings_dep
from api.schemas import (
    AccountResponse,
    CurrentUser,
    DailyRecommendationsResponse,
    MeResponse,
    PickCriteriaBody,
    ScanResponse,
    SimulateResetBody,
    SimulationStatusResponse,
    TradeBody,
    TradeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


@router.get("/auth/me", response_model=MeResponse)
def auth_me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> MeResponse:
    row = get_user_row(settings.data_dir, user.user_id)
    if not row:
        return MeResponse(
            user_id=user.user_id,
            is_admin=user.is_admin,
            email=None,
            address=None,
        )
    return MeResponse(
        user_id=row["user_id"],
        is_admin=row["is_admin"],
        email=row.get("email"),
        address=row.get("address"),
    )


@router.post("/universe/refresh")
async def api_universe_refresh(
    universe: str = Query(
        "sp500",
        max_length=32,
        description="sp500 | dow | nasdaq100 | nasdaq | russell2000",
    ),
) -> dict:
    return await asyncio.to_thread(services.service_universe_refresh, universe=universe)


@router.get("/scan", response_model=ScanResponse)
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


@router.get("/recommendations/daily", response_model=DailyRecommendationsResponse)
async def api_daily_recommendations(
    universe_id: str | None = Query(
        None,
        max_length=32,
        description="sp500 | dow | nasdaq100 | nasdaq | russell2000",
    ),
    universe_cap: int = Query(150, ge=20, le=3500, description="First N symbols from chosen list"),
    pick_count: int = Query(10, ge=1, le=25),
    skip_news: bool = False,
    min_bars: int = Query(200, ge=200, le=400, description="Need 200+ for SMA(200)"),
    min_volume: float = Query(
        200_000,
        ge=0,
        le=50_000_000,
        description="Min last-session share volume",
    ),
) -> DailyRecommendationsResponse:
    try:
        body = PickCriteriaBody(
            universe_id=universe_id,
            universe_cap=universe_cap,
            pick_count=pick_count,
            skip_news=skip_news,
            min_bars=min_bars,
            min_volume=min_volume,
        )
        return await asyncio.to_thread(services.service_daily_recommendations, body=body)
    except Exception as e:
        logger.exception("daily recommendations failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/recommendations/daily", response_model=DailyRecommendationsResponse)
async def api_daily_recommendations_post(body: PickCriteriaBody) -> DailyRecommendationsResponse:
    try:
        return await asyncio.to_thread(services.service_daily_recommendations, body=body)
    except Exception as e:
        logger.exception("daily recommendations failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/simulate/reset")
async def api_simulate_reset(body: SimulateResetBody) -> dict:
    path = await asyncio.to_thread(
        services.service_simulate_reset,
        profile=body.profile,
        cash=body.cash,
    )
    return {"ok": True, "path": path, "profile": body.profile.strip() or "default"}


@router.get("/simulate/status", response_model=SimulationStatusResponse)
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


@router.get("/account/paper", response_model=AccountResponse)
async def api_account_paper(profile: str = Query("default", max_length=64)) -> AccountResponse:
    try:
        return await asyncio.to_thread(services.service_account_paper, profile=profile)
    except Exception as e:
        logger.exception("account/paper failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/trade/paper", response_model=TradeResponse)
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
