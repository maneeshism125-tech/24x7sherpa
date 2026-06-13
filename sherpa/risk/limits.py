from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct_nav: float
    max_daily_loss_pct: float


@dataclass(frozen=True)
class RiskManager:
    limits: RiskLimits
    nav: float
    daily_pnl: float

    def allow_new_risk(self) -> bool:
        if self.nav <= 0:
            return False
        loss_floor = -abs(self.limits.max_daily_loss_pct) * self.nav
        if self.daily_pnl < loss_floor:
            return False
        return True

    def max_notional_per_position(self) -> float:
        return max(0.0, self.limits.max_position_pct_nav * self.nav)


def sizing_shares(*, price: float, max_notional: float) -> int:
    if price <= 0 or max_notional <= 0:
        return 0
    return int(max_notional // price)
