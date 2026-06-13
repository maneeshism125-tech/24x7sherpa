from __future__ import annotations

import logging

import yfinance as yf

from sherpa.cli_settings import resolve_settings
from sherpa.execution.base import OrderSide
from sherpa.execution.factory import create_broker
from sherpa.execution.paper import PaperBroker
from sherpa.execution.paper_options import recommendation_to_action
from sherpa.execution.simulation import read_paper_simulation_state, reset_paper_simulation
from sherpa.execution.simulation_paths import simulation_portfolio_path, simulation_profile_slug
from sherpa.providers import create_news_provider, create_price_provider
from sherpa.providers.prices import normalize_yfinance_history
from sherpa.signals.engine import Side, SignalEngine
from sherpa.technical.indicators import compute_features
from sherpa.universe.indices import refresh_universe_cache
from sherpa.universe.sp500 import get_sp500_tickers

from api.schemas import (
    AccountResponse,
    DailyPickRow,
    DailyRecommendationsResponse,
    OpenOrderRow,
    OptionsPositionRow,
    OptionsPositionsResponse,
    OptionsTradeBody,
    OptionsTradeResponse,
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
    scanned = 0
    for sym in tickers:
        try:
            bars = prices.history_daily(sym, days=120)
            if not bars:
                continue
            feats = compute_features(bars)
            news = [] if skip_news else news_p.headlines_for_symbol(sym, limit=8)
            sig = engine.evaluate(sym, feats, news)
            scanned += 1
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
        except Exception:
            logger.exception("scan failed for symbol %s", sym)
    return ScanResponse(signals=rows, scanned=scanned)


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
    option_positions = raw.get("option_positions") or {}
    option_last_prices = {str(k): float(v) for k, v in (raw.get("option_last_prices") or {}).items()}
    meta = raw.get("meta") or {}
    start = float(meta.get("starting_cash", cash))
    stock_mkt = sum(last_prices.get(s, 0.0) * q for s, q in positions_map.items())
    opt_mkt = 0.0
    for key, pos in option_positions.items():
        signed = int(pos.get("contracts", 0))
        if signed == 0:
            continue
        mark = option_last_prices.get(key, float(pos.get("avg_premium", 0.0)))
        if signed > 0:
            opt_mkt += mark * 100 * signed
        else:
            opt_mkt -= mark * 100 * abs(signed)
    equity = cash + stock_mkt + opt_mkt
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
    hist = normalize_yfinance_history(ticker.history(period="5d"))
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
    hist = normalize_yfinance_history(ticker.history(period="5d"))
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


def _resolve_options_trade(body: OptionsTradeBody) -> tuple[str, str]:
    option_type = body.option_type
    if body.action is not None:
        return body.action, option_type
    rec = body.recommendation
    if rec is None:
        raise ValueError("Provide action or recommendation")
    if rec == "BUY_CALL":
        option_type = "call"
    elif rec == "BUY_PUT":
        option_type = "put"
    elif rec == "SELL_PREMIUM":
        option_type = "call"
    action = recommendation_to_action(rec, option_type)  # type: ignore[arg-type]
    return action, option_type


def service_trade_options_paper(body: OptionsTradeBody) -> OptionsTradeResponse:
    settings = resolve_settings(profile=(body.profile or "default").strip() or "default")
    br = create_broker("paper", settings)
    if not isinstance(br, PaperBroker):
        raise RuntimeError("expected paper broker")
    action, option_type = _resolve_options_trade(body)
    if not body.expiry or not body.strike:
        raise ValueError("expiry and strike are required")
    res = br.submit_options_paper_order(
        underlying=body.underlying.upper().strip(),
        expiry=body.expiry,
        strike=body.strike,
        option_type=option_type,  # type: ignore[arg-type]
        action=action,  # type: ignore[arg-type]
        contracts=body.contracts,
    )
    return OptionsTradeResponse(
        status=res.status,
        broker_order_id=res.broker_order_id,
        filled_contracts=res.filled_qty,
        avg_premium=float(res.avg_fill_price or 0),
        underlying=body.underlying.upper().strip(),
        expiry=body.expiry,
        strike=body.strike,
        option_type=option_type,
        action=action,
        detail="Paper options fill at chain mid ± slippage. Not real brokerage execution.",
    )


def service_options_paper_positions(*, profile: str) -> OptionsPositionsResponse:
    settings = resolve_settings(profile=profile)
    br = create_broker("paper", settings)
    if not isinstance(br, PaperBroker):
        raise RuntimeError("expected paper broker")
    acct = br.get_account()
    rows = [
        OptionsPositionRow(
            position_key=r["position_key"],
            underlying=r["underlying"],
            expiry=r["expiry"],
            strike=r["strike"],
            option_type=r["option_type"],
            contracts=r["contracts"],
            avg_premium=r["avg_premium"],
            mark=r["mark"],
            market_value=r["market_value"],
            unrealized_pnl=r["unrealized_pnl"],
        )
        for r in br.list_option_positions()
    ]
    return OptionsPositionsResponse(
        profile=simulation_profile_slug(settings.simulation_profile),
        cash=acct.cash,
        equity=acct.equity,
        positions=rows,
    )


def service_options_paper_refresh_marks(*, profile: str) -> dict:
    settings = resolve_settings(profile=profile)
    br = create_broker("paper", settings)
    if not isinstance(br, PaperBroker):
        raise RuntimeError("expected paper broker")
    n = br.refresh_option_marks()
    acct = br.get_account()
    return {
        "ok": True,
        "marks_updated": n,
        "equity": acct.equity,
        "cash": acct.cash,
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
