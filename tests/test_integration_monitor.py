"""Smoke test: monitor initializes in lite mode without any API keys."""
import pytest
from quantforge.monitor.monitor import TradeMonitor


class TestMonitorIntegration:
    def test_lite_mode_no_keys_starts_ok(self):
        """Monitor should start in lite mode even without any API keys."""
        config = {
            "watchlist": {"US": ["AAPL", "NVDA"], "TW": ["2330"]},
            "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                         "rsi_overbought": 80, "rsi_oversold": 20},
            "notification": {"sensitivity": "medium"},
            "monitor": {"monitor_mode": "lite", "scan_interval_minutes": 15,
                         "reports": {"output_dir": "/tmp/qf-test", "retention_days": 1}},
        }
        monitor = TradeMonitor(config)
        assert monitor.mode == "lite"
        assert monitor.scan_interval == 900
        warnings = monitor._startup_check()
        assert len(warnings) > 0  # should warn about missing keys

    def test_full_mode_downgrades_without_llm(self):
        config = {
            "watchlist": {"US": ["AAPL"], "TW": []},
            "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                         "rsi_overbought": 80, "rsi_oversold": 20},
            "notification": {"sensitivity": "medium"},
            "monitor": {"monitor_mode": "full", "scan_interval_minutes": 15,
                         "reports": {"output_dir": "/tmp/qf-test", "retention_days": 1}},
        }
        monitor = TradeMonitor(config)
        assert monitor.mode == "lite"

    def test_startup_summary_has_correct_format(self):
        config = {
            "watchlist": {"US": ["AAPL", "NVDA"], "TW": ["2330"]},
            "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                         "rsi_overbought": 80, "rsi_oversold": 20},
            "monitor": {"monitor_mode": "lite", "scan_interval_minutes": 15,
                         "reports": {"output_dir": "/tmp/qf-test", "retention_days": 1}},
        }
        monitor = TradeMonitor(config)
        summary = monitor._startup_summary()
        assert "2 US" in summary
        assert "1 TW" in summary
        assert "15 min" in summary
