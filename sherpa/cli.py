from __future__ import annotations

import importlib.util
import logging
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import typer
import yfinance as yf

from sherpa.cli_settings import resolve_settings
from sherpa.config import get_settings
from sherpa.execution.base import OrderRequest, OrderSide
from sherpa.execution.factory import create_broker
from sherpa.execution.simulation import read_paper_simulation_state, reset_paper_simulation
from sherpa.execution.simulation_paths import simulation_portfolio_path, simulation_profile_slug
from sherpa.providers import create_news_provider, create_price_provider
from sherpa.recommendations.criteria import PickCriteria
from sherpa.recommendations.daily import run_daily_picks
from sherpa.signals.engine import Side, SignalEngine
from sherpa.technical.indicators import compute_features
from sherpa.universe.indices import normalize_universe_id, refresh_universe_cache
from sherpa.universe.sp500 import get_sp500_tickers

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True, add_completion=False)
simulate_app = typer.Typer(no_args_is_help=True, add_completion=False)
app.add_typer(simulate_app, name="simulate", help="Fake-money sandbox (per-profile portfolios).")


@app.command("universe-refresh")
def universe_refresh(
    universe: str = typer.Option(
        "sp500",
        "--universe",
        "-u",
        help="sp500 | dow | nasdaq100 | nasdaq | russell2000",
    ),
) -> None:
    """Download ticker list for a universe into the server data directory (cache)."""
    uid = normalize_universe_id(universe)
    n = refresh_universe_cache(uid)
    typer.echo(f"Cached {n} tickers for universe={uid}.")


@app.command("scan")
def scan(
    top: int = typer.Option(25, help="Max symbols to scan (cost control)."),
    skip_news: bool = typer.Option(False, help="Skip news fetch (faster)."),
) -> None:
    """Load prices + optional news, print rule-based signals for first N S&P 500 names."""
    settings = get_settings()
    prices = create_price_provider(settings)
    news_p = create_news_provider(settings)
    engine = SignalEngine()
    tickers = get_sp500_tickers()[:top]
    rows: list[str] = []
    for sym in tickers:
        bars = prices.history_daily(sym, days=120)
        feats = compute_features(bars)
        news = [] if skip_news else news_p.headlines_for_symbol(sym, limit=8)
        sig = engine.evaluate(sym, feats, news)
        if sig.side == Side.FLAT:
            continue
        rows.append(
            f"{sym:6} {sig.side.value:5} score={sig.score:.2f}  "
            + "; ".join(sig.reasons)
        )
    if not rows:
        typer.echo("No signals (or all flat). Try larger universe or different day.")
        return
    typer.echo("\n".join(rows))


@app.command("daily-picks")
def daily_picks(
    universe_cap: int = typer.Option(
        150,
        "--universe-cap",
        "-n",
        help="How many symbols to score from the chosen list (time/cost).",
    ),
    picks: int = typer.Option(10, help="How many top names to print."),
    universe_id: str = typer.Option(
        "sp500",
        "--universe",
        "-u",
        help="sp500 | dow | nasdaq100 | nasdaq | russell2000",
    ),
    skip_news: bool = typer.Option(False, help="Skip headlines (faster)."),
    min_volume: float = typer.Option(
        200_000,
        help="Minimum last-session volume (shares).",
    ),
) -> None:
    """Rank names from a US index list; SMA/RSI/ATR + headline rules — not advice."""
    settings = get_settings()
    uid = normalize_universe_id(universe_id)
    cr = PickCriteria(
        universe_id=uid,
        universe_cap=universe_cap,
        pick_count=picks,
        skip_news=skip_news,
        min_volume=min_volume,
    )
    out, disc, scored = run_daily_picks(settings, criteria=cr)
    typer.echo(disc)
    filt = "close>SMA200, " if cr.require_above_sma200 else ""
    typer.echo(
        f"Scored {scored} symbols ({filt}vol>{min_volume:,.0f}) from first {universe_cap} of {uid}.\n"
    )
    for i, p in enumerate(out, 1):
        r = " · ".join(p.reasons[:6])
        tb = f"{p.target_buy_price:.2f}" if p.target_buy_price is not None else "—"
        ts = f"{p.target_sell_price:.2f}" if p.target_sell_price is not None else "—"
        typer.echo(
            f"{i:2}. {p.symbol:6}  score={p.score:.1f}  buy~{tb}  sell~{ts}  | {r}"
        )


@app.command("trade")
def trade(
    symbol: str = typer.Argument(..., help="Ticker, e.g. AAPL"),
    side: str = typer.Argument(..., help="buy or sell"),
    qty: int = typer.Argument(..., help="Whole shares"),
    broker: str = typer.Option(
        "paper",
        help="paper (local sim) or alpaca (needs API keys, paper URL by default)",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Paper simulation profile (sandbox file); overrides SIMULATION_PROFILE env.",
    ),
) -> None:
    """Place a market order (paper simulation or Alpaca)."""
    settings = resolve_settings(profile=profile)
    sym = symbol.upper()
    oside = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    if oside == OrderSide.SELL and side.lower() != "sell":
        typer.echo("side must be buy or sell", err=True)
        raise typer.Exit(code=1)

    br = create_broker(broker, settings)

    if broker.strip().lower() == "paper":
        from sherpa.execution.paper import PaperBroker

        if not isinstance(br, PaperBroker):
            raise RuntimeError("expected paper broker")
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="5d")
        if hist is None or hist.empty:
            typer.echo(f"No price for {sym}", err=True)
            raise typer.Exit(code=1)
        last = float(hist["Close"].iloc[-1])
        br.set_last_price(sym, last)

    req = OrderRequest(symbol=sym, qty=qty, side=oside)
    try:
        res = br.submit_market_order(req)
    except Exception as e:
        logger.exception("Order failed")
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from e
    typer.echo(
        f"status={res.status} id={res.broker_order_id} "
        f"filled={res.filled_qty} avg={res.avg_fill_price}"
    )


@app.command("account")
def account(
    broker: str = typer.Option("paper", help="paper or alpaca"),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Paper simulation profile; overrides SIMULATION_PROFILE env.",
    ),
) -> None:
    """Show account summary from broker."""
    settings = resolve_settings(profile=profile)
    br = create_broker(broker, settings)
    a = br.get_account()
    typer.echo(f"equity={a.equity:.2f} cash={a.cash:.2f} buying_power={a.buying_power:.2f}")


@simulate_app.command("reset")
def simulate_reset(
    cash: float = typer.Option(
        100_000.0,
        "--cash",
        "-c",
        help="Starting fake cash after reset.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Named sandbox (separate portfolio file). Default from SIMULATION_PROFILE or 'default'.",
    ),
) -> None:
    """Reset a simulation profile to all cash, no positions."""
    settings = resolve_settings(profile=profile)
    path = reset_paper_simulation(settings, starting_cash=cash)
    slug = simulation_profile_slug(settings.simulation_profile)
    typer.echo(f"Reset simulation profile={slug!r} starting_cash={cash:.2f} -> {path}")


@simulate_app.command("status")
def simulate_status(
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Named sandbox; overrides SIMULATION_PROFILE env.",
    ),
) -> None:
    """Show sandbox cash, positions, and P&L vs starting cash for a profile."""
    settings = resolve_settings(profile=profile)
    slug = simulation_profile_slug(settings.simulation_profile)
    raw = read_paper_simulation_state(settings)
    if not raw:
        typer.echo(
            f"Profile {slug!r} has no saved state yet. Run: sherpa simulate reset --profile {slug}"
        )
        return
    cash = float(raw.get("cash", 0))
    positions: dict[str, int] = {
        str(k).upper(): int(v) for k, v in raw.get("positions", {}).items()
    }
    last_prices = {str(k).upper(): float(v) for k, v in raw.get("last_prices", {}).items()}
    meta = raw.get("meta") or {}
    start = float(meta.get("starting_cash", cash))
    mkt = sum(last_prices.get(s, 0.0) * q for s, q in positions.items())
    equity = cash + mkt
    pnl = equity - start
    typer.echo(f"profile={slug!r} path={simulation_portfolio_path(settings)}")
    typer.echo(f"starting_cash={start:.2f} equity={equity:.2f} cash={cash:.2f} pnl={pnl:+.2f}")
    if positions:
        typer.echo("positions:")
        for sym, q in sorted(positions.items()):
            px = last_prices.get(sym, 0.0)
            typer.echo(f"  {sym} qty={q} last={px:.4f} mkt={px * q:.2f}")
    else:
        typer.echo("positions: (none)")
    if meta.get("reset_at"):
        typer.echo(f"last_reset={meta['reset_at']}")


@app.command("doctor")
def cmd_doctor() -> None:
    """Check Python API + web UI setup and whether port 8000 responds."""
    repo = Path(__file__).resolve().parent.parent
    typer.echo(f"Repo: {repo}")
    typer.echo(f"  Python: {sys.executable}")

    has_fastapi = importlib.util.find_spec("fastapi") is not None
    typer.echo(f"  fastapi installed: {has_fastapi}")
    if not has_fastapi:
        typer.echo('    Fix: pip install -e ".[web]"')

    uvicorn = repo / ".venv" / "bin" / "uvicorn"
    if sys.platform == "win32":
        uvicorn = repo / ".venv" / "Scripts" / "uvicorn.exe"
    typer.echo(f"  uvicorn in venv: {uvicorn.is_file()}")
    if not uvicorn.is_file():
        typer.echo('    Fix: python3 -m venv .venv && pip install -e ".[web]"')

    nm = repo / "web" / "node_modules"
    typer.echo(f"  web/node_modules: {nm.is_dir()}")
    if not nm.is_dir():
        typer.echo("    Fix: npm run install-web")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    port_ok = sock.connect_ex(("127.0.0.1", 8000)) == 0
    sock.close()
    typer.echo(f"  port 8000 open: {port_ok}")
    if not port_ok:
        typer.echo("    Fix: in repo root, run: source .venv/bin/activate && sherpa-web")
    else:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as resp:
                body = resp.read(200).decode()
                typer.echo(f"  /api/health: {body}")
        except (urllib.error.URLError, OSError) as e:
            typer.echo(f"  /api/health failed: {e}")

    typer.echo("")
    typer.echo("One terminal — API + UI:")
    typer.echo("  npm run dev")
    typer.echo("Then open http://127.0.0.1:5173")


if __name__ == "__main__":
    app()
