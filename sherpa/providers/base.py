from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class NewsItem:
    published_at: datetime
    title: str
    source: str
    url: str | None = None
    summary: str | None = None


class PriceProvider(Protocol):
    def history_daily(self, symbol: str, *, days: int = 120) -> list[Bar]: ...


class NewsProvider(Protocol):
    def headlines_for_symbol(self, symbol: str, *, limit: int = 15) -> list[NewsItem]: ...
