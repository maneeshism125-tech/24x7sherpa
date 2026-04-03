from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SimulateResetBody(BaseModel):
    profile: str = Field(default="default", max_length=64)
    cash: float = Field(default=100_000.0, gt=0, le=1e12)


class TradeBody(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    side: str = Field(...)
    qty: int = Field(..., ge=1, le=1_000_000)
    profile: str = Field(default="default", max_length=64)

    @field_validator("side")
    @classmethod
    def normalize_side(cls, v: str) -> str:
        s = v.lower().strip()
        if s not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        return s


class SignalRow(BaseModel):
    symbol: str
    side: str
    score: float
    reasons: list[str]


class PositionRow(BaseModel):
    symbol: str
    qty: int
    last: float
    market_value: float


class SimulationStatusResponse(BaseModel):
    profile: str
    path: str
    starting_cash: float
    equity: float
    cash: float
    pnl: float
    positions: list[PositionRow]
    last_reset: str | None = None


class AccountResponse(BaseModel):
    equity: float
    cash: float
    buying_power: float
    profile: str


class TradeResponse(BaseModel):
    status: str
    broker_order_id: str
    filled_qty: int
    avg_fill_price: float | None
    symbol: str


class ScanResponse(BaseModel):
    signals: list[SignalRow]
    scanned: int


class DailyPickRow(BaseModel):
    symbol: str
    score: float
    reasons: list[str]
    last_close: float | None = None
    sma5: float | None = None
    sma10: float | None = None
    sma200: float | None = None
    rsi: float | None = None
    atr_pct: float | None = None
    volume_last: float | None = None
    target_buy_price: float | None = None
    target_sell_price: float | None = None


class DailyRecommendationsResponse(BaseModel):
    picks: list[DailyPickRow]
    disclaimer: str
    universe_cap: int
    candidates_scored: int
