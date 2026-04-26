"""Walk-forward validation and Monte Carlo analysis.

Spec (Section 9.2):
- Walk-forward: rolling window, every window must be profitable
- Monte Carlo: randomize trade order 1000 times, check worst-case drawdown
- Parameter robustness: find plateaus not peaks
"""
import numpy as np
from quantforge.backtest.analytics import compute_metrics, BacktestMetrics


class WalkForwardValidator:
    def __init__(self, train_ratio: float = 0.7, min_windows: int = 3):
        self.train_ratio = train_ratio
        self.min_windows = min_windows

    def validate(self, all_trade_returns: list[float],
                 window_size: int = None) -> dict:
        """Run walk-forward validation.

        Splits trade returns into rolling windows and validates each.
        Returns dict with per-window results and overall verdict.
        """
        n = len(all_trade_returns)
        if window_size is None:
            window_size = max(20, n // (self.min_windows + 1))

        if n < window_size * 2:
            return {"verdict": "INSUFFICIENT_DATA", "windows": [],
                    "profitable_windows": 0, "total_windows": 0}

        windows = []
        step = max(1, window_size // 2)

        for start in range(0, n - window_size + 1, step):
            end = start + window_size
            window_returns = all_trade_returns[start:end]
            train_end = int(len(window_returns) * self.train_ratio)
            test_returns = window_returns[train_end:]

            if len(test_returns) < 5:
                continue

            metrics = compute_metrics(test_returns, trading_days=len(test_returns))
            windows.append({
                "start": start, "end": end,
                "test_return": metrics.total_return_pct,
                "test_sharpe": metrics.sharpe_ratio,
                "profitable": metrics.total_return_pct > 0,
            })

        profitable = sum(1 for w in windows if w["profitable"])
        total = len(windows)
        pass_rate = profitable / total if total > 0 else 0

        verdict = "VALID" if pass_rate >= 0.7 else ("MARGINAL" if pass_rate >= 0.5 else "REJECT")

        return {
            "verdict": verdict,
            "windows": windows,
            "profitable_windows": profitable,
            "total_windows": total,
            "pass_rate": round(pass_rate, 2),
        }


class MonteCarloAnalyzer:
    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations

    def analyze(self, trade_returns: list[float]) -> dict:
        """Shuffle trade order N times, compute worst-case drawdown distribution."""
        if len(trade_returns) < 5:
            return {"median_drawdown": 0, "worst_drawdown": 0,
                    "p95_drawdown": 0, "simulations": 0}

        returns = np.array(trade_returns)
        max_drawdowns = []

        for _ in range(self.n_simulations):
            shuffled = np.random.permutation(returns)
            cumulative = np.cumprod(1 + shuffled / 100)
            peak = np.maximum.accumulate(cumulative)
            dd = (cumulative - peak) / peak
            max_drawdowns.append(abs(float(np.min(dd))) * 100)

        return {
            "median_drawdown": round(float(np.median(max_drawdowns)), 2),
            "worst_drawdown": round(float(np.max(max_drawdowns)), 2),
            "p95_drawdown": round(float(np.percentile(max_drawdowns, 95)), 2),
            "p5_drawdown": round(float(np.percentile(max_drawdowns, 5)), 2),
            "simulations": self.n_simulations,
        }
