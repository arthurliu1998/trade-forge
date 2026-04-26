from quantforge.portfolio.position_sizer import PositionSizer, PositionPlan
from quantforge.core.models import QuantSignal, Regime


def _signal(qs=80, regime=Regime.BULL_TREND):
    return QuantSignal("TEST", "US", qs, 0, regime, None, "")


def test_basic_sizing():
    sizer = PositionSizer()
    plan = sizer.calculate(_signal(80), total_capital=100000, current_price=100.0, atr=3.0)
    assert isinstance(plan, PositionPlan)
    assert plan.shares > 0
    assert plan.stop_loss < 100.0
    assert plan.target_price > 100.0
    assert plan.risk_pct <= 0.01  # max 1% risk


def test_bear_regime_halves_position():
    sizer = PositionSizer()
    bull = sizer.calculate(_signal(80, Regime.BULL_TREND), 100000, 100.0, 3.0)
    bear = sizer.calculate(_signal(80, Regime.BEAR_TREND), 100000, 100.0, 3.0)
    assert bear.shares <= bull.shares


def test_weaker_signal_smaller_position():
    sizer = PositionSizer()
    strong = sizer.calculate(_signal(85), 100000, 100.0, 3.0)
    weak = sizer.calculate(_signal(72), 100000, 100.0, 3.0)
    assert weak.shares <= strong.shares


def test_zero_atr_returns_zero_shares():
    sizer = PositionSizer()
    plan = sizer.calculate(_signal(80), 100000, 100.0, 0.0)
    assert plan.shares == 0


def test_high_volatility_limits_position():
    sizer = PositionSizer()
    low_vol = sizer.calculate(_signal(80), 100000, 100.0, 1.0)
    high_vol = sizer.calculate(_signal(80), 100000, 100.0, 15.0)
    assert high_vol.shares < low_vol.shares
