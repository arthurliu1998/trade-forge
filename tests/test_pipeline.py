# tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from quantforge.monitor.pipeline import AnalysisPipeline
from quantforge.core.models import QuantSignal, EdgeScores, FactorScore, Regime
from quantforge.signals.engine import Signal


def _make_quant_signal(symbol="NVDA", score=78.5):
    edge = EdgeScores(
        technical=FactorScore("technical", 3.0, 0.75, 0.45),
        chipflow=None,
        crossmarket=FactorScore("crossmarket", 1.0, 0.50, 0.20),
        sentiment=FactorScore("sentiment", 0.64, 0.82, 0.35),
    )
    return QuantSignal(symbol=symbol, market="US", quant_score=score,
                       advisor_bonus=0.0, regime=Regime.BULL_TREND,
                       edge_scores=edge, timestamp="2026-04-27T08:35:00")


@pytest.fixture
def config():
    return {
        "watchlist": {"US": ["NVDA", "AAPL"], "TW": []},
        "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                     "rsi_overbought": 80, "rsi_oversold": 20},
        "monitor": {
            "monitor_mode": "lite",
            "reports": {"output_dir": "/tmp/qf-test-reports", "retention_days": 1},
        },
    }


class TestAnalysisPipeline:
    def test_should_analyze_high_signal(self, config):
        pipeline = AnalysisPipeline(config, notifier=MagicMock(),
                                     llm_router=MagicMock())
        signal = Signal("NVDA", "rsi_oversold", "HIGH", "RSI low")
        assert pipeline._should_analyze(signal) is True

    def test_should_analyze_critical_signal(self, config):
        pipeline = AnalysisPipeline(config, notifier=MagicMock(),
                                     llm_router=MagicMock())
        signal = Signal("NVDA", "test", "CRITICAL", "test")
        assert pipeline._should_analyze(signal) is True

    def test_should_not_analyze_medium_signal(self, config):
        pipeline = AnalysisPipeline(config, notifier=MagicMock(),
                                     llm_router=MagicMock())
        signal = Signal("NVDA", "test", "MEDIUM", "test")
        assert pipeline._should_analyze(signal) is False

    def test_should_not_analyze_low_signal(self, config):
        pipeline = AnalysisPipeline(config, notifier=MagicMock(),
                                     llm_router=MagicMock())
        signal = Signal("NVDA", "test", "LOW", "test")
        assert pipeline._should_analyze(signal) is False

    @pytest.mark.asyncio
    async def test_run_calls_llm_on_high_signal(self, config):
        notifier = MagicMock()
        notifier.send_text = MagicMock(return_value=True)
        llm = MagicMock()
        llm.has_providers = MagicMock(return_value=True)
        llm.analyze = AsyncMock(return_value={"content": "Analysis", "_provider": "claude"})

        pipeline = AnalysisPipeline(config, notifier=notifier, llm_router=llm)
        pipeline._score_symbol = MagicMock(return_value=_make_quant_signal())

        signal = Signal("NVDA", "rsi_oversold", "HIGH", "RSI low")
        await pipeline.run(signal)

        llm.analyze.assert_called_once()
        notifier.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_skips_llm_on_medium_signal(self, config):
        notifier = MagicMock()
        llm = MagicMock()
        llm.analyze = AsyncMock()

        pipeline = AnalysisPipeline(config, notifier=notifier, llm_router=llm)
        signal = Signal("NVDA", "test", "MEDIUM", "test")
        await pipeline.run(signal)

        llm.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_briefing(self, config):
        notifier = MagicMock()
        notifier.send_text = MagicMock(return_value=True)
        llm = MagicMock()
        llm.has_providers = MagicMock(return_value=True)
        llm.analyze = AsyncMock(return_value={"content": "Briefing", "_provider": "claude"})

        pipeline = AnalysisPipeline(config, notifier=notifier, llm_router=llm)
        pipeline._score_symbol = MagicMock(return_value=_make_quant_signal())

        await pipeline.run_briefing("tw_premarket")
        llm.analyze.assert_called_once()
        notifier.send_text.assert_called_once()
