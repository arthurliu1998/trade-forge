"""QuantScanner: orchestrates the full factor pipeline for scoring a stock."""
import pandas as pd
from quantforge.core.models import Regime, QuantSignal
from quantforge.regime.detector import RegimeDetector
from quantforge.factors.technical_factor import TechnicalFactor
from quantforge.factors.chipflow_factor import ChipflowFactor
from quantforge.factors.crossmarket_factor import CrossMarketFactor
from quantforge.factors.sentiment_factor import SentimentFactor
from quantforge.factors.synthesizer import SignalSynthesizer

TW_WEIGHTS = {"technical": 0.35, "chipflow": 0.30, "crossmarket": 0.15, "sentiment": 0.20}
US_WEIGHTS = {"technical": 0.45, "chipflow": 0.0, "crossmarket": 0.20, "sentiment": 0.35}


class QuantScanner:
    def __init__(self):
        self.regime_detector = RegimeDetector()
        self.synthesizer = SignalSynthesizer()

    def score_stock(
        self,
        symbol: str,
        market: str,
        ohlcv: pd.DataFrame,
        chipflow_data: dict = None,
        crossmarket_data: dict = None,
        sentiment_data: dict = None,
        advisor_bonus: float = 0.0,
        vix: float = 15.0,
    ) -> QuantSignal:
        weights = TW_WEIGHTS if market == "TW" else US_WEIGHTS

        regime = self.regime_detector.detect_from_data(ohlcv, vix=vix)

        tech_factor = TechnicalFactor(weight=weights["technical"])
        tech_score = tech_factor.compute(symbol, {"ohlcv": ohlcv, "regime": regime})

        chip_score = None
        if market == "TW" and chipflow_data:
            chip_factor = ChipflowFactor(weight=weights["chipflow"])
            chip_score = chip_factor.compute(symbol, {"institutional_flow": chipflow_data})

        cross_factor = CrossMarketFactor(weight=weights["crossmarket"])
        cross_score = cross_factor.compute(symbol, crossmarket_data or {})

        sent_factor = SentimentFactor(weight=weights["sentiment"])
        sent_score = sent_factor.compute(symbol, sentiment_data or {})

        return self.synthesizer.synthesize(symbol, {
            "market": market,
            "regime": regime,
            "technical_score": tech_score,
            "chipflow_score": chip_score,
            "crossmarket_score": cross_score,
            "sentiment_score": sent_score,
            "advisor_bonus": advisor_bonus,
        })
