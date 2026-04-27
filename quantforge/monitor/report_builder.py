"""Format analysis results into Telegram summaries and full markdown reports."""
from datetime import datetime
from typing import Optional

from quantforge.core.models import QuantSignal, Regime


BRIEFING_TITLES = {
    "tw_premarket": "TW Pre-Market",
    "tw_close": "TW Close",
    "us_premarket": "US Pre-Market",
}


class ReportBuilder:
    @staticmethod
    def build_signal(signal: QuantSignal, llm_result: Optional[dict],
                     trigger: str = "") -> tuple[str, str]:
        """Build a Telegram summary (3-5 lines) and full markdown report for a signal.

        Returns:
            (summary, full) -- summary is short text for Telegram,
            full is a complete markdown report for local storage.
        """
        level = signal.signal_level
        llm_text = llm_result["content"] if llm_result else "No LLM analysis"
        provider = llm_result.get("_provider", "N/A") if llm_result else "N/A"

        llm_oneliner = llm_text[:80].replace("\n", " ")
        summary = (
            f"{signal.symbol} — {level} "
            f"(Quant: {signal.quant_score} + Advisor: {signal.advisor_bonus:+.1f})\n"
            f"Regime: {signal.regime.value} | "
            f"Trigger: {trigger}\n"
            f"LLM: {llm_oneliner}"
        )

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        edge = signal.edge_scores
        edge_table = "| Factor | Raw | Normalized | Weight | Contribution |\n"
        edge_table += "|--------|-----|-----------|--------|-------------|\n"
        if edge:
            for f in [edge.technical, edge.chipflow, edge.crossmarket, edge.sentiment]:
                if f is not None:
                    contrib = f.clamped * f.weight * 100
                    edge_table += (f"| {f.name} | {f.raw:.2f} | "
                                  f"{f.normalized:.2f} | {f.weight:.0%} | "
                                  f"{contrib:.1f} |\n")

        full = (
            f"# {signal.symbol} Analysis Report — {ts}\n\n"
            f"## Signal\n"
            f"- Trigger: {trigger}\n"
            f"- Quant Score: {signal.quant_score} → {level}\n"
            f"- Advisor Bonus: {signal.advisor_bonus:+.1f} → "
            f"Combined: {signal.combined_score:.1f}\n\n"
            f"## Edge Scores\n{edge_table}\n"
            f"## Regime: {signal.regime.value}\n\n"
            f"## LLM Analysis\n{llm_text}\n\n"
            f"## Meta\n"
            f"- Provider: {provider}\n"
            f"- Mode: auto-monitor\n"
        )
        return summary, full

    @staticmethod
    def build_briefing(briefing_type: str, signals: list[QuantSignal],
                       regime: Regime, vix: float,
                       llm_result: Optional[dict]) -> tuple[str, str]:
        """Build a market briefing summary and full report.

        Returns:
            (summary, full) -- summary is short text for Telegram,
            full is a complete markdown briefing for local storage.
        """
        title = BRIEFING_TITLES.get(briefing_type, briefing_type)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        llm_text = llm_result["content"] if llm_result else "No LLM analysis"

        ranked = sorted(signals, key=lambda s: s.quant_score, reverse=True)

        lines = [f"QuantForge {title} — {ts}",
                 f"Regime: {regime.value} | VIX: {vix:.1f}", ""]
        for s in ranked:
            level = s.signal_level
            if level == "NO_SIGNAL":
                lines.append(f"  {s.symbol:6s} {s.quant_score:5.1f}  —")
            else:
                lines.append(f"  {s.symbol:6s} {s.quant_score:5.1f}  {level}")
        summary = "\n".join(lines)

        signal_section = ""
        for s in ranked:
            signal_section += (
                f"### {s.symbol}\n"
                f"- Quant Score: {s.quant_score:.1f} → {s.signal_level}\n"
                f"- Advisor Bonus: {s.advisor_bonus:+.1f}\n\n"
            )

        full = (
            f"# {title} Briefing — {ts}\n\n"
            f"## Market\n"
            f"- Regime: {regime.value}\n"
            f"- VIX: {vix:.1f}\n\n"
            f"## Signals\n{signal_section}\n"
            f"## LLM Analysis\n{llm_text}\n"
        )
        return summary, full
