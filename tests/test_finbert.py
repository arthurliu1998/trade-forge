import pytest
from unittest.mock import patch, MagicMock
from quantforge.finbert.analyzer import FinBERTAnalyzer, ScoredArticle


class TestFinBERTAnalyzer:
    def test_score_returns_float_in_range(self):
        analyzer = FinBERTAnalyzer.__new__(FinBERTAnalyzer)
        analyzer._model = None
        analyzer._tokenizer = None
        analyzer._pipeline = MagicMock()
        analyzer._pipeline.return_value = [
            {"label": "positive", "score": 0.85},
        ]
        result = analyzer.score("Stock surges on strong earnings")
        assert isinstance(result, float)
        assert -1.0 <= result <= 1.0

    def test_score_negative_text(self):
        analyzer = FinBERTAnalyzer.__new__(FinBERTAnalyzer)
        analyzer._model = None
        analyzer._tokenizer = None
        analyzer._pipeline = MagicMock()
        analyzer._pipeline.return_value = [
            {"label": "negative", "score": 0.90},
        ]
        result = analyzer.score("Company under investigation for fraud")
        assert result < 0

    def test_score_neutral_text(self):
        analyzer = FinBERTAnalyzer.__new__(FinBERTAnalyzer)
        analyzer._model = None
        analyzer._tokenizer = None
        analyzer._pipeline = MagicMock()
        analyzer._pipeline.return_value = [
            {"label": "neutral", "score": 0.70},
        ]
        result = analyzer.score("Company reports quarterly results")
        assert -0.3 <= result <= 0.3

    def test_score_batch(self):
        analyzer = FinBERTAnalyzer.__new__(FinBERTAnalyzer)
        analyzer._model = None
        analyzer._tokenizer = None
        analyzer._pipeline = MagicMock()
        analyzer._pipeline.side_effect = [
            [{"label": "positive", "score": 0.8}],
            [{"label": "negative", "score": 0.9}],
        ]
        articles = [
            {"text": "Good news", "symbol": "AAPL", "source": "yahoo", "published": "2026-04-27"},
            {"text": "Bad news", "symbol": "AAPL", "source": "finviz", "published": "2026-04-27"},
        ]
        results = analyzer.score_batch(articles)
        assert len(results) == 2
        assert isinstance(results[0], ScoredArticle)
        assert results[0].sentiment > 0
        assert results[1].sentiment < 0

    def test_negative_boost(self):
        analyzer = FinBERTAnalyzer.__new__(FinBERTAnalyzer)
        analyzer._model = None
        analyzer._tokenizer = None
        analyzer._pipeline = MagicMock()
        analyzer._pipeline.side_effect = [
            [{"label": "negative", "score": 0.85}],
        ]
        articles = [
            {"text": "Stock crashes", "symbol": "X", "source": "y", "published": "2026-04-27"},
        ]
        results = analyzer.score_batch(articles)
        assert results[0].neg_boosted is True

    def test_is_available_false_without_model(self):
        analyzer = FinBERTAnalyzer.__new__(FinBERTAnalyzer)
        analyzer._model = None
        analyzer._tokenizer = None
        analyzer._pipeline = None
        assert analyzer.is_loaded() is False
