"""
Rule-based daily ranking of US equity names (technicals + headlines).

This is not investment advice and does not predict returns (including +1% days).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from sherpa.config import Settings, get_settings
from sherpa.providers import create_news_provider, create_price_provider
from sherpa.providers.base import NewsItem
from sherpa.recommendations.criteria import PickCriteria
from sherpa.signals.engine import NEGATIVE_NEWS_KEYWORDS
from sherpa.technical.indicators import compute_features
from sherpa.universe.indices import get_universe_tickers

DISCLAIMER = (
    "Educational ranking only. Past patterns and headlines do not predict future prices "
    "or any specific gain. Target buy/sell levels are rough ATR/SMA-based heuristics only — "
    "not guaranteed fills or outcomes. You alone decide whether to trade."
)


@dataclass(frozen=True)
class DailyPick:
    symbol: str
    score: float
    reasons: tuple[str, ...]
    last_close: float | None
    sma5: float | None
    sma10: float | None
    sma200: float | None
    rsi: float | None
    atr_pct: float | None
    volume_last: float | None
    target_buy_price: float | None
    target_sell_price: float | None


def _suggested_prices(last: pd.Series, cr: PickCriteria) -> tuple[float | None, float | None]:
    """Heuristic limit-style buy (pullback) and first take-profit using ATR; not advice."""
    c = float(last["close"])
    atr = last.get("atr_14")
    sma200 = last.get("sma_200")
    sma10 = last.get("sma_10")

    if pd.isna(sma200):
        return None, None
    sma200_f = float(sma200)
    if c <= sma200_f:
        return None, None

    if pd.isna(atr) or float(atr) <= 0:
        atr_f = c * 0.008
    else:
        atr_f = float(atr)

    floor = sma200_f * 1.001
    if not pd.isna(sma10):
        pull = min(float(sma10), c - 0.2 * atr_f)
    else:
        pull = c - 0.35 * atr_f
    raw_buy = min(c - 0.08 * atr_f, pull)
    target_buy = max(floor, raw_buy)
    if target_buy >= c - 0.01:
        target_buy = max(floor, c - 0.2 * atr_f)
    target_buy = round(target_buy, 2)

    mult = max(0.1, min(5.0, cr.sell_atr_multiplier))
    target_sell = round(min(c + mult * atr_f, c * 1.12), 2)

    return target_buy, target_sell


def _score_candidate(
    feats: pd.DataFrame,
    news: list[NewsItem],
    cr: PickCriteria,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if feats.empty or len(feats) < 2:
        return 0.0, ["insufficient_history"]

    last = feats.iloc[-1]
    prev = feats.iloc[-2]
    c = float(last["close"])
    sma5 = last.get("sma_5")
    sma10 = last.get("sma_10")
    if pd.isna(sma5) or pd.isna(sma10):
        return 0.0, ["moving_averages_not_ready"]

    sma5 = float(sma5)
    sma10 = float(sma10)
    score = 0.0

    lo, hi = cr.rsi_band_low, cr.rsi_band_high
    ob = cr.rsi_overbought
    vsurge = cr.volume_surge_ratio
    atr_hi = cr.atr_elevated_pct
    npen = max(0.0, min(100.0, cr.news_penalty))

    sma200 = last.get("sma_200")
    if not pd.isna(sma200) and c > float(sma200):
        score += 14.0
        reasons.append("close > SMA(200) (long-term trend filter)")

    if c > sma10 and sma5 > sma10:
        score += 22.0
        reasons.append("close > SMA(10) and SMA(5) > SMA(10) (short-term momentum)")

    if c > sma5 and c > sma10:
        score += 10.0
        reasons.append("close above both SMA(5) and SMA(10)")

    if prev["sma_5"] <= prev["sma_10"] and last["sma_5"] > last["sma_10"]:
        score += 14.0
        reasons.append("SMA(5) crossed above SMA(10)")

    sma20 = last.get("sma_20")
    sma50 = last.get("sma_50")
    if not pd.isna(sma20) and not pd.isna(sma50):
        sma20, sma50 = float(sma20), float(sma50)
        if sma20 > sma50:
            score += 14.0
            reasons.append("SMA(20) > SMA(50) (intermediate uptrend)")
        if c > sma20:
            score += 8.0
            reasons.append("close > SMA(20)")

    rsi = last.get("rsi_14")
    if not pd.isna(rsi):
        rsi = float(rsi)
        if lo < rsi < hi:
            score += 10.0
            reasons.append(f"RSI(14)={rsi:.0f} in neutral/constructive band ({lo:.0f}-{hi:.0f})")
        elif rsi <= lo:
            score += 4.0
            reasons.append(f"RSI(14)={rsi:.0f} on the lower side (bounce/risk trade)")
        elif rsi >= ob:
            score -= 12.0
            reasons.append(f"RSI(14)={rsi:.0f} extended vs {ob:.0f} (pullback risk)")

    vol = last.get("volume")
    v20 = feats["volume"].tail(20).mean() if len(feats) >= 20 else None
    if vol is not None and v20 is not None and not pd.isna(v20) and float(v20) > 0:
        vr = float(vol) / float(v20)
        if vr >= vsurge:
            score += 6.0
            reasons.append(f"volume vs 20d avg ~{vr:.2f}x (threshold {vsurge:.2f}x)")

    atrp = last.get("atr_pct")
    if not pd.isna(atrp) and atrp is not None:
        atrp = float(atrp)
        reasons.append(f"ATR(14)/price ~{atrp * 100:.2f}% (used for suggested targets)")
        if atrp >= atr_hi:
            score += 4.0
            reasons.append(f"elevated ATR vs price (≥{atr_hi * 100:.2f}% of price)")

    blob = " ".join(n.title.lower() for n in news[:12])
    neg = [k for k in NEGATIVE_NEWS_KEYWORDS if k in blob]
    if neg:
        score -= npen
        reasons.append(f"headline risk keywords: {', '.join(neg[:4])}")

    score = max(0.0, min(100.0, score))
    return score, reasons


def run_daily_picks(
    settings: Settings | None = None,
    *,
    criteria: PickCriteria | None = None,
) -> tuple[list[DailyPick], str, int]:
    """
    Rank symbols from ``criteria.universe_id`` using filters + scoring.
    """
    cr = criteria or PickCriteria()
    s = settings or get_settings()
    prices = create_price_provider(s)
    news_p = create_news_provider(s)
    tickers = get_universe_tickers(cr.universe_id)[: cr.universe_cap]

    need_days = max(400, cr.min_bars + 80)

    rows: list[DailyPick] = []
    for sym in tickers:
        bars = prices.history_daily(sym, days=need_days)
        feats = compute_features(bars)
        if feats.empty or len(feats) < cr.min_bars:
            continue
        last = feats.iloc[-1]
        if pd.isna(last.get("sma_200")):
            continue
        sma200 = float(last["sma_200"])
        c = float(last["close"])
        if cr.require_above_sma200 and c <= sma200:
            continue
        vol = last.get("volume")
        if pd.isna(vol) or float(vol) < float(cr.min_volume):
            continue

        news = [] if cr.skip_news else news_p.headlines_for_symbol(sym, limit=10)
        sc, rlist = _score_candidate(feats, news, cr)
        tb, ts = _suggested_prices(last, cr)

        rows.append(
            DailyPick(
                symbol=sym,
                score=round(sc, 2),
                reasons=tuple(rlist),
                last_close=c if not pd.isna(last["close"]) else None,
                sma5=float(last["sma_5"]) if not pd.isna(last.get("sma_5")) else None,
                sma10=float(last["sma_10"]) if not pd.isna(last.get("sma_10")) else None,
                sma200=sma200,
                rsi=float(last["rsi_14"]) if not pd.isna(last.get("rsi_14")) else None,
                atr_pct=float(last["atr_pct"]) if not pd.isna(last.get("atr_pct")) else None,
                volume_last=float(vol),
                target_buy_price=tb,
                target_sell_price=ts,
            )
        )

    rows.sort(key=lambda x: x.score, reverse=True)
    scored = len(rows)
    top = rows[: cr.pick_count]
    return top, DISCLAIMER, scored
