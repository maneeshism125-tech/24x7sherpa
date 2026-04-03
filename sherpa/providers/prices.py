from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from sherpa.config import Settings, get_settings
from sherpa.providers.base import Bar, PriceProvider

logger = logging.getLogger(__name__)


class YFinancePriceProvider:
    """Free-tier delayed data via Yahoo; fine for research, not for HFT."""

    def history_daily(self, symbol: str, *, days: int = 120) -> list[Bar]:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{max(days, 5)}d", auto_adjust=False)
        if df is None or df.empty:
            logger.warning("No price history for %s", symbol)
            return []
        out: list[Bar] = []
        for idx, row in df.tail(days).iterrows():
            ts = idx.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            out.append(
                Bar(
                    ts=ts,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )
        return out


def bars_to_dataframe(bars: list[Bar]) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "ts": [b.ts for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )


def create_price_provider(settings: Settings | None = None) -> PriceProvider:
    _ = settings or get_settings()
    return YFinancePriceProvider()
