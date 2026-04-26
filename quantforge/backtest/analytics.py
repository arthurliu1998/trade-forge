"""Backtest performance analytics.

Computes Sharpe, max drawdown, win rate, profit factor, alpha vs benchmark.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class BacktestMetrics:
    total_trades: int
    win_rate: float          # 0-100
    avg_return_pct: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    profit_factor: float     # gross_profit / gross_loss
    avg_win_pct: float
    avg_loss_pct: float
    alpha_vs_benchmark: Optional[float]  # vs SPY or 0050
    trading_days: int

    @property
    def verdict(self) -> str:
        if self.total_trades < 30:
            return "INSUFFICIENT"
        if self.sharpe_ratio < 0.5 or self.win_rate < 40:
            return "REJECT"
        if self.sharpe_ratio < 1.0 or self.win_rate < 50:
            return "MARGINAL"
        return "VALID"


def compute_metrics(trade_returns: list[float], trading_days: int = 252,
                    benchmark_return: float = None) -> BacktestMetrics:
    """Compute backtest metrics from list of per-trade return percentages."""
    if not trade_returns:
        return BacktestMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, None, 0)

    returns = np.array(trade_returns)
    wins = returns[returns > 0]
    losses = returns[returns < 0]

    total_return = np.prod(1 + returns / 100) - 1
    ann_return = (1 + total_return) ** (252 / max(trading_days, 1)) - 1

    # Sharpe (annualized, assume risk-free = 0)
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(min(len(returns), 252))
    else:
        sharpe = 0.0

    # Max drawdown from cumulative returns
    cumulative = np.cumprod(1 + returns / 100)
    peak = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - peak) / peak
    max_dd = abs(float(np.min(drawdowns))) * 100 if len(drawdowns) > 0 else 0

    # Profit factor
    gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0
    gross_loss = abs(float(np.sum(losses))) if len(losses) > 0 else 1
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    alpha = None
    if benchmark_return is not None:
        alpha = round((total_return - benchmark_return / 100) * 100, 2)

    return BacktestMetrics(
        total_trades=len(returns),
        win_rate=round(len(wins) / len(returns) * 100, 1),
        avg_return_pct=round(float(np.mean(returns)), 2),
        total_return_pct=round(total_return * 100, 2),
        annualized_return_pct=round(ann_return * 100, 2),
        sharpe_ratio=round(sharpe, 2),
        max_drawdown_pct=round(max_dd, 2),
        profit_factor=round(pf, 2),
        avg_win_pct=round(float(np.mean(wins)), 2) if len(wins) > 0 else 0,
        avg_loss_pct=round(float(np.mean(losses)), 2) if len(losses) > 0 else 0,
        alpha_vs_benchmark=alpha,
        trading_days=trading_days,
    )
