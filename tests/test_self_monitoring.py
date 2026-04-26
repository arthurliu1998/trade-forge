from quantforge.alpha.decay_monitor import AlphaDecayMonitor, FactorHealth, AlphaReport
from quantforge.alpha.advisor_tracker import AdvisorTracker, AdvisorReport
from quantforge.behavioral.tracker import BehavioralTracker, BehaviorEvent, BehaviorReport


# --- Alpha Decay Monitor ---
def test_factor_healthy():
    m = AlphaDecayMonitor()
    m.set_baseline("technical", 60.0)
    fh = m.evaluate_factor("technical", 58.0)
    assert fh.status == "healthy"
    assert fh.weight_adjustment == 1.0


def test_factor_warning():
    m = AlphaDecayMonitor()
    m.set_baseline("technical", 60.0)
    fh = m.evaluate_factor("technical", 55.0)  # ~8.3% decline
    assert fh.status == "warning"
    assert fh.weight_adjustment == 0.8


def test_factor_paused():
    m = AlphaDecayMonitor()
    m.set_baseline("chipflow", 65.0)
    fh = m.evaluate_factor("chipflow", 52.0)  # 20% decline
    assert fh.status == "paused"
    assert fh.weight_adjustment == 0.0


def test_strategy_stopped_after_3_negative():
    m = AlphaDecayMonitor()
    m.set_baseline("tech", 60)
    m.record_monthly_alpha(-1.0)
    m.record_monthly_alpha(-0.5)
    report = m.generate_report({"tech": 58}, strategy_alpha=-0.3)
    assert report.consecutive_negative_months == 3
    assert report.strategy_status == "stopped"


def test_strategy_active():
    m = AlphaDecayMonitor()
    report = m.generate_report({"tech": 60}, strategy_alpha=2.0)
    assert report.strategy_status == "active"


# --- Advisor Tracker ---
def test_advisor_category_a():
    t = AdvisorTracker()
    t.record_trade("AAPL", quant_score=75, advisor_bonus=0, return_pct=3.0)
    report = t.generate_report()
    assert report.category_a_count == 1
    assert report.category_b_count == 0


def test_advisor_category_b():
    t = AdvisorTracker()
    t.record_trade("2330", quant_score=65, advisor_bonus=8, return_pct=2.0)
    report = t.generate_report()
    assert report.category_b_count == 1


def test_advisor_cap_recommendation():
    t = AdvisorTracker()
    # A trades perform well
    for i in range(10):
        t.record_trade(f"A{i}", 75, 0, 2.0)
    # B trades perform poorly
    for i in range(10):
        t.record_trade(f"B{i}", 65, 8, 0.5)
    report = t.generate_report()
    assert report.recommended_cap < 10.0  # should reduce


def test_advisor_insufficient_data():
    t = AdvisorTracker()
    t.record_trade("X", 65, 8, 1.0)  # only 1 B trade
    report = t.generate_report()
    assert report.recommended_cap == 10.0  # not enough data to change


# --- Behavioral Tracker ---
def test_behavior_all_disciplined():
    bt = BehavioralTracker()
    bt.record(BehaviorEvent("AAPL", "stop_executed", return_pct=-2.0))
    bt.record(BehaviorEvent("NVDA", "signal_followed", return_pct=3.0))
    report = bt.generate_report()
    assert report.stop_execution_rate == 100
    assert report.signal_follow_rate == 100
    assert len(report.diagnostic_codes) == 0


def test_behavior_missed_stops():
    bt = BehavioralTracker()
    bt.record(BehaviorEvent("AAPL", "stop_missed", return_pct=-8.0))
    bt.record(BehaviorEvent("NVDA", "stop_executed", return_pct=-2.0))
    bt.record(BehaviorEvent("TSLA", "stop_missed", return_pct=-6.0))
    report = bt.generate_report()
    assert report.stop_execution_rate < 50
    assert "BHV-02" in report.diagnostic_codes


def test_behavior_chasing():
    bt = BehavioralTracker()
    for i in range(5):
        bt.record(BehaviorEvent(f"S{i}", "chase", signal_price=100, actual_price=105, return_pct=-1.0))
    for i in range(5):
        bt.record(BehaviorEvent(f"T{i}", "signal_followed", return_pct=2.0))
    report = bt.generate_report()
    assert report.chase_rate > 0
    assert report.avg_chase_deviation > 0


def test_behavior_empty():
    bt = BehavioralTracker()
    report = bt.generate_report()
    assert report.total_events == 0
    assert report.stop_execution_rate == 100
