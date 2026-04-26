"""Behavioral discipline tracker.

Spec (Section 10.3):
- Track stop-loss execution rate
- Track signal ignore rate
- Track chase rate (entry price vs signal price deviation)
- Weekly report comparing disciplined vs undisciplined trades
"""
from dataclasses import dataclass, field


@dataclass
class BehaviorEvent:
    symbol: str
    event_type: str  # "stop_executed", "stop_missed", "signal_followed", "signal_ignored", "chase"
    signal_price: float = 0.0
    actual_price: float = 0.0
    return_pct: float = 0.0


@dataclass
class BehaviorReport:
    total_events: int
    stop_execution_rate: float  # 0-100%
    signal_follow_rate: float  # 0-100%
    chase_rate: float  # 0-100%
    avg_chase_deviation: float  # % average overpay when chasing
    disciplined_avg_return: float
    undisciplined_avg_return: float
    estimated_cost_of_indiscipline: float  # total $ lost to behavioral errors
    diagnostic_codes: list[str]  # BHV-01 through BHV-04


class BehavioralTracker:
    def __init__(self):
        self._events: list[BehaviorEvent] = []

    def record(self, event: BehaviorEvent):
        self._events.append(event)

    def generate_report(self) -> BehaviorReport:
        if not self._events:
            return BehaviorReport(0, 100, 100, 0, 0, 0, 0, 0, [])

        stops = [e for e in self._events if e.event_type in ("stop_executed", "stop_missed")]
        signals = [e for e in self._events if e.event_type in ("signal_followed", "signal_ignored")]
        chases = [e for e in self._events if e.event_type == "chase"]

        # Stop execution rate
        stop_exec = sum(1 for e in stops if e.event_type == "stop_executed")
        stop_rate = stop_exec / len(stops) * 100 if stops else 100

        # Signal follow rate
        sig_follow = sum(1 for e in signals if e.event_type == "signal_followed")
        sig_rate = sig_follow / len(signals) * 100 if signals else 100

        # Chase rate
        chase_rate = len(chases) / max(len(self._events), 1) * 100
        chase_devs = [(e.actual_price - e.signal_price) / e.signal_price * 100
                      for e in chases if e.signal_price > 0]
        avg_chase = sum(chase_devs) / len(chase_devs) if chase_devs else 0

        # Disciplined vs undisciplined returns
        disciplined = [e for e in self._events
                       if e.event_type in ("stop_executed", "signal_followed") and e.return_pct != 0]
        undisciplined = [e for e in self._events
                         if e.event_type in ("stop_missed", "signal_ignored", "chase") and e.return_pct != 0]
        d_avg = sum(e.return_pct for e in disciplined) / len(disciplined) if disciplined else 0
        u_avg = sum(e.return_pct for e in undisciplined) / len(undisciplined) if undisciplined else 0

        # Cost of indiscipline
        cost = sum(e.return_pct for e in undisciplined) - sum(e.return_pct for e in disciplined) if undisciplined else 0

        # Diagnostic codes
        codes = []
        if chase_rate > 20:
            codes.append("BHV-01")  # FOMO/chasing
        if stop_rate < 80:
            codes.append("BHV-02")  # Held loser too long
        if len(self._events) > 30 and len(set(e.symbol for e in self._events)) > 20:
            codes.append("BHV-03")  # Overtrading
        if d_avg > 0 and u_avg < 0:
            codes.append("BHV-04")  # Cut winner, held loser

        return BehaviorReport(
            total_events=len(self._events),
            stop_execution_rate=round(stop_rate, 1),
            signal_follow_rate=round(sig_rate, 1),
            chase_rate=round(chase_rate, 1),
            avg_chase_deviation=round(avg_chase, 2),
            disciplined_avg_return=round(d_avg, 2),
            undisciplined_avg_return=round(u_avg, 2),
            estimated_cost_of_indiscipline=round(cost, 2),
            diagnostic_codes=codes,
        )
