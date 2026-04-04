from __future__ import annotations

import logging

import yfinance as yf

from sherpa.cli_settings import resolve_settings
from sherpa.execution.base import OrderSide
from sherpa.execution.factory import create_broker
from sherpa.execution.paper import PaperBroker
from sherpa.execution.simulation import read_paper_simulation_state, reset_paper_simulation
from sherpa.execution.simulation_paths import simulation_portfolio_path, simulation_profile_slug
from sherpa.providers import create_news_provider, create_price_provider
from sherpa.signals.engine import Side, SignalEngine
from sherpa.technical.indicators import compute_features
from sherpa.universe.indices import refresh_universe_cache
from sherpa.universe.sp500 import get_sp500_tickers

from api.schemas import (
    AccountResponse,
    DailyPickRow,
    DailyRecommendationsResponse,
    OpenOrderRow,
    PaperTickBody,
    PickCriteriaBody,
    PositionRow,
    ScanResponse,
    SignalRow,
    SimulationStatusResponse,
    TradeBody,
    TradeResponse,
)

logger = logging.getLogger(__name__)


def service_universe_refresh(*, universe: str = "sp500") -> dict:
    from sherpa.universe.indices import normalize_universe_id

    uid = normalize_universe_id(universe)
    n = refresh_universe_cache(uid)
    return {"universe": uid, "tickers_cached": n}


def service_scan(*, top: int, skip_news: bool) -> ScanResponse:
    from sherpa.config import get_settings

    settings = get_settings()
    prices = create_price_provider(settings)
    news_p = create_news_provider(settings)
    engine = SignalEngine()
    tickers = get_sp500_tickers()[:top]
    rows: list[SignalRow] = []
    for sym in tickers:
        bars = prices.history_daily(sym, days=120)
        feats = compute_features(bars)
        news = [] if skip_news else news_p.headlines_for_symbol(sym, limit=8)
        sig = engine.evaluate(sym, feats, news)
        if sig.side == Side.FLAT:
            continue
        rows.append(
            SignalRow(
                symbol=sym,
                side=sig.side.value,
                score=float(sig.score),
                reasons=list(sig.reasons),
            )
        )
    return ScanResponse(signals=rows, scanned=len(tickers))


def service_simulate_reset(*, profile: str, cash: float) -> str:
    settings = resolve_settings(profile=profile)
    path = reset_paper_simulation(settings, starting_cash=cash)
    return str(path)


def service_simulation_status(*, profile: str) -> SimulationStatusResponse | None:
    settings = resolve_settings(profile=profile)
    slug = simulation_profile_slug(settings.simulation_profile)
    raw = read_paper_simulation_state(settings)
    if not raw:
        return None
    cash = float(raw.get("cash", 0))
    positions_map = {str(k).upper(): int(v) for k, v in raw.get("positions", {}).items()}
    last_prices = {str(k).upper(): float(v) for k, v in raw.get("last_prices", {}).items()}
    meta = raw.get("meta") or {}
    start = float(meta.get("starting_cash", cash))
    mkt = sum(last_prices.get(s, 0.0) * q for s, q in positions_map.items())
    equity = cash + mkt
    pnl = equity - start
    pos_rows = [
        PositionRow(
            symbol=s,
            qty=q,
            last=last_prices.get(s, 0.0),
            market_value=last_prices.get(s, 0.0) * q,
        )
        for s, q in sorted(positions_map.items())
    ]
    return SimulationStatusResponse(
        profile=slug,
        path=str(simulation_portfolio_path(settings)),
        starting_cash=start,
        equity=equity,
        cash=cash,
        pnl=pnl,
        positions=pos_rows,
        last_reset=meta.get("reset_at"),
    )


def service_account_paper(*, profile: str) -> AccountResponse:
    settings = resolve_settings(profile=profile)
    br = create_broker("paper", settings)
    if not isinstance(br, PaperBroker):
        raise RuntimeError("expected paper broker")
    a = br.get_account()
    return AccountResponse(
        equity=a.equity,
        cash=a.cash,
        buying_power=a.buying_power,
        profile=simulation_profile_slug(settings.simulation_profile),
    )


def service_trade_paper(body: TradeBody) -> TradeResponse:
    settings = resolve_settings(profile=(body.profile or "default").strip() or "default")
    sym = body.symbol.upper().strip()
    br = create_broker("paper", settings)
    if not isinstance(br, PaperBroker):
        raise RuntimeError("expected paper broker")
    ticker = yf.Ticker(sym)
    hist = ticker.history(period="5d")
    if hist is None or hist.empty:
        raise ValueError(f"No price data for {sym}")
    last = float(hist["Close"].iloc[-1])
    br.refresh_symbol_from_last(sym, last)
    oside = OrderSide.BUY if body.side == "buy" else OrderSide.SELL
    res = br.submit_paper_order(
        symbol=sym,
        side=oside,
        qty=body.qty,
        order_type=body.order_type,
        limit_price=body.limit_price,
        stop_price=body.stop_price,
    )
    detail = None
    if res.status == "accepted":
        detail = (
            "Order accepted and working. Refresh the quote on this symbol (or place another order) "
            "to pull the latest price and evaluate limit/stop fills."
        )
    return TradeResponse(
        status=res.status,
        broker_order_id=res.broker_order_id,
        filled_qty=res.filled_qty,
        avg_fill_price=res.avg_fill_price,
        symbol=sym,
        order_type=body.order_type,
        detail=detail,
    )


def service_paper_open_orders(*, profile: str) -> list[OpenOrderRow]:
    settings = resolve_settings(profile=profile)
    br = create_broker("paper", settings)
    if not isinstance(br, PaperBroker):
        raise RuntimeError("expected paper broker")
    out: list[OpenOrderRow] = []
    for o in br.list_open_orders():
        out.append(
            OpenOrderRow(
                id=o["id"],
                symbol=o["symbol"],
                side=o["side"],
                qty=int(o["qty"]),
                order_type=o["order_type"],
                limit_price=o.get("limit_price"),
                stop_price=o.get("stop_price"),
                stop_triggered=bool(o.get("stop_triggered", False)),
                status=o["status"],
                created_at=str(o.get("created_at", "")),
            )
        )
    return out


def service_paper_cancel_order(*, profile: str, order_id: str) -> None:
    settings = resolve_settings(profile=profile)
    br = create_broker("paper", settings)
    if not isinstance(br, PaperBroker):
        raise RuntimeError("expected paper broker")
    if not br.cancel_order(order_id):
        raise ValueError("Order not found or not cancellable (already filled or cancelled).")


def service_paper_tick(body: PaperTickBody) -> dict:
    settings = resolve_settings(profile=(body.profile or "default").strip() or "default")
    sym = body.symbol.upper().strip()
    br = create_broker("paper", settings)
    if not isinstance(br, PaperBroker):
        raise RuntimeError("expected paper broker")
    ticker = yf.Ticker(sym)
    hist = ticker.history(period="5d")
    if hist is None or hist.empty:
        raise ValueError(f"No price data for {sym}")
    last = float(hist["Close"].iloc[-1])
    br.refresh_symbol_from_last(sym, last)
    return {
        "ok": True,
        "symbol": sym,
        "last": last,
        "working_orders": len(br.list_open_orders()),
    }


def service_daily_recommendations(*, body: PickCriteriaBody | None = None) -> DailyRecommendationsResponse:
    from sherpa.config import get_settings
    from sherpa.recommendations.criteria import PickCriteria
    from sherpa.recommendations.daily import run_daily_picks

    overrides = body.model_dump(exclude_none=True) if body else {}
    cr = PickCriteria.from_dict(overrides)
    picks, disclaimer, scored = run_daily_picks(get_settings(), criteria=cr)
    rows = [
        DailyPickRow(
            symbol=p.symbol,
            score=p.score,
            reasons=list(p.reasons),
            last_close=p.last_close,
            sma5=p.sma5,
            sma10=p.sma10,
            sma200=p.sma200,
            rsi=p.rsi,
            atr_pct=p.atr_pct,
            volume_last=p.volume_last,
            target_buy_price=p.target_buy_price,
            target_sell_price=p.target_sell_price,
        )
        for p in picks
    ]
    return DailyRecommendationsResponse(
        picks=rows,
        disclaimer=disclaimer,
        universe_cap=cr.universe_cap,
        candidates_scored=scored,
        criteria=cr.to_dict(),
    )
