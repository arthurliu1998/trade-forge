"""Advisor accuracy tracker — A/B comparison of pure quant vs advisor-assisted trades.

Spec (Section 10.2):
- Category A: Pure quant signals (quant >= 70)
- Category B: Advisor-assisted (quant 60-69 + advisor >= 70)
- Auto-adjust advisor cap based on B vs A performance
"""
from dataclasses import dataclass, field


@dataclass
class TradeRecord:
    symbol: str
    category: str  # "A" (pure quant) or "B" (advisor-assisted)
    quant_score: float
    advisor_bonus: float
    return_pct: float


@dataclass
class AdvisorReport:
    category_a_count: int
    category_a_avg_return: float
    category_a_win_rate: float
    category_b_count: int
    category_b_avg_return: float
    category_b_win_rate: float
    performance_ratio: float  # B avg / A avg (> 0.8 = helpful)
    recommended_cap: float  # +/-10, +/-7, +/-3, or 0


class AdvisorTracker:
    def __init__(self, initial_cap: float = 10.0):
        self.current_cap = initial_cap
        self._trades: list[TradeRecord] = []

    def record_trade(self, symbol: str, quant_score: float,
                     advisor_bonus: float, return_pct: float):
        category = "B" if quant_score < 70 and quant_score + advisor_bonus >= 70 else "A"
        self._trades.append(TradeRecord(symbol, category, quant_score, advisor_bonus, return_pct))

    def generate_report(self) -> AdvisorReport:
        a_trades = [t for t in self._trades if t.category == "A"]
        b_trades = [t for t in self._trades if t.category == "B"]

        a_avg = sum(t.return_pct for t in a_trades) / len(a_trades) if a_trades else 0
        b_avg = sum(t.return_pct for t in b_trades) / len(b_trades) if b_trades else 0
        a_wins = sum(1 for t in a_trades if t.return_pct > 0)
        b_wins = sum(1 for t in b_trades if t.return_pct > 0)
        a_wr = a_wins / len(a_trades) * 100 if a_trades else 0
        b_wr = b_wins / len(b_trades) * 100 if b_trades else 0

        ratio = b_avg / a_avg if a_avg > 0 else 0

        if len(b_trades) < 5:
            rec_cap = self.current_cap  # not enough data
        elif ratio >= 0.8:
            rec_cap = 10.0
        elif ratio >= 0.5:
            rec_cap = 7.0
        elif ratio > 0:
            rec_cap = 3.0
        else:
            rec_cap = 0.0  # downgrade to Option B

        return AdvisorReport(
            category_a_count=len(a_trades), category_a_avg_return=round(a_avg, 2),
            category_a_win_rate=round(a_wr, 1),
            category_b_count=len(b_trades), category_b_avg_return=round(b_avg, 2),
            category_b_win_rate=round(b_wr, 1),
            performance_ratio=round(ratio, 2), recommended_cap=rec_cap,
        )
