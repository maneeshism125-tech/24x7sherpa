from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    qty: int
    side: OrderSide


@dataclass(frozen=True)
class OrderResult:
    broker_order_id: str
    status: str
    filled_qty: int
    avg_fill_price: float | None


@dataclass(frozen=True)
class AccountSummary:
    equity: float
    cash: float
    buying_power: float


class BrokerClient(Protocol):
    def get_account(self) -> AccountSummary: ...

    def submit_market_order(self, req: OrderRequest) -> OrderResult: ...
