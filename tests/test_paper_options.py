from __future__ import annotations

import pytest

from sherpa.config import Settings
from sherpa.execution.paper import PaperBroker
from sherpa.execution.paper_options import list_option_positions, recommendation_to_action


@pytest.fixture
def paper_broker(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, simulation_profile="opt-test")
    monkeypatch.setattr(
        "sherpa.execution.paper_options.fetch_option_mid_price",
        lambda *args, **kwargs: 2.50,
    )
    return PaperBroker(settings=settings, cash=50_000.0)


def test_recommendation_to_action() -> None:
    assert recommendation_to_action("BUY_CALL", "call") == "buy_to_open"
    assert recommendation_to_action("BUY_PUT", "put") == "buy_to_open"
    assert recommendation_to_action("SELL_PREMIUM", "call") == "sell_to_open"


def test_buy_call_debits_cash(paper_broker: PaperBroker) -> None:
    start = paper_broker.cash
    res = paper_broker.submit_options_paper_order(
        underlying="AAPL",
        expiry="2026-07-18",
        strike=150.0,
        option_type="call",
        action="buy_to_open",
        contracts=2,
        premium=2.50,
    )
    assert res.status == "filled"
    assert res.filled_qty == 2
    fill = 2.50 * (1 + 5 / 10_000)  # default slippage bps
    assert paper_broker.cash == pytest.approx(start - fill * 100 * 2)
    rows = list_option_positions(paper_broker)
    assert len(rows) == 1
    assert rows[0]["contracts"] == 2
    assert rows[0]["underlying"] == "AAPL"


def test_sell_premium_credits_cash(paper_broker: PaperBroker) -> None:
    start = paper_broker.cash
    paper_broker.submit_options_paper_order(
        underlying="MSFT",
        expiry="2026-07-18",
        strike=400.0,
        option_type="call",
        action="sell_to_open",
        contracts=1,
        premium=5.00,
    )
    assert paper_broker.cash > start
    rows = list_option_positions(paper_broker)
    assert rows[0]["contracts"] == -1


def test_close_long_position(paper_broker: PaperBroker) -> None:
    paper_broker.submit_options_paper_order(
        underlying="AAPL",
        expiry="2026-07-18",
        strike=150.0,
        option_type="call",
        action="buy_to_open",
        contracts=1,
        premium=2.00,
    )
    paper_broker.submit_options_paper_order(
        underlying="AAPL",
        expiry="2026-07-18",
        strike=150.0,
        option_type="call",
        action="sell_to_close",
        contracts=1,
        premium=2.20,
    )
    assert list_option_positions(paper_broker) == []


def test_equity_includes_options(paper_broker: PaperBroker) -> None:
    paper_broker.submit_options_paper_order(
        underlying="AAPL",
        expiry="2026-07-18",
        strike=150.0,
        option_type="call",
        action="buy_to_open",
        contracts=1,
        premium=3.00,
    )
    acct = paper_broker.get_account()
    assert acct.equity > paper_broker.cash
