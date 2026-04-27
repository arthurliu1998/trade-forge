"""FinBERT sentiment analyzer. Local model, deterministic, free."""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "ProsusAI/finbert"


@dataclass
class ScoredArticle:
    text: str
    symbol: str
    source: str
    published: str
    sentiment: float  # -1.0 to 1.0
    neg_boosted: bool = False


class FinBERTAnalyzer:
    """Wrapper for ProsusAI/finbert sentiment model.

    Lazy-loads on first use. Use `python -m quantforge.finbert.download`
    to pre-download the model (~400MB).
    """

    def __init__(self, neg_boost: float = 1.5):
        self._pipeline = None
        self._model = None
        self._tokenizer = None
        self.neg_boost = neg_boost

    def _load(self):
        if self._pipeline is not None:
            return
        try:
            from transformers import pipeline as hf_pipeline
            self._pipeline = hf_pipeline(
                "sentiment-analysis", model=MODEL_NAME, tokenizer=MODEL_NAME,
                truncation=True, max_length=512,
            )
            logger.info("FinBERT model loaded successfully")
        except Exception as e:
            logger.error("Failed to load FinBERT: %s", type(e).__name__)
            raise

    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def score(self, text: str) -> float:
        """Score a single text. Returns -1.0 (bearish) to 1.0 (bullish)."""
        self._load()
        result = self._pipeline(text[:512])[0]
        label = result["label"].lower()
        confidence = result["score"]
        if label == "positive":
            return confidence
        elif label == "negative":
            return -confidence
        else:
            return 0.0

    def score_batch(self, articles: list[dict]) -> list[ScoredArticle]:
        """Score a batch of articles.

        Args:
            articles: list of dicts with keys: text, symbol, source, published

        Returns:
            List of ScoredArticle with sentiment scores.
            Negative articles are marked with neg_boosted=True.
        """
        self._load()
        results = []
        for article in articles:
            sentiment = self.score(article["text"])
            boosted = sentiment < 0
            results.append(ScoredArticle(
                text=article["text"],
                symbol=article["symbol"],
                source=article["source"],
                published=article["published"],
                sentiment=sentiment,
                neg_boosted=boosted,
            ))
        return results
