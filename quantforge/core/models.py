"""Core data models for QuantForge signal pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Regime(Enum):
    BULL_TREND = "bull_trend"
    BEAR_TREND = "bear_trend"
    CONSOLIDATION = "consolidation"
    CRISIS = "crisis"
    NEUTRAL = "neutral"


@dataclass
class FactorScore:
    name: str
    raw: float
    normalized: float
    weight: float

    @property
    def clamped(self) -> float:
        return max(0.0, min(1.0, self.normalized))


@dataclass
class EdgeScores:
    technical: FactorScore
    chipflow: Optional[FactorScore]
    crossmarket: FactorScore
    sentiment: FactorScore

    @property
    def quant_score(self) -> float:
        total = 0.0
        for f in [self.technical, self.chipflow, self.crossmarket, self.sentiment]:
            if f is not None:
                total += f.clamped * f.weight
        return total * 100


@dataclass
class QuantSignal:
    symbol: str
    market: str
    quant_score: float
    advisor_bonus: float
    regime: Regime
    edge_scores: Optional[EdgeScores]
    timestamp: str
    buy_threshold: float = 70.0

    @property
    def combined_score(self) -> float:
        return self.quant_score + self.advisor_bonus

    @property
    def signal_level(self) -> str:
        qs = self.quant_score
        cs = self.combined_score
        if qs >= max(80, self.buy_threshold):
            return "STRONG_BUY"
        if qs >= self.buy_threshold:
            return "BUY"
        if qs >= 60 and cs >= self.buy_threshold:
            return "ADVISOR_ASSISTED_BUY"
        if qs >= 60:
            return "WATCHLIST"
        if qs <= 29:
            return "STRONG_SELL"
        if qs <= 39:
            return "WATCH_SELL"
        return "NO_SIGNAL"

    @property
    def position_multiplier(self) -> float:
        level = self.signal_level
        return {"STRONG_BUY": 1.0, "BUY": 0.7, "ADVISOR_ASSISTED_BUY": 0.5}.get(level, 0.0)
