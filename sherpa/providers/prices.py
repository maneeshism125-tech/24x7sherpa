from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from sherpa.config import Settings, get_settings
from sherpa.providers.base import Bar, PriceProvider

logger = logging.getLogger(__name__)


def normalize_yfinance_history(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns (yfinance) and normalize OHLCV capitalisation."""
    if df is None or df.empty:
        return df
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = pd.Index([str(x) for x in df.columns.get_level_values(0)])
    canon = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    rename = {c: canon[str(c).lower()] for c in df.columns if str(c).lower() in canon}
    if rename:
        df = df.rename(columns=rename)
    return df


class YFinancePriceProvider:
    """Free-tier delayed data via Yahoo; fine for research, not for HFT."""

    def history_daily(self, symbol: str, *, days: int = 120) -> list[Bar]:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{max(days, 5)}d", auto_adjust=False)
        df = normalize_yfinance_history(df)
        if df is None or df.empty:
            logger.warning("No price history for %s", symbol)
            return []
        need = ("Open", "High", "Low", "Close", "Volume")
        if not all(c in df.columns for c in need):
            logger.warning("Unexpected Yahoo columns for %s: %s", symbol, list(df.columns))
            return []
        out: list[Bar] = []
        for idx, row in df.tail(days).iterrows():
            ts = idx.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            try:
                out.append(
                    Bar(
                        ts=ts,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row["Volume"]) if pd.notna(row["Volume"]) else 0.0,
                    )
                )
            except (TypeError, ValueError) as e:
                logger.warning("Bad bar row for %s at %s: %s", symbol, idx, e)
                continue
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
