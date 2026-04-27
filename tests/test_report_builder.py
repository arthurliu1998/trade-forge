"""Tests for ReportBuilder — Telegram summaries and full markdown reports."""
from quantforge.monitor.report_builder import ReportBuilder
from quantforge.core.models import QuantSignal, EdgeScores, FactorScore, Regime


def _make_signal(symbol="NVDA", quant_score=78.5, advisor_bonus=6.2,
                 regime=Regime.BULL_TREND) -> QuantSignal:
    edge = EdgeScores(
        technical=FactorScore("technical", 3.0, 0.75, 0.45),
        chipflow=None,
        crossmarket=FactorScore("crossmarket", 1.0, 0.50, 0.20),
        sentiment=FactorScore("sentiment", 0.64, 0.82, 0.35),
    )
    return QuantSignal(
        symbol=symbol, market="US", quant_score=quant_score,
        advisor_bonus=advisor_bonus, regime=regime,
        edge_scores=edge, timestamp="2026-04-27T08:35:00",
    )


class TestReportBuilder:
    def test_build_signal_returns_summary_and_full(self):
        signal = _make_signal()
        llm_result = {"content": "Strong data center demand.", "_provider": "claude"}
        summary, full = ReportBuilder.build_signal(signal, llm_result, trigger="MA20 crossover up")
        assert isinstance(summary, str)
        assert isinstance(full, str)

    def test_summary_contains_symbol_and_score(self):
        signal = _make_signal()
        llm_result = {"content": "Analysis text.", "_provider": "claude"}
        summary, _ = ReportBuilder.build_signal(signal, llm_result, trigger="RSI oversold")
        assert "NVDA" in summary
        assert "78.5" in summary

    def test_full_report_contains_all_sections(self):
        signal = _make_signal()
        llm_result = {"content": "Detailed analysis.", "_provider": "claude"}
        _, full = ReportBuilder.build_signal(signal, llm_result, trigger="RSI oversold")
        assert "# NVDA Analysis Report" in full
        assert "Edge Scores" in full
        assert "Regime" in full
        assert "LLM Analysis" in full
        assert "Detailed analysis." in full

    def test_summary_short_enough_for_telegram(self):
        signal = _make_signal()
        llm_result = {"content": "Short.", "_provider": "claude"}
        summary, _ = ReportBuilder.build_signal(signal, llm_result, trigger="test")
        lines = summary.strip().split("\n")
        assert len(lines) <= 5

    def test_build_signal_without_llm(self):
        signal = _make_signal()
        summary, full = ReportBuilder.build_signal(signal, llm_result=None, trigger="test")
        assert "NVDA" in summary
        assert "N/A" in full or "No LLM" in full

    def test_build_briefing(self):
        signals = [_make_signal("NVDA", 78.5), _make_signal("AAPL", 65.0)]
        llm_result = {"content": "Market overview text.", "_provider": "claude"}
        summary, full = ReportBuilder.build_briefing(
            "tw_premarket", signals, regime=Regime.BULL_TREND,
            vix=18.2, llm_result=llm_result,
        )
        assert "NVDA" in summary
        assert "AAPL" in summary
        assert "BULL_TREND" in summary or "bull_trend" in summary
