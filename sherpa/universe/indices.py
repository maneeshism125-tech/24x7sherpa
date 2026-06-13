"""
Load ticker lists for major US equity universes (Wikipedia, Nasdaq Trader, cached R2K).

Lists are point-in-time from public sources; not guaranteed to match index rebalances instantly.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

import httpx
import pandas as pd

from sherpa.config import get_settings
from sherpa.universe.sp500 import get_sp500_tickers, refresh_sp500_cache

logger = logging.getLogger(__name__)

HTTP_HEADERS = {
    "User-Agent": "SherpaTrader/1.0 (https://github.com/; educational research)",
    "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
}

UNIVERSE_SP500 = "sp500"
UNIVERSE_DOW = "dow"
UNIVERSE_NASDAQ100 = "nasdaq100"
UNIVERSE_NASDAQ = "nasdaq"
UNIVERSE_RUSSELL2000 = "russell2000"

UNIVERSE_IDS = frozenset(
    {
        UNIVERSE_SP500,
        UNIVERSE_DOW,
        UNIVERSE_NASDAQ100,
        UNIVERSE_NASDAQ,
        UNIVERSE_RUSSELL2000,
    }
)

WIKI_DOW = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
WIKI_NDX = "https://en.wikipedia.org/wiki/Nasdaq-100"
NASDAQ_LISTED_URL = "https://ftp.nasdaqtrader.com/dynamic/SymbolDirectory/nasdaqlisted.txt"
RUSSELL2000_LIST_URL = "https://stockanalysis.com/list/russell-2000-stocks/"


def _cache_path(name: str) -> Path:
    d = get_settings().data_dir
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _wiki_table_symbols(html: str, prefer_columns: tuple[str, ...]) -> list[str]:
    tables = pd.read_html(io.StringIO(html))
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        for want in prefer_columns:
            if want in t.columns:
                s = t[want].astype(str).str.strip()
                tickers = s.str.replace(".", "-", regex=False).tolist()
                out = [x for x in tickers if x and re.match(r"^[A-Z0-9.\-]+$", x.upper())]
                if out:
                    return [x.upper().replace(".", "-") for x in out]
        # fuzzy: column containing "symbol" or "ticker"
        for i, c in enumerate(cols):
            cl = c.lower()
            if "symbol" in cl or cl == "ticker":
                col = t.iloc[:, i]
                s = col.astype(str).str.strip()
                tickers = s.str.replace(".", "-", regex=False).tolist()
                out = [x for x in tickers if x and re.match(r"^[A-Z0-9.\-]+$", x.upper())]
                if out:
                    return [x.upper().replace(".", "-") for x in out]
    return []


def _fetch_wiki_symbols(url: str, *column_names: str) -> list[str]:
    with httpx.Client(timeout=45.0, headers=HTTP_HEADERS, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
    syms = _wiki_table_symbols(r.text, column_names)
    if not syms:
        raise RuntimeError(f"No symbol column found in Wikipedia tables for {url}")
    return syms


def get_dow_tickers(*, use_cache: bool = True) -> list[str]:
    path = _cache_path("dow_tickers.txt")
    if use_cache and path.exists():
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            return lines
    syms = _fetch_wiki_symbols(WIKI_DOW, "Symbol", "Ticker")
    path.write_text("\n".join(syms), encoding="utf-8")
    logger.info("Cached %d Dow tickers to %s", len(syms), path)
    return syms


def get_nasdaq100_tickers(*, use_cache: bool = True) -> list[str]:
    path = _cache_path("nasdaq100_tickers.txt")
    if use_cache and path.exists():
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            return lines
    syms = _fetch_wiki_symbols(WIKI_NDX, "Ticker", "Symbol")
    path.write_text("\n".join(syms), encoding="utf-8")
    logger.info("Cached %d Nasdaq-100 tickers to %s", len(syms), path)
    return syms


def get_nasdaq_listed_tickers(*, use_cache: bool = True) -> list[str]:
    """Nasdaq-listed common stocks from Nasdaq Trader symbol directory (excludes test issues, ETFs)."""
    path = _cache_path("nasdaq_listed_tickers.txt")
    if use_cache and path.exists():
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            return lines
    with httpx.Client(timeout=60.0, headers=HTTP_HEADERS, follow_redirects=True) as client:
        r = client.get(NASDAQ_LISTED_URL)
        r.raise_for_status()
    text = r.text
    syms: list[str] = []
    for line in text.splitlines():
        if "|" not in line or line.startswith("Symbol|"):
            continue
        parts = line.split("|")
        if len(parts) < 8:
            continue
        sym, _name, _cat, test_issue, _fin, _lot, etf, *_rest = parts[:8]
        sym = sym.strip().upper()
        if test_issue.strip() != "N":
            continue
        if etf.strip() == "Y":
            continue
        if not sym or "$" in sym or len(sym) > 8:
            continue
        syms.append(sym.replace(".", "-"))
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for s in syms:
        if s not in seen:
            seen.add(s)
            out.append(s)
    path.write_text("\n".join(out), encoding="utf-8")
    logger.info("Cached %d Nasdaq-listed tickers to %s", len(out), path)
    return out


def refresh_russell2000_cache() -> list[str]:
    """Fetch Russell ~2000 list from stockanalysis.com and cache (may break if site layout changes)."""
    with httpx.Client(timeout=60.0, headers=HTTP_HEADERS, follow_redirects=True) as client:
        r = client.get(RUSSELL2000_LIST_URL)
        r.raise_for_status()
    tables = pd.read_html(io.StringIO(r.text))
    syms: list[str] = []
    for t in tables:
        cols_lower = [str(c).lower() for c in t.columns]
        for i, cl in enumerate(cols_lower):
            if "symbol" in cl or cl == "ticker":
                col = t.iloc[:, i]
                for x in col.astype(str).str.strip().tolist():
                    xu = x.upper().replace(".", "-")
                    if xu and re.match(r"^[A-Z0-9\-]{1,8}$", xu) and xu not in ("SYMBOL", "TICKER"):
                        syms.append(xu)
                break
    seen: set[str] = set()
    out: list[str] = []
    for s in syms:
        if s not in seen:
            seen.add(s)
            out.append(s)
    if len(out) < 500:
        raise RuntimeError(
            f"Russell 2000 parse looks wrong ({len(out)} symbols). "
            "The source page layout may have changed."
        )
    path = _cache_path("russell2000_tickers.txt")
    path.write_text("\n".join(out), encoding="utf-8")
    logger.info("Cached %d Russell 2000 tickers to %s", len(out), path)
    return out


def get_russell2000_tickers(*, use_cache: bool = True) -> list[str]:
    path = _cache_path("russell2000_tickers.txt")
    if use_cache and path.exists():
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            return lines
    return refresh_russell2000_cache()


def normalize_universe_id(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return UNIVERSE_SP500
    s = str(raw).strip().lower().replace("-", "").replace("_", "")
    aliases = {
        "sp500": UNIVERSE_SP500,
        "sandp500": UNIVERSE_SP500,
        "dow": UNIVERSE_DOW,
        "djia": UNIVERSE_DOW,
        "dia": UNIVERSE_DOW,
        "qqq": UNIVERSE_NASDAQ100,
        "nasdaq100": UNIVERSE_NASDAQ100,
        "ndx": UNIVERSE_NASDAQ100,
        "nasdaq": UNIVERSE_NASDAQ,
        "russell2000": UNIVERSE_RUSSELL2000,
        "rut": UNIVERSE_RUSSELL2000,
        "iwm": UNIVERSE_RUSSELL2000,
    }
    if s in aliases:
        return aliases[s]
    if s in UNIVERSE_IDS:
        return s
    logger.warning("Unknown universe_id %r, using sp500", raw)
    return UNIVERSE_SP500


def get_universe_tickers(universe_id: str, *, use_cache: bool = True) -> list[str]:
    uid = normalize_universe_id(universe_id)
    if uid == UNIVERSE_SP500:
        return get_sp500_tickers(use_cache=use_cache)
    if uid == UNIVERSE_DOW:
        return get_dow_tickers(use_cache=use_cache)
    if uid == UNIVERSE_NASDAQ100:
        return get_nasdaq100_tickers(use_cache=use_cache)
    if uid == UNIVERSE_NASDAQ:
        return get_nasdaq_listed_tickers(use_cache=use_cache)
    if uid == UNIVERSE_RUSSELL2000:
        return get_russell2000_tickers(use_cache=use_cache)
    return get_sp500_tickers(use_cache=use_cache)


def refresh_universe_cache(universe_id: str) -> int:
    """Re-download list for one universe; returns ticker count."""
    uid = normalize_universe_id(universe_id)
    if uid == UNIVERSE_SP500:
        return len(refresh_sp500_cache())
    if uid == UNIVERSE_DOW:
        return len(get_dow_tickers(use_cache=False))
    if uid == UNIVERSE_NASDAQ100:
        return len(get_nasdaq100_tickers(use_cache=False))
    if uid == UNIVERSE_NASDAQ:
        return len(get_nasdaq_listed_tickers(use_cache=False))
    if uid == UNIVERSE_RUSSELL2000:
        return len(refresh_russell2000_cache())
    return len(refresh_sp500_cache())
