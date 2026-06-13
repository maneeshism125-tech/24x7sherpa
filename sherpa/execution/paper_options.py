"""Paper options positions (long/short) stored alongside equity sandbox cash."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, Literal

from sherpa.execution.base import OrderResult
from sherpa.options.market_data import fetch_option_mid_price

if TYPE_CHECKING:
    from sherpa.execution.paper import PaperBroker

logger = logging.getLogger(__name__)

CONTRACT_MULTIPLIER = 100
OptionType = Literal["call", "put"]
OptionsAction = Literal["buy_to_open", "sell_to_open", "sell_to_close", "buy_to_close"]


def option_position_key(
    underlying: str, expiry: str, strike: float, option_type: OptionType
) -> str:
    return f"{underlying.upper()}|{expiry}|{strike:.2f}|{option_type.lower()}"


def parse_position_key(key: str) -> dict[str, Any]:
    parts = key.split("|")
    if len(parts) != 4:
        raise ValueError(f"Invalid option position key: {key}")
    return {
        "underlying": parts[0],
        "expiry": parts[1],
        "strike": float(parts[2]),
        "option_type": parts[3],
    }


def options_equity(broker: PaperBroker) -> float:
    total = 0.0
    for key, pos in broker.option_positions.items():
        mark = broker.option_last_prices.get(key, pos.get("avg_premium", 0.0))
        signed = int(pos["contracts"])
        if signed > 0:
            total += mark * CONTRACT_MULTIPLIER * signed
        else:
            total -= mark * CONTRACT_MULTIPLIER * abs(signed)
    return total


def list_option_positions(broker: PaperBroker) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, pos in sorted(broker.option_positions.items()):
        signed = int(pos["contracts"])
        if signed == 0:
            continue
        mark = broker.option_last_prices.get(key, float(pos.get("avg_premium", 0.0)))
        avg = float(pos["avg_premium"])
        abs_c = abs(signed)
        if signed > 0:
            mkt = mark * CONTRACT_MULTIPLIER * abs_c
            pnl = (mark - avg) * CONTRACT_MULTIPLIER * abs_c
        else:
            mkt = -(mark * CONTRACT_MULTIPLIER * abs_c)
            pnl = (avg - mark) * CONTRACT_MULTIPLIER * abs_c
        rows.append(
            {
                "position_key": key,
                "underlying": pos["underlying"],
                "expiry": pos["expiry"],
                "strike": float(pos["strike"]),
                "option_type": pos["option_type"],
                "contracts": signed,
                "avg_premium": avg,
                "mark": mark,
                "market_value": mkt,
                "unrealized_pnl": pnl,
            }
        )
    return rows


def set_option_mark(
    broker: PaperBroker,
    *,
    underlying: str,
    expiry: str,
    strike: float,
    option_type: OptionType,
    mark: float,
) -> None:
    if mark <= 0:
        raise ValueError("Option mark must be positive")
    key = option_position_key(underlying, expiry, strike, option_type)
    broker.option_last_prices[key] = mark
    broker._save()


def refresh_option_mark_from_chain(
    broker: PaperBroker,
    *,
    underlying: str,
    expiry: str,
    strike: float,
    option_type: OptionType,
) -> float:
    mark = fetch_option_mid_price(underlying, expiry, strike, option_type)
    set_option_mark(
        broker,
        underlying=underlying,
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        mark=mark,
    )
    return mark


def refresh_all_option_marks(broker: PaperBroker) -> int:
    updated = 0
    for key, pos in list(broker.option_positions.items()):
        if int(pos.get("contracts", 0)) == 0:
            continue
        refresh_option_mark_from_chain(
            broker,
            underlying=str(pos["underlying"]),
            expiry=str(pos["expiry"]),
            strike=float(pos["strike"]),
            option_type=str(pos["option_type"]),  # type: ignore[arg-type]
        )
        updated += 1
    return updated


def submit_options_trade(
    broker: PaperBroker,
    *,
    underlying: str,
    expiry: str,
    strike: float,
    option_type: OptionType,
    action: OptionsAction,
    contracts: int,
    premium: float | None = None,
) -> OrderResult:
    sym = underlying.upper()
    if contracts <= 0:
        raise ValueError("contracts must be positive")
    if premium is None:
        premium = fetch_option_mid_price(sym, expiry, strike, option_type)
    fill = broker._slip_option_premium(premium, action)
    key = option_position_key(sym, expiry, strike, option_type)
    pos = broker.option_positions.get(key)

    if action in ("sell_to_close", "buy_to_close"):
        if not pos or int(pos["contracts"]) == 0:
            raise ValueError("No open option position to close")
        current = int(pos["contracts"])
        if action == "sell_to_close":
            if current <= 0:
                raise ValueError("Cannot sell to close — position is not long")
            if contracts > current:
                raise ValueError("Close quantity exceeds long contracts")
            cash_delta = fill * CONTRACT_MULTIPLIER * contracts
            broker.cash += cash_delta
            new_qty = current - contracts
        else:
            if current >= 0:
                raise ValueError("Cannot buy to close — position is not short")
            if contracts > abs(current):
                raise ValueError("Close quantity exceeds short contracts")
            cash_delta = fill * CONTRACT_MULTIPLIER * contracts
            broker.cash -= cash_delta
            new_qty = current + contracts
        if new_qty == 0:
            broker.option_positions.pop(key, None)
            broker.option_last_prices.pop(key, None)
        else:
            pos["contracts"] = new_qty
        logger.info("Paper options close %s %s x%d @ %.4f", key, action, contracts, fill)
    elif action in ("buy_to_open", "sell_to_open"):
        if pos:
            current = int(pos["contracts"])
            if action == "buy_to_open" and current < 0:
                raise ValueError("Buy to open conflicts with an existing short — close it first")
            if action == "sell_to_open" and current > 0:
                raise ValueError("Sell to open conflicts with an existing long — close it first")
        notional = fill * CONTRACT_MULTIPLIER * contracts
        if action == "buy_to_open":
            if notional > broker.cash + 1e-6:
                raise ValueError("Insufficient paper cash for option debit")
            broker.cash -= notional
            delta = contracts
        else:
            broker.cash += notional
            delta = -contracts
        if pos:
            old_qty = int(pos["contracts"])
            old_avg = float(pos["avg_premium"])
            new_qty = old_qty + delta
            total_abs = abs(old_qty) + abs(delta)
            pos["avg_premium"] = (old_avg * abs(old_qty) + fill * abs(delta)) / total_abs
            pos["contracts"] = new_qty
        else:
            broker.option_positions[key] = {
                "underlying": sym,
                "expiry": expiry,
                "strike": float(strike),
                "option_type": option_type,
                "contracts": delta,
                "avg_premium": fill,
            }
        broker.option_last_prices[key] = fill
        logger.info("Paper options open %s %s x%d @ %.4f", key, action, contracts, fill)
    else:
        raise ValueError(f"Unknown options action: {action}")

    broker._save()
    return OrderResult(
        broker_order_id=str(uuid.uuid4()),
        status="filled",
        filled_qty=contracts,
        avg_fill_price=fill,
    )


def recommendation_to_action(
    recommendation: str, option_type: OptionType
) -> OptionsAction:
    rec = recommendation.upper()
    if rec == "BUY_CALL":
        if option_type != "call":
            raise ValueError("BUY_CALL requires a call option")
        return "buy_to_open"
    if rec == "BUY_PUT":
        if option_type != "put":
            raise ValueError("BUY_PUT requires a put option")
        return "buy_to_open"
    if rec == "SELL_PREMIUM":
        return "sell_to_open"
    raise ValueError("NEUTRAL recommendations cannot be paper traded")
