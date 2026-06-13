from __future__ import annotations

import logging
from datetime import datetime, timezone

from cachetools import TTLCache

from sherpa.options.analyzer import analyze_symbol, generate_all_recommendations
from sherpa.options.constants import DOW_JONES_30, NASDAQ_100, OPTIONS_DISCLAIMER
from sherpa.options.models import OptionsRecommendationsResponse, TradeRecommendation

logger = logging.getLogger(__name__)

_options_cache: TTLCache = TTLCache(maxsize=4, ttl=4 * 3600)


def service_options_recommendations(*, refresh: bool = False) -> OptionsRecommendationsResponse:
    cache_key = "daily"
    if not refresh and cache_key in _options_cache:
        return _options_cache[cache_key]

    logger.info("Generating options recommendations (may take several minutes)...")
    dow, nasdaq = generate_all_recommendations()
    response = OptionsRecommendationsResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        market_date=datetime.now().strftime("%Y-%m-%d"),
        dow_jones=dow,
        nasdaq=nasdaq,
        disclaimer=OPTIONS_DISCLAIMER,
    )
    _options_cache[cache_key] = response
    return response


def service_options_symbol(symbol: str) -> TradeRecommendation:
    symbol = symbol.upper()
    index = "DOW" if symbol in DOW_JONES_30 else "NASDAQ"
    rec = analyze_symbol(symbol, index)  # type: ignore[arg-type]
    if not rec:
        raise ValueError(f"Could not analyze {symbol}")
    rec.rank = 1
    return rec
