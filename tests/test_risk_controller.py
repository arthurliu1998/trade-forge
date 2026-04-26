from quantforge.risk.controller import RiskController, RiskCheckResult


def test_approve_within_limits():
    rc = RiskController()
    result = rc.check("AAPL", "US", 0.05, {"stock_weights": {}, "total_exposure": 0.3})
    assert result.approved
    assert result.reason == "OK"


def test_reject_single_stock_exceeded():
    rc = RiskController()
    result = rc.check("AAPL", "US", 0.10,
                      {"stock_weights": {"AAPL": 0.15}, "total_exposure": 0.4})
    assert not result.approved
    assert "25.0%" in result.reason


def test_reject_total_exposure():
    rc = RiskController()
    result = rc.check("NVDA", "US", 0.10,
                      {"stock_weights": {}, "total_exposure": 0.55})
    assert not result.approved
    assert "exposure" in result.reason.lower()


def test_reject_per_trade_risk():
    rc = RiskController()
    result = rc.check("TSLA", "US", 0.05,
                      {"stock_weights": {}, "total_exposure": 0.3}, risk_pct=0.02)
    assert not result.approved
    assert "risk" in result.reason.lower()


def test_sector_warning():
    rc = RiskController()
    result = rc.check("AMD", "US", 0.05,
                      {"stock_weights": {}, "total_exposure": 0.3,
                       "sector_weights": {"Technology": 0.40}})
    assert result.approved  # warning, not blocking
    assert len(result.warnings) > 0


def test_correlation_warning():
    rc = RiskController()
    result = rc.check("AMD", "US", 0.05,
                      {"stock_weights": {}, "total_exposure": 0.3,
                       "correlations": {"NVDA-AMD": 0.85}})
    assert result.approved
    assert any("correlation" in w.lower() for w in result.warnings)
