from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from sherpa.providers.base import NewsItem


class Side(str, Enum):
    FLAT = "flat"
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: Side
    score: float
    reasons: tuple[str, ...]


NEGATIVE_NEWS_KEYWORDS = (
    "sec charges",
    "sec investigation",
    "lawsuit",
    "bankruptcy",
    "fraud",
    "restates",
    "halt",
)


class SignalEngine:
    """
    Rule-based demo: trend (SMA20 vs SMA50) + RSI band + optional news filter.
    Replace with your own model; this is a structural placeholder.
    """

    def __init__(
        self,
        *,
        rsi_oversold: float = 35.0,
        rsi_overbought: float = 65.0,
        block_on_negative_news: bool = True,
    ) -> None:
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.block_on_negative_news = block_on_negative_news

    def evaluate(
        self,
        symbol: str,
        features: pd.DataFrame,
        news: list[NewsItem] | None = None,
    ) -> Signal:
        news = news or []
        reasons: list[str] = []

        if features.empty or len(features) < 2:
            return Signal(symbol, Side.FLAT, 0.0, ("insufficient_history",))

        last = features.iloc[-1]
        prev = features.iloc[-2]

        sma20 = last.get("sma_20")
        sma50 = last.get("sma_50")
        rsi = last.get("rsi_14")
        if pd.isna(sma20) or pd.isna(sma50) or pd.isna(rsi):
            return Signal(symbol, Side.FLAT, 0.0, ("indicators_not_ready",))

        crossed_up = prev["sma_20"] <= prev["sma_50"] and last["sma_20"] > last["sma_50"]
        crossed_down = prev["sma_20"] >= prev["sma_50"] and last["sma_20"] < last["sma_50"]

        if self.block_on_negative_news:
            blob = " ".join(n.title.lower() for n in news[:10])
            hits = [k for k in NEGATIVE_NEWS_KEYWORDS if k in blob]
            if hits:
                return Signal(symbol, Side.FLAT, 0.0, tuple(f"news_block:{h}" for h in hits))

        if crossed_up and rsi < self.rsi_overbought:
            reasons.append("sma_cross_up")
            reasons.append(f"rsi={rsi:.1f}")
            return Signal(symbol, Side.LONG, min(1.0, (self.rsi_overbought - float(rsi)) / 30), tuple(reasons))

        if crossed_down and rsi > self.rsi_oversold:
            reasons.append("sma_cross_down")
            reasons.append(f"rsi={rsi:.1f}")
            return Signal(symbol, Side.SHORT, min(1.0, (float(rsi) - self.rsi_oversold) / 30), tuple(reasons))

        if last["sma_20"] > last["sma_50"] and rsi < self.rsi_oversold:
            reasons.append("uptrend_pullback")
            return Signal(symbol, Side.LONG, 0.5, tuple(reasons))

        if last["sma_20"] < last["sma_50"] and rsi > self.rsi_overbought:
            reasons.append("downtrend_rally")
            return Signal(symbol, Side.SHORT, 0.5, tuple(reasons))

        # Fallback so scans usually surface names (strict cross/pullbacks are rare on a given day).
        if float(sma20) > float(sma50):
            reasons.append("bullish_structure")
            reasons.append(f"rsi={rsi:.1f}")
            return Signal(symbol, Side.LONG, 0.25, tuple(reasons))
        if float(sma20) < float(sma50):
            reasons.append("bearish_structure")
            reasons.append(f"rsi={rsi:.1f}")
            return Signal(symbol, Side.SHORT, 0.25, tuple(reasons))

        return Signal(symbol, Side.FLAT, 0.0, ("no_setup",))
