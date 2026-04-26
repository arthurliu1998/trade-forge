import pandas as pd
import numpy as np
from quantforge.backtest.cost_model import CostModel
from quantforge.backtest.analytics import compute_metrics, BacktestMetrics
from quantforge.backtest.validation import WalkForwardValidator, MonteCarloAnalyzer
from quantforge.backtest.engine import BacktestEngine


# --- Cost Model Tests ---
def test_cost_model_tw_round_trip():
    cm = CostModel()
    rt = cm.round_trip("TW")
    assert 0.01 < rt < 0.015  # ~1.385% (commission + slippage + impact both ways, + sell tax)


def test_cost_model_us_no_sell_tax():
    cm = CostModel()
    assert cm.exit_cost("US") < cm.exit_cost("TW")


def test_apply_entry_increases_price():
    cm = CostModel()
    assert cm.apply_entry(100, "TW") > 100


def test_apply_exit_decreases_price():
    cm = CostModel()
    assert cm.apply_exit(100, "TW") < 100


# --- Analytics Tests ---
def test_metrics_winning_trades():
    returns = [2.0, -1.0, 3.0, -0.5, 1.5, 2.0, -1.0, 1.0] * 5
    m = compute_metrics(returns, trading_days=200)
    assert m.total_trades == 40
    assert m.win_rate > 50
    assert m.sharpe_ratio > 0
    assert m.max_drawdown_pct >= 0
    assert m.profit_factor > 1


def test_metrics_empty():
    m = compute_metrics([], 0)
    assert m.total_trades == 0
    assert m.verdict == "INSUFFICIENT"


def test_metrics_with_benchmark():
    returns = [1.0] * 50
    m = compute_metrics(returns, 252, benchmark_return=5.0)
    assert m.alpha_vs_benchmark is not None


def test_verdict_valid():
    returns = [2.0, -1.0, 1.5, 2.0, -0.5] * 10  # 50 trades, good performance
    m = compute_metrics(returns, 252)
    assert m.total_trades == 50
    assert m.verdict in ("VALID", "MARGINAL")


# --- Walk-Forward Tests ---
def test_walk_forward_profitable():
    returns = [1.0, -0.5, 2.0, -0.3, 1.5, 0.8] * 20  # 120 trades, mostly profitable
    wf = WalkForwardValidator()
    result = wf.validate(returns, window_size=30)
    assert result["total_windows"] > 0
    assert "verdict" in result


def test_walk_forward_insufficient():
    wf = WalkForwardValidator()
    result = wf.validate([1.0, 2.0], window_size=10)
    assert result["verdict"] == "INSUFFICIENT_DATA"


# --- Monte Carlo Tests ---
def test_monte_carlo():
    np.random.seed(42)
    returns = [2.0, -1.0, 3.0, -0.5, 1.5] * 10
    mc = MonteCarloAnalyzer(n_simulations=100)
    result = mc.analyze(returns)
    assert result["simulations"] == 100
    assert result["worst_drawdown"] >= result["median_drawdown"]
    assert result["p95_drawdown"] >= result["median_drawdown"]


def test_monte_carlo_empty():
    mc = MonteCarloAnalyzer()
    result = mc.analyze([])
    assert result["simulations"] == 0


# --- Engine Tests ---
def _make_trending_df(n=200):
    prices = [100 + i * 0.3 + np.random.normal(0, 1) for i in range(n)]
    return pd.DataFrame({
        "Open": prices,
        "High": [p + np.random.uniform(0.5, 2) for p in prices],
        "Low": [p - np.random.uniform(0.5, 2) for p in prices],
        "Close": [p + np.random.normal(0, 0.5) for p in prices],
        "Volume": [1000000] * n,
    })


def test_engine_basic():
    engine = BacktestEngine(market="US")
    df = _make_trending_df(200)
    signals = [{"index": i, "direction": "long", "score": 75} for i in range(20, 180, 10)]
    result = engine.run(df, signals)
    assert isinstance(result, BacktestMetrics)
    assert result.total_trades > 0


def test_engine_empty():
    engine = BacktestEngine()
    result = engine.run(pd.DataFrame(), [])
    assert result.total_trades == 0


def test_engine_with_costs():
    engine = BacktestEngine(market="TW")
    df = _make_trending_df(200)
    signals = [{"index": 50, "direction": "long", "score": 80}]
    result = engine.run(df, signals)
    assert result.total_trades == 1
