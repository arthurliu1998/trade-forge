"""Realistic transaction cost model.

Spec (Section 9.1):
- Commission: 0.1425% (TW broker fee)
- Transaction tax: 0.3% on sell (TW), 0.15% for ETF, 0.1% for day trade
- Slippage: 0.3% (conservative)
- Market impact: 0.1%
- Round-trip total: ~0.85%
"""
from dataclasses import dataclass


@dataclass
class CostModel:
    commission: float = 0.001425  # 0.1425%
    tax_sell_tw: float = 0.003    # 0.3%
    tax_sell_us: float = 0.0     # no sell tax in US
    slippage: float = 0.003      # 0.3%
    market_impact: float = 0.001  # 0.1%

    def entry_cost(self, market: str) -> float:
        """Cost as fraction of trade value on entry."""
        return self.commission + self.slippage + self.market_impact

    def exit_cost(self, market: str) -> float:
        """Cost as fraction of trade value on exit."""
        tax = self.tax_sell_tw if market == "TW" else self.tax_sell_us
        return self.commission + tax + self.slippage + self.market_impact

    def round_trip(self, market: str) -> float:
        """Total round-trip cost as fraction."""
        return self.entry_cost(market) + self.exit_cost(market)

    def apply_entry(self, price: float, market: str) -> float:
        """Effective entry price after costs (higher than market)."""
        return price * (1 + self.entry_cost(market))

    def apply_exit(self, price: float, market: str) -> float:
        """Effective exit price after costs (lower than market)."""
        return price * (1 - self.exit_cost(market))
