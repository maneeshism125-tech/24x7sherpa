from __future__ import annotations

import logging
from typing import Any

import httpx

from sherpa.config import Settings, get_settings
from sherpa.execution.base import AccountSummary, OrderRequest, OrderResult, OrderSide

logger = logging.getLogger(__name__)


class AlpacaBroker:
    """
    Alpaca Trading API (paper or live). Free paper account: https://alpaca.markets
    Set ALPACA_API_KEY and ALPACA_SECRET_KEY; default base is paper-api.
    """

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            raise ValueError("Alpaca requires ALPACA_API_KEY and ALPACA_SECRET_KEY in environment.")
        self._client = client or httpx.Client(
            base_url=self.settings.alpaca_base_url.rstrip("/"),
            timeout=30.0,
            headers={
                "APCA-API-KEY-ID": self.settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
            },
        )

    def _get(self, path: str) -> dict[str, Any]:
        r = self._client.get(path)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post(path, json=body)
        r.raise_for_status()
        return r.json()

    def get_account(self) -> AccountSummary:
        data = self._get("/v2/account")
        return AccountSummary(
            equity=float(data.get("equity", 0)),
            cash=float(data.get("cash", 0)),
            buying_power=float(data.get("buying_power", 0)),
        )

    def submit_market_order(self, req: OrderRequest) -> OrderResult:
        body = {
            "symbol": req.symbol.upper(),
            "qty": str(req.qty),
            "side": req.side.value,
            "type": "market",
            "time_in_force": "day",
        }
        data = self._post("/v2/orders", body)
        oid = str(data.get("id", ""))
        filled = data.get("filled_qty")
        filled_qty = int(filled) if filled not in (None, "") else 0
        avg = data.get("filled_avg_price")
        avg_fill = float(avg) if avg not in (None, "") else None
        status = str(data.get("status", "unknown"))
        logger.info("Alpaca order %s %s status=%s", oid, req.symbol, status)
        return OrderResult(
            broker_order_id=oid,
            status=status,
            filled_qty=filled_qty,
            avg_fill_price=avg_fill,
        )
