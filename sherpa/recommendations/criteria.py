"""Tunable parameters for daily pick ranking (filters + scoring bands)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from sherpa.universe.indices import normalize_universe_id


@dataclass(frozen=True)
class PickCriteria:
    universe_id: str = "sp500"
    universe_cap: int = 150
    pick_count: int = 10
    skip_news: bool = False
    min_bars: int = 200
    min_volume: float = 200_000.0
    require_above_sma200: bool = True
    rsi_band_low: float = 38.0
    rsi_band_high: float = 65.0
    rsi_overbought: float = 70.0
    volume_surge_ratio: float = 1.35
    atr_elevated_pct: float = 0.015
    news_penalty: float = 45.0
    sell_atr_multiplier: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PickCriteria:
        base = cls()
        keys = {f.name for f in fields(cls)}
        merged = base.to_dict()
        for k, v in data.items():
            if k in keys and v is not None:
                merged[k] = v
        merged["universe_id"] = normalize_universe_id(
            str(merged["universe_id"]) if merged.get("universe_id") is not None else None
        )
        return cls(**merged)
