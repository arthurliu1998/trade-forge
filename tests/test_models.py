from quantforge.core.models import Regime, FactorScore, EdgeScores, QuantSignal


def test_regime_enum():
    assert Regime.BULL_TREND.value == "bull_trend"
    assert Regime.CRISIS.value == "crisis"


def test_factor_score_clamp():
    fs = FactorScore(name="tech", raw=1.5, normalized=1.5, weight=0.35)
    assert fs.clamped == 1.0
    fs2 = FactorScore(name="tech", raw=-0.5, normalized=-0.5, weight=0.35)
    assert fs2.clamped == 0.0


def test_edge_scores_quant_score():
    scores = EdgeScores(
        technical=FactorScore("tech", 0.75, 0.75, 0.35),
        chipflow=FactorScore("chip", 0.70, 0.70, 0.30),
        crossmarket=FactorScore("cross", 0.80, 0.80, 0.15),
        sentiment=FactorScore("sent", 0.67, 0.67, 0.20),
    )
    expected = (0.75 * 0.35 + 0.70 * 0.30 + 0.80 * 0.15 + 0.67 * 0.20) * 100
    assert abs(scores.quant_score - expected) < 0.01


def test_edge_scores_us_no_chipflow():
    scores = EdgeScores(
        technical=FactorScore("tech", 0.75, 0.75, 0.45),
        chipflow=None,
        crossmarket=FactorScore("cross", 0.80, 0.80, 0.20),
        sentiment=FactorScore("sent", 0.67, 0.67, 0.35),
    )
    expected = (0.75 * 0.45 + 0.80 * 0.20 + 0.67 * 0.35) * 100
    assert abs(scores.quant_score - expected) < 0.01


def test_quant_signal_levels():
    def make(qs, ab=0.0, bt=70.0):
        return QuantSignal("X", "US", qs, ab, Regime.BULL_TREND, None, "", bt)

    assert make(82).signal_level == "STRONG_BUY"
    assert make(74).signal_level == "BUY"
    assert make(65, 8).signal_level == "ADVISOR_ASSISTED_BUY"
    assert make(65, 0).signal_level == "WATCHLIST"
    assert make(55, 10).signal_level == "NO_SIGNAL"
    assert make(25).signal_level == "STRONG_SELL"
    assert make(35).signal_level == "WATCH_SELL"


def test_quant_signal_bear_threshold():
    sig = QuantSignal("X", "TW", 75.0, 0, Regime.BEAR_TREND, None, "", buy_threshold=85.0)
    assert sig.signal_level == "WATCHLIST"  # 75 < 85 threshold


def test_position_multiplier():
    def make(qs, ab=0.0):
        return QuantSignal("X", "US", qs, ab, Regime.BULL_TREND, None, "")
    assert make(82).position_multiplier == 1.0
    assert make(74).position_multiplier == 0.7
    assert make(64, 8).position_multiplier == 0.5
    assert make(50).position_multiplier == 0.0
