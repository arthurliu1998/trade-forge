# tests/test_event_detector.py
import pytest
from datetime import datetime, timedelta
from quantforge.monitor.event_detector import EventDetector, CriticalEvent
from quantforge.finbert.analyzer import ScoredArticle


@pytest.fixture
def config():
    return {
        "finbert_threshold_pos": 0.9,
        "finbert_threshold_neg": -0.85,
        "keywords": ["earnings", "merger", "delisting"],
        "article_cluster_count": 3,
        "article_cluster_window_min": 15,
    }


@pytest.fixture
def cooldown_config():
    return {"same_symbol_minutes": 120, "daily_recalc_limit": 5}


class TestEventDetector:
    def test_finbert_extreme_positive_triggers(self, config, cooldown_config):
        detector = EventDetector(config, cooldown_config)
        articles = [
            ScoredArticle("Great news", "NVDA", "yahoo", "2026-04-27", 0.95, False),
        ]
        events = detector.detect_from_news(articles)
        assert len(events) == 1
        assert events[0].symbol == "NVDA"
        assert events[0].trigger == "finbert_extreme"

    def test_finbert_extreme_negative_triggers(self, config, cooldown_config):
        detector = EventDetector(config, cooldown_config)
        articles = [
            ScoredArticle("Fraud investigation", "AAPL", "finviz", "2026-04-27", -0.90, True),
        ]
        events = detector.detect_from_news(articles)
        assert len(events) == 1
        assert events[0].symbol == "AAPL"

    def test_keyword_match_triggers(self, config, cooldown_config):
        detector = EventDetector(config, cooldown_config)
        articles = [
            ScoredArticle("TSLA earnings beat estimates", "TSLA", "yahoo", "2026-04-27", 0.5, False),
        ]
        events = detector.detect_from_news(articles)
        assert any(e.trigger == "keyword" for e in events)

    def test_article_cluster_triggers(self, config, cooldown_config):
        detector = EventDetector(config, cooldown_config)
        now = datetime.now().isoformat()
        articles = [
            ScoredArticle("NVDA up", "NVDA", "s1", now, 0.6, False),
            ScoredArticle("NVDA surges", "NVDA", "s2", now, 0.5, False),
            ScoredArticle("NVDA rally", "NVDA", "s3", now, 0.7, False),
        ]
        events = detector.detect_from_news(articles)
        assert any(e.trigger == "article_cluster" for e in events)

    def test_score_delta_triggers(self, config, cooldown_config):
        detector = EventDetector(config, cooldown_config)
        detector._last_scores = {"NVDA": 60.0}
        events = detector.detect_from_scores({"NVDA": 80.0})
        assert len(events) == 1
        assert events[0].trigger == "score_delta"

    def test_score_delta_below_threshold_no_trigger(self, config, cooldown_config):
        detector = EventDetector(config, cooldown_config)
        detector._last_scores = {"NVDA": 60.0}
        events = detector.detect_from_scores({"NVDA": 65.0})
        assert len(events) == 0

    def test_regime_change_triggers(self, config, cooldown_config):
        from quantforge.core.models import Regime
        detector = EventDetector(config, cooldown_config)
        detector._last_regime = Regime.BULL_TREND
        events = detector.detect_regime_change(Regime.BEAR_TREND, vix=25.0)
        assert len(events) == 1
        assert events[0].trigger == "regime_change"

    def test_vix_crisis_triggers(self, config, cooldown_config):
        from quantforge.core.models import Regime
        detector = EventDetector(config, cooldown_config)
        detector._last_regime = Regime.BULL_TREND
        events = detector.detect_regime_change(Regime.CRISIS, vix=35.0)
        assert any(e.trigger == "vix_crisis" for e in events)

    def test_cooldown_blocks_same_symbol(self, config, cooldown_config):
        detector = EventDetector(config, cooldown_config)
        articles = [
            ScoredArticle("Big news", "NVDA", "yahoo", "2026-04-27", 0.95, False),
        ]
        events1 = detector.detect_from_news(articles)
        assert len(events1) == 1
        events2 = detector.detect_from_news(articles)
        assert len(events2) == 0

    def test_daily_limit(self, config):
        cooldown = {"same_symbol_minutes": 0, "daily_recalc_limit": 2}
        detector = EventDetector(config, cooldown)
        for i in range(3):
            sym = f"SYM{i}"
            articles = [ScoredArticle(f"News {i}", sym, "y", "now", 0.95, False)]
            events = detector.detect_from_news(articles)
            if i < 2:
                assert len(events) == 1
            else:
                assert len(events) == 0
