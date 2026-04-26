"""Alpha decay monitor — tracks factor performance over time.

Spec (Section 10.1):
- Monthly re-backtest each factor using recent 3 months data
- Win rate decline < 5%: no action
- Win rate decline 5-10%: warning, reduce weight 20%
- Win rate decline > 10%: pause factor
- Strategy alpha < 0 for 3 consecutive months: stop strategy
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FactorHealth:
    name: str
    baseline_win_rate: float
    current_win_rate: float
    decay_rate: float  # as fraction (0.05 = 5% decline)
    status: str  # "healthy", "warning", "paused"
    weight_adjustment: float  # multiplier (1.0 = no change, 0.8 = -20%)

    @property
    def recommendation(self) -> str:
        if self.decay_rate < 0.05:
            return "No action needed"
        if self.decay_rate < 0.10:
            return f"Reduce weight by 20% (decay {self.decay_rate:.1%})"
        return f"Pause factor (decay {self.decay_rate:.1%})"


@dataclass
class AlphaReport:
    factor_health: list[FactorHealth]
    strategy_alpha: float  # vs benchmark
    consecutive_negative_months: int
    strategy_status: str  # "active", "warning", "stopped"
    recommended_weight_adjustments: dict  # {factor_name: multiplier}


class AlphaDecayMonitor:
    def __init__(self):
        self._baselines: dict[str, float] = {}  # factor -> baseline win rate
        self._monthly_alphas: list[float] = []

    def set_baseline(self, factor_name: str, win_rate: float):
        self._baselines[factor_name] = win_rate

    def record_monthly_alpha(self, alpha: float):
        self._monthly_alphas.append(alpha)

    def evaluate_factor(self, factor_name: str, current_win_rate: float) -> FactorHealth:
        baseline = self._baselines.get(factor_name, current_win_rate)
        if baseline <= 0:
            decay = 0.0
        else:
            decay = max(0, (baseline - current_win_rate) / baseline)

        if decay < 0.05:
            status, adj = "healthy", 1.0
        elif decay < 0.10:
            status, adj = "warning", 0.8
        else:
            status, adj = "paused", 0.0

        return FactorHealth(
            name=factor_name, baseline_win_rate=baseline,
            current_win_rate=current_win_rate, decay_rate=round(decay, 4),
            status=status, weight_adjustment=adj,
        )

    def generate_report(self, factor_win_rates: dict[str, float],
                        strategy_alpha: float) -> AlphaReport:
        self.record_monthly_alpha(strategy_alpha)

        factors = []
        adjustments = {}
        for name, wr in factor_win_rates.items():
            fh = self.evaluate_factor(name, wr)
            factors.append(fh)
            if fh.weight_adjustment != 1.0:
                adjustments[name] = fh.weight_adjustment

        neg_months = 0
        for a in reversed(self._monthly_alphas):
            if a < 0:
                neg_months += 1
            else:
                break

        if neg_months >= 3:
            strat_status = "stopped"
        elif neg_months >= 2:
            strat_status = "warning"
        else:
            strat_status = "active"

        return AlphaReport(
            factor_health=factors, strategy_alpha=strategy_alpha,
            consecutive_negative_months=neg_months,
            strategy_status=strat_status,
            recommended_weight_adjustments=adjustments,
        )
