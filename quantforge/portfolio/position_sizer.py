"""Position sizing with ATR-based risk control.

Spec (Section 3, Layer 3):
- Standard position = Total capital x 5%
- Adjusted by signal strength (position_multiplier from QuantSignal)
- Adjusted by regime discount (bear/crisis = x0.5)
- ATR sizing: position = acceptable_loss / (2 x ATR), max risk 1% per trade
- Stop-loss = entry_price - 2 x ATR
"""
from dataclasses import dataclass
from quantforge.core.models import Regime, QuantSignal


@dataclass
class PositionPlan:
    symbol: str
    market: str
    entry_price: float
    stop_loss: float
    target_price: float
    position_value: float
    shares: int
    risk_pct: float  # actual risk as % of total capital


class PositionSizer:
    def __init__(self, base_pct: float = 0.05, max_risk_pct: float = 0.01,
                 atr_stop_multiplier: float = 2.0, reward_risk_ratio: float = 1.5):
        self.base_pct = base_pct
        self.max_risk_pct = max_risk_pct
        self.atr_stop_mult = atr_stop_multiplier
        self.rr_ratio = reward_risk_ratio

    def calculate(self, signal: QuantSignal, total_capital: float,
                  current_price: float, atr: float) -> PositionPlan:
        if atr <= 0 or current_price <= 0 or total_capital <= 0:
            return PositionPlan(signal.symbol, signal.market, current_price,
                                current_price, current_price, 0, 0, 0.0)

        # Signal-based position
        signal_position = total_capital * self.base_pct * signal.position_multiplier

        # Regime discount
        if signal.regime in (Regime.BEAR_TREND, Regime.CRISIS):
            signal_position *= 0.5

        # ATR-based max position (risk limit)
        stop_distance = self.atr_stop_mult * atr
        acceptable_loss = total_capital * self.max_risk_pct
        atr_position = (acceptable_loss / stop_distance) * current_price

        # Take the smaller of signal-based and ATR-based
        position_value = min(signal_position, atr_position)
        shares = max(0, int(position_value / current_price))
        actual_value = shares * current_price

        stop_loss = round(current_price - stop_distance, 2)
        target_price = round(current_price + stop_distance * self.rr_ratio, 2)
        risk_pct = (stop_distance * shares) / total_capital if total_capital > 0 else 0

        return PositionPlan(
            symbol=signal.symbol, market=signal.market,
            entry_price=current_price, stop_loss=stop_loss,
            target_price=target_price, position_value=round(actual_value, 2),
            shares=shares, risk_pct=round(risk_pct, 4),
        )
