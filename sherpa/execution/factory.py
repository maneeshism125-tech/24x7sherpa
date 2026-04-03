from __future__ import annotations

from sherpa.config import Settings, get_settings
from sherpa.execution.base import BrokerClient
from sherpa.execution.brokers.alpaca import AlpacaBroker
from sherpa.execution.paper import PaperBroker


def create_broker(kind: str, settings: Settings | None = None) -> BrokerClient:
    s = settings or get_settings()
    k = kind.strip().lower()
    if k == "alpaca":
        return AlpacaBroker(settings=s)
    if k == "paper":
        return PaperBroker(settings=s)
    raise ValueError(f"Unknown broker {kind!r}; use 'paper' or 'alpaca'.")
