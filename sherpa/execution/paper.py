from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sherpa.config import Settings, get_settings
from sherpa.execution.base import AccountSummary, OrderRequest, OrderResult, OrderSide
from sherpa.execution.simulation_paths import (
    legacy_paper_portfolio_path,
    simulation_portfolio_path,
)

logger = logging.getLogger(__name__)


@dataclass
class PaperBroker:
    """
    Paper portfolio with JSON persistence per simulation profile under data/simulations/<profile>/.
    Migrates legacy data/paper_portfolio.json into the default profile on first load.
    """

    settings: Settings = field(default_factory=get_settings)
    cash: float = 100_000.0
    positions: dict[str, int] = field(default_factory=dict)
    _last_prices: dict[str, float] = field(default_factory=dict)
    _meta: dict = field(default_factory=dict)
    _state_path: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = simulation_portfolio_path(self.settings)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        if self._state_path.exists():
            self._load_from_path(self._state_path)
        else:
            legacy = legacy_paper_portfolio_path(self.settings)
            if (
                self.settings.simulation_profile.strip().lower() == "default"
                and legacy.exists()
            ):
                self._load_from_path(legacy)
                self._save()
            else:
                self._meta = {"starting_cash": self.cash, "schema_version": 1}
                self._save()

    def _load_from_path(self, path: Path) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.cash = float(raw.get("cash", self.cash))
        self.positions = {
            str(k).upper(): int(v) for k, v in raw.get("positions", {}).items()
        }
        self._last_prices = {
            str(k).upper(): float(v) for k, v in raw.get("last_prices", {}).items()
        }
        self._meta = dict(raw.get("meta") or {})
        if "starting_cash" not in self._meta:
            self._meta["starting_cash"] = self.cash

    def _save(self) -> None:
        payload = {
            "cash": self.cash,
            "positions": self.positions,
            "last_prices": self._last_prices,
            "meta": self._meta,
        }
        self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def set_last_price(self, symbol: str, price: float) -> None:
        self._last_prices[symbol.upper()] = price
        self._save()

    def _slip(self, price: float, side: OrderSide) -> float:
        bps = self.settings.default_slippage_bps / 10_000.0
        if side == OrderSide.BUY:
            return price * (1 + bps)
        return price * (1 - bps)

    def get_account(self) -> AccountSummary:
        equity = self.cash + sum(
            self._last_prices.get(s, 0.0) * q for s, q in self.positions.items()
        )
        return AccountSummary(equity=equity, cash=self.cash, buying_power=self.cash)

    def submit_market_order(self, req: OrderRequest) -> OrderResult:
        sym = req.symbol.upper()
        px = self._last_prices.get(sym)
        if px is None or px <= 0:
            raise ValueError(f"Set last price for {sym} before paper order (use set_last_price).")
        fill = self._slip(px, req.side)
        oid = str(uuid.uuid4())
        qty = req.qty
        if qty <= 0:
            raise ValueError("qty must be positive")

        pos = self.positions.get(sym, 0)
        if req.side == OrderSide.BUY:
            cost = fill * qty
            if cost > self.cash + 1e-6:
                raise ValueError("Insufficient paper cash.")
            self.cash -= cost
            self.positions[sym] = pos + qty
        else:
            if pos < qty:
                raise ValueError("Insufficient shares to sell (paper).")
            self.cash += fill * qty
            self.positions[sym] = pos - qty
            if self.positions[sym] == 0:
                del self.positions[sym]

        logger.info("Paper fill %s %s %s @ %.4f", sym, req.side.value, qty, fill)
        self._last_prices[sym] = fill
        self._save()
        return OrderResult(
            broker_order_id=oid,
            status="filled",
            filled_qty=qty,
            avg_fill_price=fill,
        )
