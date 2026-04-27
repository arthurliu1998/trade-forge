"""Detect critical events from price data and news for instant recalculation."""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from quantforge.core.models import Regime
from quantforge.finbert.analyzer import ScoredArticle

logger = logging.getLogger(__name__)

SCORE_DELTA_THRESHOLD = 15.0


@dataclass
class CriticalEvent:
    symbol: str
    trigger: str
    detail: str
    timestamp: str


class EventDetector:
    """Detects critical events from news, quant scores, and market regime.

    Three detection surfaces:
    1. News: FinBERT extreme scores, keyword matches, article clusters
    2. Price: quant_score delta > 15
    3. Market: regime transitions, VIX > 30 crisis

    Cooldown prevents excessive recalculation: per-symbol cooldown
    (default 120 min) and daily limit (default 5).
    """

    def __init__(self, event_config: dict, cooldown_config: dict):
        self.finbert_pos = event_config.get("finbert_threshold_pos", 0.9)
        self.finbert_neg = event_config.get("finbert_threshold_neg", -0.85)
        self.keywords = [k.lower() for k in event_config.get("keywords", [])]
        self.cluster_count = event_config.get("article_cluster_count", 3)
        self.cluster_window = event_config.get("article_cluster_window_min", 15)

        self.cooldown_minutes = cooldown_config.get("same_symbol_minutes", 120)
        self.daily_limit = cooldown_config.get("daily_recalc_limit", 5)

        self._last_scores: dict[str, float] = {}
        self._last_regime: Optional[Regime] = None
        self._cooldowns: dict[str, datetime] = {}
        self._daily_count: int = 0
        self._daily_reset_date: Optional[datetime] = None

    # ------------------------------------------------------------------
    # News-based detection
    # ------------------------------------------------------------------

    def detect_from_news(
        self, scored_articles: list[ScoredArticle]
    ) -> list[CriticalEvent]:
        """Detect events from scored news articles.

        Triggers on:
        - finbert_extreme: sentiment score above pos threshold or below neg threshold
        - keyword: article text contains a watched keyword
        - article_cluster: >= cluster_count same-direction articles for one symbol
        """
        events: list[CriticalEvent] = []
        now = datetime.now()

        # --- per-article checks ---
        for article in scored_articles:
            # FinBERT extreme
            if (
                article.sentiment >= self.finbert_pos
                or article.sentiment <= self.finbert_neg
            ):
                event = CriticalEvent(
                    symbol=article.symbol,
                    trigger="finbert_extreme",
                    detail=f"FinBERT={article.sentiment:.2f}: {article.text[:60]}",
                    timestamp=now.isoformat(),
                )
                if self._cooldown_ok(article.symbol):
                    events.append(event)

            # Keyword match
            text_lower = f"{article.text} {article.symbol}".lower()
            for kw in self.keywords:
                if kw in text_lower:
                    event = CriticalEvent(
                        symbol=article.symbol,
                        trigger="keyword",
                        detail=f"Keyword '{kw}': {article.text[:60]}",
                        timestamp=now.isoformat(),
                    )
                    if self._cooldown_ok(article.symbol):
                        events.append(event)
                    break  # one keyword match per article is enough

        # --- cluster check (per symbol) ---
        symbol_articles: dict[str, list[ScoredArticle]] = {}
        for a in scored_articles:
            symbol_articles.setdefault(a.symbol, []).append(a)

        for symbol, arts in symbol_articles.items():
            if len(arts) >= self.cluster_count:
                directions = [1 if a.sentiment > 0 else -1 for a in arts]
                if abs(sum(directions)) == len(directions):
                    event = CriticalEvent(
                        symbol=symbol,
                        trigger="article_cluster",
                        detail=f"{len(arts)} same-direction articles",
                        timestamp=now.isoformat(),
                    )
                    if self._cooldown_ok(symbol):
                        events.append(event)

        return events

    # ------------------------------------------------------------------
    # Score-based detection
    # ------------------------------------------------------------------

    def detect_from_scores(
        self, current_scores: dict[str, float]
    ) -> list[CriticalEvent]:
        """Detect events from quant score changes.

        Triggers when absolute score delta exceeds SCORE_DELTA_THRESHOLD (15).
        """
        events: list[CriticalEvent] = []
        now = datetime.now()
        for symbol, score in current_scores.items():
            prev = self._last_scores.get(symbol)
            if prev is not None and abs(score - prev) > SCORE_DELTA_THRESHOLD:
                event = CriticalEvent(
                    symbol=symbol,
                    trigger="score_delta",
                    detail=f"Score changed {prev:.1f} -> {score:.1f} (delta={score - prev:+.1f})",
                    timestamp=now.isoformat(),
                )
                if self._cooldown_ok(symbol):
                    events.append(event)
        self._last_scores = dict(current_scores)
        return events

    # ------------------------------------------------------------------
    # Regime-based detection
    # ------------------------------------------------------------------

    def detect_regime_change(
        self, current_regime: Regime, vix: float
    ) -> list[CriticalEvent]:
        """Detect events from market regime transitions and VIX spikes.

        Triggers:
        - vix_crisis: VIX > 30 and regime is CRISIS
        - regime_change: regime transitioned (non-crisis)
        """
        events: list[CriticalEvent] = []
        now = datetime.now()

        if current_regime == Regime.CRISIS and vix > 30:
            events.append(
                CriticalEvent(
                    symbol="MARKET",
                    trigger="vix_crisis",
                    detail=f"VIX={vix:.1f} -- crisis mode",
                    timestamp=now.isoformat(),
                )
            )

        if (
            self._last_regime is not None
            and current_regime != self._last_regime
            and current_regime != Regime.CRISIS
        ):
            events.append(
                CriticalEvent(
                    symbol="MARKET",
                    trigger="regime_change",
                    detail=f"{self._last_regime.value} -> {current_regime.value}",
                    timestamp=now.isoformat(),
                )
            )

        self._last_regime = current_regime
        return events

    # ------------------------------------------------------------------
    # Cooldown logic
    # ------------------------------------------------------------------

    def _cooldown_ok(self, symbol: str) -> bool:
        """Check if a symbol is past its cooldown and under the daily limit.

        Returns True and records the event if allowed, False otherwise.
        """
        now = datetime.now()
        today = now.date()

        # Reset daily counter at midnight
        if self._daily_reset_date is None or self._daily_reset_date != today:
            self._daily_count = 0
            self._daily_reset_date = today

        if self._daily_count >= self.daily_limit:
            logger.info("Daily recalc limit reached (%d)", self.daily_limit)
            return False

        last = self._cooldowns.get(symbol)
        if last and (now - last) < timedelta(minutes=self.cooldown_minutes):
            logger.debug("Cooldown active for %s", symbol)
            return False

        self._cooldowns[symbol] = now
        self._daily_count += 1
        return True
