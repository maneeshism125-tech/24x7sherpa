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


class PickCriteriaBody(BaseModel):
    """All fields optional; omitted values use server defaults (see PickCriteria)."""

    universe_id: str | None = Field(
        None,
        max_length=32,
        description="sp500 | dow | nasdaq100 (QQQ) | nasdaq (Nasdaq-listed) | russell2000",
    )
    universe_cap: int | None = Field(None, ge=20, le=3500)
    pick_count: int | None = Field(None, ge=1, le=25)
    skip_news: bool | None = None
    min_bars: int | None = Field(None, ge=200, le=400)
    min_volume: float | None = Field(None, ge=0, le=50_000_000)
    require_above_sma200: bool | None = None
    rsi_band_low: float | None = Field(None, ge=0, le=100)
    rsi_band_high: float | None = Field(None, ge=0, le=100)
    rsi_overbought: float | None = Field(None, ge=50, le=100)
    volume_surge_ratio: float | None = Field(None, ge=1.0, le=5.0)
    atr_elevated_pct: float | None = Field(None, ge=0.001, le=0.1)
    news_penalty: float | None = Field(None, ge=0, le=100)
    sell_atr_multiplier: float | None = Field(None, ge=0.1, le=5.0)


class DailyRecommendationsResponse(BaseModel):
    picks: list[DailyPickRow]
    disclaimer: str
    universe_cap: int
    candidates_scored: int
    criteria: dict


class CurrentUser(BaseModel):
    user_id: str
    is_admin: bool


class AuthConfigResponse(BaseModel):
    auth_required: bool


class LoginBody(BaseModel):
    user_id: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    user_id: str
    is_admin: bool


class UserAdminRow(BaseModel):
    user_id: str
    is_admin: bool
    disabled: bool
    created_at: float


class AdminCreateUserBody(BaseModel):
    user_id: str = Field(
        ...,
        min_length=3,
        max_length=32,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Letters, digits, underscore only",
    )
    password: str = Field(..., min_length=8, max_length=256)
    is_admin: bool = False


class AdminPatchUserBody(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=256)
    is_admin: bool | None = None
    disabled: bool | None = None
