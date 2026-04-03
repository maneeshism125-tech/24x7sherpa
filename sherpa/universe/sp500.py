from __future__ import annotations

import io
import logging
from pathlib import Path

import httpx
import pandas as pd

from sherpa.config import get_settings

logger = logging.getLogger(__name__)

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _cache_path() -> Path:
    d = get_settings().data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d / "sp500_tickers.txt"


def refresh_sp500_cache() -> list[str]:
    """Fetch S&P 500 symbols from Wikipedia and write cache."""
    headers = {
        "User-Agent": "SherpaTrader/1.0 (https://github.com/; educational research)",
        "Accept": "text/html,application/xhtml+xml",
    }
    with httpx.Client(timeout=45.0, headers=headers, follow_redirects=True) as client:
        r = client.get(WIKI_URL)
        r.raise_for_status()
        html = r.text
    tables = pd.read_html(io.StringIO(html))
    table = next(t for t in tables if "Symbol" in t.columns)
    tickers = table["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
    path = _cache_path()
    path.write_text("\n".join(tickers), encoding="utf-8")
    logger.info("Cached %d S&P 500 tickers to %s", len(tickers), path)
    return tickers


def get_sp500_tickers(*, use_cache: bool = True) -> list[str]:
    """
    Return S&P 500 ticker symbols. Uses data/sp500_tickers.txt when present;
    otherwise downloads from Wikipedia (requires network).
    """
    path = _cache_path()
    if use_cache and path.exists():
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            return lines
    return refresh_sp500_cache()
