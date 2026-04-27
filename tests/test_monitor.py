# tests/test_monitor.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from quantforge.monitor.monitor import TradeMonitor


@pytest.fixture
def lite_config():
    return {
        "watchlist": {"US": ["AAPL"], "TW": []},
        "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                     "rsi_overbought": 80, "rsi_oversold": 20},
        "notification": {"sensitivity": "medium"},
        "monitor": {
            "monitor_mode": "lite",
            "scan_interval_minutes": 15,
            "reports": {"output_dir": "/tmp/qf-test-reports", "retention_days": 1},
        },
    }


@pytest.fixture
def full_config():
    return {
        "watchlist": {"US": ["AAPL"], "TW": []},
        "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                     "rsi_overbought": 80, "rsi_oversold": 20},
        "notification": {"sensitivity": "medium"},
        "monitor": {
            "monitor_mode": "full",
            "scan_interval_minutes": 15,
            "briefing_timezone": "Asia/Taipei",
            "briefing_schedule": ["08:30", "14:00", "21:00"],
            "cooldown": {"same_symbol_minutes": 120, "daily_recalc_limit": 5},
            "event_detector": {
                "finbert_threshold_pos": 0.9, "finbert_threshold_neg": -0.85,
                "keywords": ["earnings"], "article_cluster_count": 3,
                "article_cluster_window_min": 15,
            },
            "reports": {"output_dir": "/tmp/qf-test-reports", "retention_days": 1},
        },
    }


class TestTradeMonitorInit:
    def test_init_lite(self, lite_config):
        monitor = TradeMonitor(lite_config)
        assert monitor.mode == "lite"
        assert monitor.pipeline is not None

    def test_init_full_without_llm_falls_back_to_lite(self, full_config):
        """Full mode without LLM provider should fallback to lite."""
        monitor = TradeMonitor(full_config)
        # Without API keys configured, LLM router has no providers
        # so full mode should downgrade to lite
        assert monitor.mode == "lite"

    def test_scan_interval_from_config(self, lite_config):
        monitor = TradeMonitor(lite_config)
        assert monitor.scan_interval == 900  # 15 * 60


class TestTradeMonitorStartup:
    def test_startup_warnings_no_telegram(self, lite_config):
        monitor = TradeMonitor(lite_config)
        warnings = monitor._startup_check()
        telegram_warns = [w for w in warnings if "Telegram" in w]
        assert len(telegram_warns) > 0

    def test_startup_summary_format(self, lite_config):
        monitor = TradeMonitor(lite_config)
        summary = monitor._startup_summary()
        assert "QuantForge Monitor started" in summary
        assert "lite" in summary


class TestTradeMonitorStop:
    @pytest.mark.asyncio
    async def test_stop(self, lite_config):
        monitor = TradeMonitor(lite_config)
        monitor._running = True
        await monitor.stop()
        assert monitor._running is False
