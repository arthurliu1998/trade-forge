import pandas as pd
import numpy as np
from quantforge.scanner import QuantScanner
from quantforge.core.models import Regime, QuantSignal


def _make_ohlcv(n=80, trend="up"):
    if trend == "up":
        prices = [100 + i * 0.5 + np.random.normal(0, 0.1) for i in range(n)]
    else:
        prices = [100 - i * 0.3 + np.random.normal(0, 0.1) for i in range(n)]
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": prices, "High": [p+1 for p in prices],
        "Low": [p-1 for p in prices], "Close": prices,
        "Volume": [1000000 + np.random.randint(-100000, 100000) for _ in range(n)],
    }, index=dates)


def test_tw_full_pipeline():
    scanner = QuantScanner()
    signal = scanner.score_stock(
        symbol="2330", market="TW", ohlcv=_make_ohlcv(80, "up"),
        chipflow_data={"foreign_net_consecutive_days": 4, "trust_same_direction": True,
                       "foreign_net_volume_ratio": 0.12, "margin_change_pct": -3.0,
                       "short_change_pct": 0.0},
        crossmarket_data={"sox_return": 1.5, "adr_spread": 0.01},
        sentiment_data={"finbert_sentiment": 0.3},
        vix=15.0,
    )
    assert isinstance(signal, QuantSignal)
    assert signal.symbol == "2330"
    assert signal.market == "TW"
    assert 0 <= signal.quant_score <= 100


def test_us_full_pipeline():
    scanner = QuantScanner()
    signal = scanner.score_stock(
        symbol="AAPL", market="US", ohlcv=_make_ohlcv(80, "up"),
        crossmarket_data={"sox_return": 0.5},
        sentiment_data={"finbert_sentiment": 0.1},
        vix=18.0,
    )
    assert signal.market == "US"
    assert signal.edge_scores.chipflow is None


def test_empty_data():
    scanner = QuantScanner()
    signal = scanner.score_stock(symbol="XXX", market="US", ohlcv=pd.DataFrame(), vix=15.0)
    assert signal.signal_level == "NO_SIGNAL"
