from __future__ import annotations

import pandas as pd

from sherpa.providers.prices import bars_to_dataframe
from sherpa.providers.base import Bar


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def compute_features(bars: list[Bar]) -> pd.DataFrame:
    """Daily bars → SMA5/10/20/50/200, RSI, ATR(14) as percent of price."""
    df = bars_to_dataframe(bars)
    if df.empty or len(df) < 15:
        return df
    df = df.sort_values("ts").reset_index(drop=True)
    c = df["close"]
    df["sma_5"] = c.rolling(5, min_periods=5).mean()
    df["sma_10"] = c.rolling(10, min_periods=10).mean()
    if len(df) >= 20:
        df["sma_20"] = c.rolling(20).mean()
    if len(df) >= 50:
        df["sma_50"] = c.rolling(50).mean()
    if len(df) >= 200:
        df["sma_200"] = c.rolling(200).mean()
    df["rsi_14"] = _rsi(c, 14)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - c.shift(1)).abs(),
            (df["low"] - c.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr_14"] / c
    return df
