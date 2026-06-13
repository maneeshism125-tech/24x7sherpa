from __future__ import annotations

import re
from pathlib import Path

from sherpa.config import Settings


def simulation_profile_slug(profile: str) -> str:
    raw = (profile or "default").strip() or "default"
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw).strip("_")[:64] or "default"
    return safe


def simulation_portfolio_path(settings: Settings) -> Path:
    slug = simulation_profile_slug(settings.simulation_profile)
    return settings.data_dir / "simulations" / slug / "portfolio.json"


def legacy_paper_portfolio_path(settings: Settings) -> Path:
    return settings.data_dir / "paper_portfolio.json"
