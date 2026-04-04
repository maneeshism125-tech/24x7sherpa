from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sherpa.config import Settings
from sherpa.execution.simulation_paths import simulation_portfolio_path


def reset_paper_simulation(settings: Settings, *, starting_cash: float) -> Path:
    """Clear positions and set fake cash for learning / sandbox trading."""
    path = simulation_portfolio_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cash": float(starting_cash),
        "positions": {},
        "last_prices": {},
        "open_orders": [],
        "meta": {
            "starting_cash": float(starting_cash),
            "schema_version": 2,
            "reset_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def read_paper_simulation_state(settings: Settings) -> dict:
    path = simulation_portfolio_path(settings)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
