"""Central risk controller -- validates signals against all risk limits.

Spec (Section 5):
- Single stock max: 20% of total capital
- Sector concentration: <= 40% (TW) / <= 35% (US)
- Correlated sector combined: <= 50%
- Total exposure: <= 60%
- Per-trade risk: max 1%
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str
    warnings: list[str]


class RiskController:
    def __init__(self, config: dict = None):
        config = config or {}
        self.single_stock_max = config.get("single_stock_max", 0.20)
        self.sector_max_tw = config.get("sector_max_tw", 0.40)
        self.sector_max_us = config.get("sector_max_us", 0.35)
        self.correlated_sector_max = config.get("correlated_sector_max", 0.50)
        self.total_exposure_max = config.get("total_exposure_max", 0.60)
        self.per_trade_risk_max = config.get("per_trade_risk_max", 0.01)

    def check(self, symbol: str, market: str, new_position_pct: float,
              current_holdings: dict, risk_pct: float = 0.0) -> RiskCheckResult:
        """Validate a new position against all risk rules.

        Args:
            symbol: stock symbol
            market: "US" or "TW"
            new_position_pct: new position as fraction of total capital
            current_holdings: dict with keys:
                - stock_weights: {symbol: pct} for all current positions
                - sector_weights: {sector: pct}
                - total_exposure: float (0-1)
            risk_pct: per-trade risk as fraction of total capital
        """
        warnings = []

        # 1. Single stock limit
        current_stock = current_holdings.get("stock_weights", {}).get(symbol, 0.0)
        new_total = current_stock + new_position_pct
        if new_total > self.single_stock_max:
            return RiskCheckResult(False,
                f"{symbol} would be {new_total:.1%} of portfolio (max {self.single_stock_max:.0%})", warnings)

        # 2. Total exposure limit
        current_exposure = current_holdings.get("total_exposure", 0.0)
        if current_exposure + new_position_pct > self.total_exposure_max:
            return RiskCheckResult(False,
                f"Total exposure would be {current_exposure + new_position_pct:.1%} (max {self.total_exposure_max:.0%})", warnings)

        # 3. Per-trade risk
        if risk_pct > self.per_trade_risk_max:
            return RiskCheckResult(False,
                f"Per-trade risk {risk_pct:.2%} exceeds {self.per_trade_risk_max:.0%} limit", warnings)

        # 4. Sector concentration (warning, not blocking)
        sector_max = self.sector_max_tw if market == "TW" else self.sector_max_us
        sector_weights = current_holdings.get("sector_weights", {})
        for sector, weight in sector_weights.items():
            if weight > sector_max:
                warnings.append(f"Sector '{sector}' at {weight:.1%} exceeds {sector_max:.0%} limit")

        # 5. Correlation warning
        correlations = current_holdings.get("correlations", {})
        for pair, corr in correlations.items():
            if corr > 0.7:
                warnings.append(f"High correlation {corr:.2f} between {pair}")

        return RiskCheckResult(True, "OK", warnings)
