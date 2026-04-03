from __future__ import annotations

import pandas as pd

from sherpa.recommendations.daily import _score_candidate


def test_score_bullish_alignment() -> None:
    n = 30
    rows: list[dict] = []
    base = 100.0
    for i in range(n):
        c = base + i * 0.25
        rows.append(
            {
                "close": c,
                "volume": 1e6 * (1.6 if i == n - 1 else 1.0),
                "sma_5": c - 0.2,
                "sma_10": c - 0.4,
                "sma_20": c - 0.8,
                "sma_50": c - 1.5,
                "sma_200": c - 3.0,
                "rsi_14": 48.0,
                "atr_pct": 0.016,
                "atr_14": 1.5,
            }
        )
    df = pd.DataFrame(rows)
    c = float(df.iloc[-1]["close"])
    df.loc[df.index[-1], "sma_10"] = c - 0.9
    df.loc[df.index[-1], "sma_5"] = c - 0.2
    sc, reasons = _score_candidate(df, [])
    assert sc >= 25
    assert any("SMA(5)" in r or "momentum" in r or "SMA(10)" in r for r in reasons)
