"""Fetch stock and options data via yfinance."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_stock_history(symbol: str, period: str = "6mo") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)
    if hist.empty:
        raise ValueError(f"No price history for {symbol}")
    return hist


def fetch_current_price(symbol: str) -> float:
    ticker = yf.Ticker(symbol)
    info = ticker.fast_info
    price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
    if price is None:
        hist = ticker.history(period="5d")
        if hist.empty:
            raise ValueError(f"No price data for {symbol}")
        price = float(hist["Close"].iloc[-1])
    return float(price)


def fetch_options_expirations(symbol: str) -> list[str]:
    ticker = yf.Ticker(symbol)
    expirations = ticker.options
    return list(expirations) if expirations else []


def fetch_options_chain(symbol: str, expiration: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ticker = yf.Ticker(symbol)
    chain = ticker.option_chain(expiration)
    return chain.calls.copy(), chain.puts.copy()


def pick_nearest_expiry(expirations: list[str], min_days: int = 14, max_days: int = 45) -> str | None:
    if not expirations:
        return None
    today = datetime.now().date()
    best = None
    best_delta = None
    target = min_days + (max_days - min_days) // 2

    for exp in expirations:
        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
        days = (exp_date - today).days
        if days < min_days:
            continue
        delta = abs(days - target)
        if best is None or delta < best_delta:
            best = exp
            best_delta = delta

    return best or expirations[0]


def compute_historical_volatility(closes: pd.Series, window: int = 20) -> float:
    if len(closes) < window + 1:
        return 0.0
    returns = np.log(closes / closes.shift(1)).dropna()
    if returns.empty:
        return 0.0
    return float(returns.tail(window).std() * np.sqrt(252) * 100)


def aggregate_chain_metrics(calls: pd.DataFrame, puts: pd.DataFrame) -> dict[str, Any]:
    call_volume = int(calls["volume"].fillna(0).sum()) if not calls.empty else 0
    put_volume = int(puts["volume"].fillna(0).sum()) if not puts.empty else 0
    call_oi = int(calls["openInterest"].fillna(0).sum()) if not calls.empty else 0
    put_oi = int(puts["openInterest"].fillna(0).sum()) if not puts.empty else 0

    pcr_volume = put_volume / call_volume if call_volume > 0 else (2.0 if put_volume > 0 else 1.0)
    pcr_oi = put_oi / call_oi if call_oi > 0 else (2.0 if put_oi > 0 else 1.0)

    call_iv = calls["impliedVolatility"].replace(0, np.nan).dropna()
    put_iv = puts["impliedVolatility"].replace(0, np.nan).dropna()
    avg_iv = float(pd.concat([call_iv, put_iv]).mean() * 100) if len(call_iv) + len(put_iv) > 0 else None
    call_iv_mean = float(call_iv.mean() * 100) if not call_iv.empty else None
    put_iv_mean = float(put_iv.mean() * 100) if not put_iv.empty else None

    return {
        "call_volume": call_volume,
        "put_volume": put_volume,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "pcr_volume": round(pcr_volume, 3),
        "pcr_oi": round(pcr_oi, 3),
        "avg_iv": avg_iv,
        "call_iv_mean": call_iv_mean,
        "put_iv_mean": put_iv_mean,
        "calls": calls,
        "puts": puts,
    }


def find_atm_strike(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> float:
    strikes = sorted(set(calls["strike"].tolist() + puts["strike"].tolist()))
    if not strikes:
        return spot
    return min(strikes, key=lambda s: abs(s - spot))


def compute_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    if calls.empty and puts.empty:
        return None

    strikes = sorted(set(calls["strike"].tolist() + puts["strike"].tolist()))
    if not strikes:
        return None

    min_pain = float("inf")
    max_pain_strike = strikes[len(strikes) // 2]

    call_oi_map = calls.set_index("strike")["openInterest"].fillna(0).to_dict() if not calls.empty else {}
    put_oi_map = puts.set_index("strike")["openInterest"].fillna(0).to_dict() if not puts.empty else {}

    for test_strike in strikes:
        pain = 0.0
        for strike, oi in call_oi_map.items():
            if test_strike > strike:
                pain += (test_strike - strike) * oi * 100
        for strike, oi in put_oi_map.items():
            if test_strike < strike:
                pain += (strike - test_strike) * oi * 100
        if pain < min_pain:
            min_pain = pain
            max_pain_strike = test_strike

    return float(max_pain_strike)


def detect_unusual_activity(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> dict[str, Any]:
    unusual_calls: list[dict] = []
    unusual_puts: list[dict] = []

    for label, df, bucket in [("call", calls, unusual_calls), ("put", puts, unusual_puts)]:
        if df.empty:
            continue
        near = df[(df["strike"] >= spot * 0.95) & (df["strike"] <= spot * 1.05)].copy()
        if near.empty:
            near = df.copy()
        near = near[near["volume"].fillna(0) > 0]
        if near.empty:
            continue
        near["vol_oi"] = near["volume"] / near["openInterest"].replace(0, np.nan)
        threshold = near["vol_oi"].quantile(0.75)
        if pd.isna(threshold):
            continue
        flagged = near[near["vol_oi"] >= max(threshold, 1.5)]
        for _, row in flagged.nlargest(3, "volume").iterrows():
            bucket.append({
                "type": label,
                "strike": float(row["strike"]),
                "volume": int(row["volume"]),
                "open_interest": int(row.get("openInterest", 0) or 0),
                "vol_oi_ratio": round(float(row["vol_oi"]), 2) if pd.notna(row["vol_oi"]) else 0,
            })

    total_unusual = len(unusual_calls) + len(unusual_puts)
    call_bias = sum(u["volume"] for u in unusual_calls)
    put_bias = sum(u["volume"] for u in unusual_puts)

    return {
        "unusual_calls": unusual_calls,
        "unusual_puts": unusual_puts,
        "total_unusual": total_unusual,
        "call_bias_volume": call_bias,
        "put_bias_volume": put_bias,
    }


def compute_rsi(closes: pd.Series, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else 50.0


def compute_macd_signal(closes: pd.Series) -> dict[str, float]:
    if len(closes) < 35:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return {
        "macd": float(macd.iloc[-1]),
        "signal": float(signal.iloc[-1]),
        "histogram": float(histogram.iloc[-1]),
    }


def compute_iv_rank_samples(closes: pd.Series, window: int = 20) -> list[float]:
    if len(closes) < window + 5:
        return []
    samples: list[float] = []
    for i in range(window, len(closes), 5):
        sample = closes.iloc[: i + 1]
        hv = compute_historical_volatility(sample, window)
        if hv > 0:
            samples.append(hv)
    return samples[-52:]


def estimate_iv_rank(current_iv: float | None, hist_ivs: list[float]) -> float | None:
    if current_iv is None or not hist_ivs:
        return None
    low, high = min(hist_ivs), max(hist_ivs)
    if high <= low:
        return 50.0
    return round((current_iv - low) / (high - low) * 100, 1)
