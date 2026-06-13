"""Score symbols and produce ranked options trade recommendations."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal

from sherpa.options.constants import (
    DOW_JONES_30,
    NASDAQ_100,
    PCR_BEARISH,
    PCR_BULLISH,
    SCORE_WEIGHTS,
    UNUSUAL_VOLUME_OI_RATIO,
)
from sherpa.options.market_data import (
    aggregate_chain_metrics,
    compute_historical_volatility,
    compute_iv_rank_samples,
    compute_macd_signal,
    compute_max_pain,
    compute_rsi,
    detect_unusual_activity,
    estimate_iv_rank,
    fetch_current_price,
    fetch_options_chain,
    fetch_options_expirations,
    fetch_stock_history,
    find_atm_strike,
    pick_nearest_expiry,
)
from sherpa.options.models import SignalDetail, TradeRecommendation

logger = logging.getLogger(__name__)


def _score_put_call_ratio(pcr: float) -> tuple[float, str, Literal["BUY_CALL", "BUY_PUT", "NEUTRAL"]]:
    if pcr <= PCR_BULLISH:
        score = min(100, 70 + (PCR_BULLISH - pcr) * 60)
        return score, f"Bullish sentiment (PCR {pcr:.2f} — heavy call activity)", "BUY_CALL"
    if pcr >= PCR_BEARISH:
        score = min(100, 70 + (pcr - PCR_BEARISH) * 40)
        return score, f"Bearish sentiment (PCR {pcr:.2f} — heavy put activity)", "BUY_PUT"
    return 50.0, f"Neutral PCR ({pcr:.2f})", "NEUTRAL"


def _score_iv_analysis(iv: float | None, hv: float, iv_rank: float | None) -> tuple[float, str, str]:
    if iv is None:
        return 40.0, "IV data unavailable", "NEUTRAL"
    iv_hv_spread = iv - hv
    if iv_rank is not None:
        if iv_rank >= 70:
            return 85.0, f"High IV rank ({iv_rank:.0f}%) — premium selling favorable", "SELL_PREMIUM"
        if iv_rank <= 30:
            return 80.0, f"Low IV rank ({iv_rank:.0f}%) — cheap options, buy premium", "BUY_CALL"
    if iv_hv_spread > 15:
        return 75.0, f"IV ({iv:.1f}%) well above HV ({hv:.1f}%) — inflated premium", "SELL_PREMIUM"
    if iv_hv_spread < -5:
        return 75.0, f"IV ({iv:.1f}%) below HV ({hv:.1f}%) — underpriced options", "BUY_CALL"
    return 50.0, f"IV {iv:.1f}% vs HV {hv:.1f}% — fairly priced", "NEUTRAL"


def _score_unusual_activity(activity: dict) -> tuple[float, str, str]:
    total = activity["total_unusual"]
    call_vol = activity["call_bias_volume"]
    put_vol = activity["put_bias_volume"]
    if total == 0:
        return 35.0, "No unusual options activity detected", "NEUTRAL"
    ratio = call_vol / put_vol if put_vol > 0 else (3.0 if call_vol > 0 else 1.0)
    score = min(100, 50 + total * 8)
    if ratio >= 1.5:
        return score, f"Unusual call buying ({total} flagged strikes, {call_vol:,} vol)", "BUY_CALL"
    if ratio <= 0.67:
        return score, f"Unusual put buying ({total} flagged strikes, {put_vol:,} vol)", "BUY_PUT"
    return score, f"Mixed unusual activity ({total} flagged strikes)", "NEUTRAL"


def _score_momentum(rsi: float, macd: dict) -> tuple[float, str, str]:
    hist = macd["histogram"]
    bullish = bearish = 0
    if rsi < 35:
        bullish += 1
    elif rsi > 65:
        bearish += 1
    if hist > 0:
        bullish += 1
    elif hist < 0:
        bearish += 1
    if bullish >= 2:
        return 78.0, f"Oversold/momentum turning up (RSI {rsi:.0f}, MACD hist +)", "BUY_CALL"
    if bearish >= 2:
        return 78.0, f"Overbought/momentum fading (RSI {rsi:.0f}, MACD hist -)", "BUY_PUT"
    if rsi < 45 and hist > 0:
        return 62.0, f"Mild bullish momentum (RSI {rsi:.0f})", "BUY_CALL"
    if rsi > 55 and hist < 0:
        return 62.0, f"Mild bearish momentum (RSI {rsi:.0f})", "BUY_PUT"
    return 45.0, f"Mixed momentum (RSI {rsi:.0f})", "NEUTRAL"


def _score_volume_oi(metrics: dict) -> tuple[float, str]:
    call_v, put_v = metrics["call_volume"], metrics["put_volume"]
    call_oi, put_oi = metrics["call_oi"], metrics["put_oi"]
    total_vol = call_v + put_v
    total_oi = call_oi + put_oi
    if total_oi == 0:
        return 30.0, "Low options liquidity"
    vol_oi = total_vol / total_oi
    if vol_oi >= UNUSUAL_VOLUME_OI_RATIO:
        return min(95, 60 + vol_oi * 10), f"High volume/OI ({vol_oi:.2f}x) — active positioning"
    if vol_oi >= 1.0:
        return 65.0, f"Elevated volume/OI ({vol_oi:.2f}x)"
    return 45.0, f"Normal volume/OI ({vol_oi:.2f}x)"


def _score_iv_skew(call_iv: float | None, put_iv: float | None) -> tuple[float, str, str]:
    if call_iv is None or put_iv is None:
        return 40.0, "IV skew data unavailable", "NEUTRAL"
    skew = put_iv - call_iv
    if skew > 5:
        return 72.0, f"Put skew +{skew:.1f}% — hedging/fear premium in puts", "BUY_PUT"
    if skew < -3:
        return 72.0, f"Call skew {skew:.1f}% — bullish demand in calls", "BUY_CALL"
    return 48.0, f"Balanced skew ({skew:+.1f}%)", "NEUTRAL"


def _pd_notna(val) -> bool:
    try:
        import pandas as pd
        return bool(pd.notna(val))
    except Exception:
        return val is not None


def _score_liquidity(calls, puts) -> tuple[float, str]:
    spreads = []
    for df in (calls, puts):
        if df.empty:
            continue
        valid = df[(df["bid"] > 0) & (df["ask"] > 0)]
        if valid.empty:
            continue
        spread_pct = ((valid["ask"] - valid["bid"]) / valid["ask"] * 100).median()
        if _pd_notna(spread_pct):
            spreads.append(spread_pct)
    if not spreads:
        return 35.0, "Limited liquidity data"
    avg_spread = sum(spreads) / len(spreads)
    if avg_spread <= 5:
        return 85.0, f"Tight spreads (~{avg_spread:.1f}%) — good for trading"
    if avg_spread <= 12:
        return 60.0, f"Moderate spreads (~{avg_spread:.1f}%)"
    return 35.0, f"Wide spreads (~{avg_spread:.1f}%) — slippage risk"


def _score_max_pain(max_pain: float | None, spot: float) -> tuple[float, str, str]:
    if max_pain is None:
        return 40.0, "Max pain unavailable", "NEUTRAL"
    diff_pct = (max_pain - spot) / spot * 100
    if diff_pct > 2:
        return 68.0, f"Max pain ${max_pain:.0f} above spot — upward pin potential", "BUY_CALL"
    if diff_pct < -2:
        return 68.0, f"Max pain ${max_pain:.0f} below spot — downward pin potential", "BUY_PUT"
    return 50.0, f"Max pain ${max_pain:.0f} near spot — range-bound", "NEUTRAL"


def _resolve_recommendation(votes: dict[str, int]) -> str:
    order = ["BUY_CALL", "BUY_PUT", "SELL_PREMIUM", "NEUTRAL"]
    return max(order, key=lambda k: votes.get(k, 0))


def analyze_symbol(symbol: str, index: Literal["DOW", "NASDAQ"]) -> TradeRecommendation | None:
    try:
        spot = fetch_current_price(symbol)
        hist = fetch_stock_history(symbol)
        closes = hist["Close"]
        hv = compute_historical_volatility(closes)
        hv_samples = compute_iv_rank_samples(closes)
        rsi = compute_rsi(closes)
        macd = compute_macd_signal(closes)

        expirations = fetch_options_expirations(symbol)
        expiry = pick_nearest_expiry(expirations)
        if not expiry:
            logger.warning("No options expirations for %s", symbol)
            return None

        calls, puts = fetch_options_chain(symbol, expiry)
        metrics = aggregate_chain_metrics(calls, puts)
        max_pain = compute_max_pain(calls, puts)
        activity = detect_unusual_activity(calls, puts, spot)
        atm_strike = find_atm_strike(calls, puts, spot)

        pcr = metrics["pcr_volume"]
        iv = metrics["avg_iv"]
        iv_rank = estimate_iv_rank(iv, hv_samples)

        pcr_score, pcr_interp, pcr_dir = _score_put_call_ratio(pcr)
        iv_score, iv_interp, iv_dir = _score_iv_analysis(iv, hv, iv_rank)
        ua_score, ua_interp, ua_dir = _score_unusual_activity(activity)
        mom_score, mom_interp, mom_dir = _score_momentum(rsi, macd)
        voi_score, voi_interp = _score_volume_oi(metrics)
        skew_score, skew_interp, skew_dir = _score_iv_skew(metrics["call_iv_mean"], metrics["put_iv_mean"])
        liq_score, liq_interp = _score_liquidity(calls, puts)
        mp_score, mp_interp, mp_dir = _score_max_pain(max_pain, spot)

        signals = [
            SignalDetail(name="Put/Call Ratio", value=pcr, score=pcr_score, interpretation=pcr_interp, weight=SCORE_WEIGHTS["put_call_ratio"]),
            SignalDetail(name="IV Analysis", value=f"{iv:.1f}%" if iv else "N/A", score=iv_score, interpretation=iv_interp, weight=SCORE_WEIGHTS["iv_analysis"]),
            SignalDetail(name="Unusual Activity", value=activity["total_unusual"], score=ua_score, interpretation=ua_interp, weight=SCORE_WEIGHTS["unusual_activity"]),
            SignalDetail(name="Momentum (RSI/MACD)", value=f"RSI {rsi:.0f}", score=mom_score, interpretation=mom_interp, weight=SCORE_WEIGHTS["momentum"]),
            SignalDetail(name="Volume/OI", value=f"{metrics['call_volume'] + metrics['put_volume']:,}", score=voi_score, interpretation=voi_interp, weight=SCORE_WEIGHTS["volume_oi"]),
            SignalDetail(name="IV Skew", value=f"{(metrics['put_iv_mean'] or 0) - (metrics['call_iv_mean'] or 0):+.1f}%", score=skew_score, interpretation=skew_interp, weight=SCORE_WEIGHTS["iv_skew"]),
            SignalDetail(name="Liquidity", value=liq_interp.split("—")[0].strip(), score=liq_score, interpretation=liq_interp, weight=SCORE_WEIGHTS["liquidity"]),
            SignalDetail(name="Max Pain", value=f"${max_pain:.0f}" if max_pain else "N/A", score=mp_score, interpretation=mp_interp, weight=SCORE_WEIGHTS["max_pain"]),
        ]

        composite = sum(s.score * s.weight for s in signals)
        votes: dict[str, int] = {"BUY_CALL": 0, "BUY_PUT": 0, "SELL_PREMIUM": 0, "NEUTRAL": 0}
        for direction, weight_key in [
            (pcr_dir, 3), (iv_dir, 2), (ua_dir, 3), (mom_dir, 2),
            (skew_dir, 2), (mp_dir, 1),
        ]:
            if direction != "NEUTRAL":
                votes[direction] += weight_key

        recommendation = _resolve_recommendation(votes)
        confidence = min(95, composite * 0.6 + max(votes.values()) * 5)
        rec_labels = {
            "BUY_CALL": "Buy Call",
            "BUY_PUT": "Buy Put",
            "SELL_PREMIUM": "Sell Premium (Credit Spread / Iron Condor)",
            "NEUTRAL": "Wait / No Clear Edge",
        }
        summary = (
            f"{symbol} @ ${spot:.2f} — {rec_labels[recommendation]}. "
            f"Key driver: {max(signals, key=lambda s: s.score * s.weight).name}."
        )

        return TradeRecommendation(
            rank=0,
            symbol=symbol,
            index=index,
            current_price=round(spot, 2),
            recommendation=recommendation,
            confidence=round(confidence, 1),
            composite_score=round(composite, 1),
            suggested_strike=atm_strike,
            suggested_expiry=expiry,
            put_call_ratio=pcr,
            implied_volatility=round(iv, 2) if iv else None,
            iv_rank=iv_rank,
            signals=signals,
            summary=summary,
        )
    except Exception as exc:
        logger.warning("Failed to analyze %s: %s", symbol, exc)
        return None


def rank_recommendations(recs: list[TradeRecommendation], top_n: int = 10) -> list[TradeRecommendation]:
    actionable = [r for r in recs if r.recommendation != "NEUTRAL"]
    neutral = [r for r in recs if r.recommendation == "NEUTRAL"]
    sorted_recs = sorted(actionable, key=lambda r: (r.composite_score, r.confidence), reverse=True)
    sorted_recs += sorted(neutral, key=lambda r: r.composite_score, reverse=True)
    top = sorted_recs[:top_n]
    for i, rec in enumerate(top, 1):
        rec.rank = i
    return top


def generate_index_recommendations(
    symbols: list[str],
    index: Literal["DOW", "NASDAQ"],
    top_n: int = 10,
    max_workers: int = 8,
) -> list[TradeRecommendation]:
    results: list[TradeRecommendation] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(analyze_symbol, sym, index): sym for sym in symbols}
        for future in as_completed(futures):
            rec = future.result()
            if rec:
                results.append(rec)
    return rank_recommendations(results, top_n)


def generate_all_recommendations() -> tuple[list[TradeRecommendation], list[TradeRecommendation]]:
    dow = generate_index_recommendations(DOW_JONES_30, "DOW", 10)
    nasdaq = generate_index_recommendations(NASDAQ_100, "NASDAQ", 10)
    return dow, nasdaq
