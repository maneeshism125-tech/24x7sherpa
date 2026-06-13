from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class SignalDetail(BaseModel):
    name: str
    value: float | str
    score: float = Field(ge=0, le=100)
    interpretation: str
    weight: float


class TradeRecommendation(BaseModel):
    rank: int
    symbol: str
    index: Literal["DOW", "NASDAQ"]
    current_price: float
    recommendation: Literal["BUY_CALL", "BUY_PUT", "NEUTRAL", "SELL_PREMIUM"]
    confidence: float = Field(ge=0, le=100)
    composite_score: float = Field(ge=0, le=100)
    suggested_strike: float | None = None
    suggested_expiry: str | None = None
    put_call_ratio: float
    implied_volatility: float | None = None
    iv_rank: float | None = None
    signals: list[SignalDetail]
    summary: str


class OptionsRecommendationsResponse(BaseModel):
    generated_at: str
    market_date: str
    dow_jones: list[TradeRecommendation]
    nasdaq: list[TradeRecommendation]
    disclaimer: str
