from __future__ import annotations

from sherpa.universe.indices import UNIVERSE_SP500, normalize_universe_id


def test_normalize_universe_aliases() -> None:
    assert normalize_universe_id("QQQ") == "nasdaq100"
    assert normalize_universe_id("dow") == "dow"
    assert normalize_universe_id("russell2000") == "russell2000"
    assert normalize_universe_id("nasdaq") == "nasdaq"
    assert normalize_universe_id(None) == UNIVERSE_SP500
    assert normalize_universe_id("not-a-real-universe") == UNIVERSE_SP500
