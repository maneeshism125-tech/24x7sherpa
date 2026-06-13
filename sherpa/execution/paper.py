from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sherpa.config import Settings, get_settings
from sherpa.execution.base import AccountSummary, OrderRequest, OrderResult, OrderSide
from sherpa.execution.simulation_paths import (
    legacy_paper_portfolio_path,
    simulation_portfolio_path,
)

logger = logging.getLogger(__name__)

OrderTypeName = Literal["market", "limit", "stop", "stop_limit"]


@dataclass
class PaperBroker:
    """
    Paper portfolio with JSON persistence per simulation profile under data/simulations/<profile>/.
    Supports market, limit, stop (stop-market), and stop-limit working orders evaluated on last price.
    """

    settings: Settings = field(default_factory=get_settings)
    cash: float = 100_000.0
    positions: dict[str, int] = field(default_factory=dict)
    _last_prices: dict[str, float] = field(default_factory=dict)
    open_orders: list[dict[str, Any]] = field(default_factory=list)
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
                self._meta = {"starting_cash": self.cash, "schema_version": 2}
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
        self.open_orders = list(raw.get("open_orders") or [])
        self._meta = dict(raw.get("meta") or {})
        if "starting_cash" not in self._meta:
            self._meta["starting_cash"] = self.cash
        self._meta.setdefault("schema_version", 2)

    def _save(self) -> None:
        payload = {
            "cash": self.cash,
            "positions": self.positions,
            "last_prices": self._last_prices,
            "open_orders": self.open_orders,
            "meta": self._meta,
        }
        self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def set_last_price(self, symbol: str, price: float) -> None:
        sym = symbol.upper()
        if price <= 0:
            raise ValueError("Price must be positive")
        self._last_prices[sym] = price
        self._process_open_orders(sym)
        self._save()

    def list_open_orders(self) -> list[dict[str, Any]]:
        return [dict(o) for o in self.open_orders if o.get("status") == "open"]

    def cancel_order(self, order_id: str) -> bool:
        oid = order_id.strip()
        for o in self.open_orders:
            if o.get("id") == oid and o.get("status") == "open":
                o["status"] = "cancelled"
                self._save()
                return True
        return False

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

    def _fill_market(
        self, sym: str, side: OrderSide, qty: int, *, update_last_to_fill: bool
    ) -> OrderResult:
        sym = sym.upper()
        px = self._last_prices.get(sym)
        if px is None or px <= 0:
            raise ValueError(f"Set last price for {sym} before paper order (use set_last_price).")
        fill = self._slip(px, side)
        oid = str(uuid.uuid4())
        if qty <= 0:
            raise ValueError("qty must be positive")
        pos = self.positions.get(sym, 0)
        if side == OrderSide.BUY:
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
        logger.info("Paper market fill %s %s %s @ %.4f", sym, side.value, qty, fill)
        if update_last_to_fill:
            self._last_prices[sym] = fill
        self._save()
        return OrderResult(
            broker_order_id=oid,
            status="filled",
            filled_qty=qty,
            avg_fill_price=fill,
        )

    def submit_market_order(self, req: OrderRequest) -> OrderResult:
        return self._fill_market(req.symbol, req.side, req.qty, update_last_to_fill=True)

    def submit_paper_order(
        self,
        *,
        symbol: str,
        side: OrderSide,
        qty: int,
        order_type: OrderTypeName,
        limit_price: float | None,
        stop_price: float | None,
    ) -> OrderResult:
        sym = symbol.upper()
        ot = order_type.lower().strip()
        if ot == "market":
            return self.submit_market_order(OrderRequest(symbol=sym, qty=qty, side=side))
        if ot == "limit":
            if limit_price is None or limit_price <= 0:
                raise ValueError("limit_price is required and must be > 0 for limit orders")
            if side == OrderSide.BUY:
                need = limit_price * qty
                if self.cash + 1e-6 < need:
                    raise ValueError("Insufficient paper cash for this limit buy (at limit price).")
            else:
                if self.positions.get(sym, 0) < qty:
                    raise ValueError("Insufficient shares for this limit sell.")
            return self._queue_order(
                sym, side, qty, "limit", limit_price=limit_price, stop_price=None
            )
        if ot == "stop":
            if stop_price is None or stop_price <= 0:
                raise ValueError("stop_price is required and must be > 0 for stop orders")
            if side == OrderSide.SELL and self.positions.get(sym, 0) < qty:
                raise ValueError("Insufficient shares for this stop sell (stop-loss style).")
            return self._queue_order(
                sym, side, qty, "stop", limit_price=None, stop_price=stop_price
            )
        if ot == "stop_limit":
            if (
                stop_price is None
                or limit_price is None
                or stop_price <= 0
                or limit_price <= 0
            ):
                raise ValueError("stop_price and limit_price are required for stop-limit orders")
            if side == OrderSide.SELL and self.positions.get(sym, 0) < qty:
                raise ValueError("Insufficient shares for this stop-limit sell.")
            return self._queue_order(
                sym,
                side,
                qty,
                "stop_limit",
                limit_price=limit_price,
                stop_price=stop_price,
            )
        raise ValueError(f"Unknown order_type: {order_type}")

    def _queue_order(
        self,
        sym: str,
        side: OrderSide,
        qty: int,
        order_type: str,
        *,
        limit_price: float | None,
        stop_price: float | None,
    ) -> OrderResult:
        oid = str(uuid.uuid4())
        self.open_orders.append(
            {
                "id": oid,
                "symbol": sym,
                "side": side.value,
                "qty": int(qty),
                "order_type": order_type,
                "limit_price": limit_price,
                "stop_price": stop_price,
                "stop_triggered": False,
                "status": "open",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._save()
        px = self._last_prices.get(sym)
        if px is not None and px > 0:
            self._process_open_orders(sym)
        return OrderResult(
            broker_order_id=oid,
            status="accepted",
            filled_qty=0,
            avg_fill_price=None,
        )

    def _process_open_orders(self, sym: str) -> None:
        sym_u = sym.upper()
        for _ in range(100):
            last = self._last_prices.get(sym_u)
            if last is None or last <= 0:
                return
            filled_one = False
            next_orders: list[dict[str, Any]] = []
            for o in self.open_orders:
                if o.get("symbol") != sym_u or o.get("status") != "open":
                    next_orders.append(o)
                    continue
                action = self._evaluate_working_order(o, last)
                if action == "remove":
                    filled_one = True
                    continue
                next_orders.append(o)
                if action == "mutated":
                    filled_one = True
            self.open_orders = next_orders
            self._save()
            if not filled_one:
                return

    def _evaluate_working_order(self, o: dict[str, Any], last: float) -> str:
        """Return 'remove' (filled or error drop), 'mutated' (stop triggered), or 'noop'."""
        side = OrderSide.BUY if o["side"] == "buy" else OrderSide.SELL
        sym = o["symbol"]
        qty = int(o["qty"])
        ot = o["order_type"]

        if ot == "limit":
            lp = float(o["limit_price"])
            if side == OrderSide.BUY:
                if last <= lp:
                    fill = min(self._slip(last, side), lp)
                    cost = fill * qty
                    if cost > self.cash + 1e-6:
                        return "noop"
                    self.cash -= cost
                    self.positions[sym] = self.positions.get(sym, 0) + qty
                    logger.info("Paper limit buy fill %s %s @ %.4f", sym, qty, fill)
                    return "remove"
            else:
                if last >= lp:
                    fill = max(self._slip(last, side), lp)
                    if self.positions.get(sym, 0) < qty:
                        return "noop"
                    self.cash += fill * qty
                    self.positions[sym] = self.positions.get(sym, 0) - qty
                    if self.positions[sym] == 0:
                        del self.positions[sym]
                    logger.info("Paper limit sell fill %s %s @ %.4f", sym, qty, fill)
                    return "remove"
            return "noop"

        if ot == "stop":
            sp = float(o["stop_price"])
            if side == OrderSide.SELL:
                if last <= sp:
                    self._fill_market(sym, side, qty, update_last_to_fill=False)
                    return "remove"
            else:
                if last >= sp:
                    self._fill_market(sym, side, qty, update_last_to_fill=False)
                    return "remove"
            return "noop"

        if ot == "stop_limit":
            sp = float(o["stop_price"])
            lp = float(o["limit_price"])
            if not o.get("stop_triggered"):
                if side == OrderSide.SELL:
                    if last <= sp:
                        o["stop_triggered"] = True
                        return "mutated"
                else:
                    if last >= sp:
                        o["stop_triggered"] = True
                        return "mutated"
                return "noop"
            if side == OrderSide.SELL:
                if last >= lp:
                    fill = max(self._slip(last, side), lp)
                    if self.positions.get(sym, 0) < qty:
                        return "noop"
                    self.cash += fill * qty
                    self.positions[sym] = self.positions.get(sym, 0) - qty
                    if self.positions[sym] == 0:
                        del self.positions[sym]
                    logger.info("Paper stop-limit sell fill %s %s @ %.4f", sym, qty, fill)
                    return "remove"
            else:
                if last <= lp:
                    fill = min(self._slip(last, side), lp)
                    cost = fill * qty
                    if cost > self.cash + 1e-6:
                        return "noop"
                    self.cash -= cost
                    self.positions[sym] = self.positions.get(sym, 0) + qty
                    logger.info("Paper stop-limit buy fill %s %s @ %.4f", sym, qty, fill)
                    return "remove"
            return "noop"

        return "noop"

    def refresh_symbol_from_last(self, symbol: str, last: float) -> None:
        """Update quote and attempt to fill working orders (does not change holdings itself)."""
        self.set_last_price(symbol, last)
