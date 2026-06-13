from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class SimulateResetBody(BaseModel):
    profile: str = Field(default="default", max_length=64)
    cash: float = Field(default=100_000.0, gt=0, le=1e12)


class TradeBody(BaseModel):
    """Paper trade request (market, limit, stop / stop-market, stop-limit)."""

    symbol: str = Field(..., min_length=1, max_length=16)
    side: str = Field(...)
    qty: int = Field(..., ge=1, le=1_000_000)
    profile: str = Field(default="default", max_length=64)
    order_type: Literal["market", "limit", "stop", "stop_limit"] = "market"
    limit_price: float | None = Field(None, gt=0)
    stop_price: float | None = Field(None, gt=0)

    @field_validator("side")
    @classmethod
    def normalize_side(cls, v: str) -> str:
        s = v.lower().strip()
        if s not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        return s

    @model_validator(mode="after")
    def validate_prices_for_order_type(self) -> TradeBody:
        ot = self.order_type
        if ot == "limit" and self.limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        if ot == "stop" and self.stop_price is None:
            raise ValueError("stop_price is required for stop (stop-market) orders")
        if ot == "stop_limit" and (self.stop_price is None or self.limit_price is None):
            raise ValueError("Both stop_price and limit_price are required for stop-limit orders")
        return self


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
    order_type: str | None = None
    detail: str | None = None


class OpenOrderRow(BaseModel):
    id: str
    symbol: str
    side: str
    qty: int
    order_type: str
    limit_price: float | None = None
    stop_price: float | None = None
    stop_triggered: bool = False
    status: str
    created_at: str


class PaperTickBody(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    profile: str = Field(default="default", max_length=64)


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
    allow_signup: bool


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
    email: str | None = None
    address: str | None = None


class RegisterBody(BaseModel):
    email: EmailStr
    user_id: str = Field(
        ...,
        min_length=3,
        max_length=32,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Letters, digits, underscore only",
    )
    address: str = Field(..., min_length=4, max_length=512)
    password: str = Field(..., min_length=8, max_length=256)


class UserAdminRow(BaseModel):
    user_id: str
    is_admin: bool
    disabled: bool
    created_at: float
    email: str | None = None
    address: str | None = None


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
    email: EmailStr | None = None
    address: str | None = Field(None, max_length=512)


class AdminPatchUserBody(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=256)
    is_admin: bool | None = None
    disabled: bool | None = None
    email: EmailStr | None = None
    address: str | None = Field(None, max_length=512)


class OptionsSignalDetail(BaseModel):
    name: str
    value: float | str
    score: float = Field(ge=0, le=100)
    interpretation: str
    weight: float


class OptionsTradeRecommendation(BaseModel):
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
    signals: list[OptionsSignalDetail]
    summary: str


class OptionsRecommendationsResponse(BaseModel):
    generated_at: str
    market_date: str
    dow_jones: list[OptionsTradeRecommendation]
    nasdaq: list[OptionsTradeRecommendation]
    disclaimer: str


class OptionsPositionRow(BaseModel):
    position_key: str
    underlying: str
    expiry: str
    strike: float
    option_type: Literal["call", "put"]
    contracts: int
    avg_premium: float
    mark: float
    market_value: float
    unrealized_pnl: float


class OptionsTradeBody(BaseModel):
    profile: str = Field(default="default", max_length=64)
    underlying: str = Field(..., min_length=1, max_length=16)
    expiry: str = Field(..., min_length=8, max_length=16, pattern=r"^\d{4}-\d{2}-\d{2}$")
    strike: float = Field(..., gt=0)
    option_type: Literal["call", "put"] = "call"
    contracts: int = Field(default=1, ge=1, le=100)
    action: Literal["buy_to_open", "sell_to_open", "sell_to_close", "buy_to_close"] | None = None
    recommendation: Literal["BUY_CALL", "BUY_PUT", "SELL_PREMIUM"] | None = None

    @model_validator(mode="after")
    def require_action_or_recommendation(self) -> OptionsTradeBody:
        if self.action is None and self.recommendation is None:
            raise ValueError("Provide action or recommendation")
        return self


class OptionsTradeResponse(BaseModel):
    status: str
    broker_order_id: str
    filled_contracts: int
    avg_premium: float
    underlying: str
    expiry: str
    strike: float
    option_type: str
    action: str
    detail: str | None = None


class OptionsPositionsResponse(BaseModel):
    profile: str
    cash: float
    equity: float
    positions: list[OptionsPositionRow]
