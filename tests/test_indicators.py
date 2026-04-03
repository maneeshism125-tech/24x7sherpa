from datetime import datetime, timedelta, timezone

import pandas as pd

from sherpa.providers.base import Bar
from sherpa.technical.indicators import compute_features


def _bars_uptrend(n: int = 60) -> list[Bar]:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    out: list[Bar] = []
    price = 100.0
    for i in range(n):
        ts = base + timedelta(days=i)
        o = price
        c = price + 0.5
        h = c + 0.2
        l = o - 0.1
        out.append(Bar(ts=ts, open=o, high=h, low=l, close=c, volume=1e6))
        price = c
    return out


def test_compute_features_has_columns() -> None:
    bars = _bars_uptrend(60)
    df = compute_features(bars)
    assert not df.empty
    assert "sma_20" in df.columns
    assert "rsi_14" in df.columns
    last = df.iloc[-1]
    assert not pd.isna(last["sma_20"])
