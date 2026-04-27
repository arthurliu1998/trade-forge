# Auto Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance TradeMonitor to automatically trigger LLM deep analysis on signals, generate scheduled briefings, scrape news with FinBERT sentiment, and detect critical events — all without manual user input.

**Architecture:** Single-process enhancement of existing `TradeMonitor`. New `AnalysisPipeline` orchestrates `QuantScanner` → `LLMRouter` → `ReportBuilder` → Telegram/local storage. Two switchable modes (Lite/Full) via `config.yaml`. Non-blocking via `asyncio.create_task()`.

**Tech Stack:** Python 3.10+, asyncio, feedparser (RSS), transformers + torch (FinBERT), existing quantforge modules (QuantScanner, LLMRouter, TelegramNotifier).

**Spec:** `docs/superpowers/specs/2026-04-27-auto-monitor-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|----------------|
| `quantforge/monitor/report_store.py` | Save markdown reports to `~/.quantforge/reports/<date>/`, auto-cleanup |
| `quantforge/monitor/report_builder.py` | Format QuantSignal + LLM result → Telegram summary + full markdown report |
| `quantforge/monitor/pipeline.py` | AnalysisPipeline — orchestrate scoring → LLM → report → notify |
| `quantforge/monitor/news_scraper.py` | Fetch news from 6 RSS sources, filter by watchlist symbols |
| `quantforge/monitor/event_detector.py` | Detect critical events from price changes + news, manage cooldowns |
| `quantforge/finbert/__init__.py` | Package init |
| `quantforge/finbert/analyzer.py` | FinBERT model wrapper — score single text or batch |
| `quantforge/finbert/download.py` | CLI entry point to download FinBERT model |
| `tests/test_report_store.py` | Tests for ReportStore |
| `tests/test_report_builder.py` | Tests for ReportBuilder |
| `tests/test_pipeline.py` | Tests for AnalysisPipeline (update existing file) |
| `tests/test_news_scraper.py` | Tests for NewsScraper |
| `tests/test_event_detector.py` | Tests for EventDetector |
| `tests/test_finbert.py` | Tests for FinBERTAnalyzer |

### Modified Files

| File | Changes |
|------|---------|
| `quantforge/monitor/monitor.py` | Add mode switching, briefing_loop, event_detector_loop, startup self-check, integrate AnalysisPipeline |
| `quantforge/monitor/scanner.py` | Accept optional FinBERT scores to feed into sentiment factor |
| `quantforge/config.py` | Validate new `monitor` config section |
| `config.yaml.example` | Add `monitor` section with all new fields |
| `requirements.txt` | Add transformers, torch, feedparser |
| `install.sh` | Add FinBERT model download step |
| `tests/test_monitor.py` | Add tests for new monitor modes and startup |

---

## Task 1: Config Foundation

**Files:**
- Modify: `config.yaml.example`
- Modify: `quantforge/config.py`
- Modify: `requirements.txt`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write test for new monitor config validation**

```python
# tests/test_config.py — add to existing file

class TestMonitorConfig:
    def test_valid_monitor_config(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
watchlist:
  US: [AAPL]
  TW: ["2330"]
signals:
  ma_crossover: [20, 60]
monitor:
  monitor_mode: full
  scan_interval_minutes: 15
  briefing_timezone: "Asia/Taipei"
  briefing_schedule: ["08:30", "14:00", "21:00"]
  cooldown:
    same_symbol_minutes: 120
    daily_recalc_limit: 5
""")
        from quantforge.config import load_config
        config = load_config(str(cfg))
        assert config["monitor"]["monitor_mode"] == "full"
        assert config["monitor"]["scan_interval_minutes"] == 15

    def test_missing_monitor_section_uses_defaults(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("watchlist:\n  US: [AAPL]\n")
        from quantforge.config import load_config
        config = load_config(str(cfg))
        assert "monitor" not in config  # no monitor section is valid

    def test_invalid_monitor_mode_rejected(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("""
watchlist:
  US: [AAPL]
monitor:
  monitor_mode: turbo
""")
        from quantforge.config import load_config, validate_monitor_config
        config = load_config(str(cfg))
        validated = validate_monitor_config(config.get("monitor", {}))
        assert validated["monitor_mode"] == "lite"  # fallback
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd . && python -m pytest tests/test_config.py::TestMonitorConfig -v`
Expected: FAIL — `validate_monitor_config` does not exist

- [ ] **Step 3: Add `validate_monitor_config` to config.py**

```python
# quantforge/config.py — add after existing code

MONITOR_DEFAULTS = {
    "monitor_mode": "lite",
    "scan_interval_minutes": 15,
    "briefing_timezone": "Asia/Taipei",
    "briefing_schedule": ["08:30", "14:00", "21:00"],
    "cooldown": {
        "same_symbol_minutes": 120,
        "daily_recalc_limit": 5,
    },
    "event_detector": {
        "finbert_threshold_pos": 0.9,
        "finbert_threshold_neg": -0.85,
        "keywords": ["earnings", "merger", "investigation", "delisting", "upgrade", "downgrade"],
        "article_cluster_count": 3,
        "article_cluster_window_min": 15,
    },
    "reports": {
        "retention_days": 30,
        "output_dir": "~/.quantforge/reports",
    },
}

VALID_MODES = ("lite", "full")


def validate_monitor_config(monitor_cfg: dict) -> dict:
    """Validate and fill defaults for monitor config section."""
    result = {}
    for key, default in MONITOR_DEFAULTS.items():
        result[key] = monitor_cfg.get(key, default)

    if result["monitor_mode"] not in VALID_MODES:
        result["monitor_mode"] = "lite"

    if not isinstance(result["scan_interval_minutes"], (int, float)):
        result["scan_interval_minutes"] = 15

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd . && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Update config.yaml.example**

Add monitor section to `config.yaml.example`:
```yaml
# --- existing content stays ---

monitor:
  monitor_mode: lite              # lite | full
  scan_interval_minutes: 15
  briefing_timezone: "Asia/Taipei"
  briefing_schedule:
    - "08:30"
    - "14:00"
    - "21:00"
  cooldown:
    same_symbol_minutes: 120
    daily_recalc_limit: 5
  event_detector:
    finbert_threshold_pos: 0.9
    finbert_threshold_neg: -0.85
    keywords:
      - earnings
      - merger
      - investigation
      - delisting
      - upgrade
      - downgrade
    article_cluster_count: 3
    article_cluster_window_min: 15
  reports:
    retention_days: 30
    output_dir: "~/.quantforge/reports"
```

- [ ] **Step 6: Update requirements.txt**

Add to `requirements.txt`:
```
transformers>=4.30
torch>=2.0
feedparser>=6.0
```

- [ ] **Step 7: Commit**

```bash
git add quantforge/config.py config.yaml.example requirements.txt tests/test_config.py
git commit -m "feat: add monitor config validation with Lite/Full mode support"
```

---

## Task 2: ReportStore

**Files:**
- Create: `quantforge/monitor/report_store.py`
- Test: `tests/test_report_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_report_store.py
import os
from datetime import datetime
from quantforge.monitor.report_store import ReportStore


class TestReportStore:
    def test_save_creates_date_directory(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path))
        store.save("signal", "NVDA", "# Report content")
        today = datetime.now().strftime("%Y-%m-%d")
        assert (tmp_path / today).is_dir()

    def test_save_creates_markdown_file(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path))
        path = store.save("signal", "NVDA", "# Report content")
        assert path.endswith(".md")
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "# Report content"

    def test_save_filename_contains_symbol_and_type(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path))
        path = store.save("signal", "NVDA", "content")
        filename = os.path.basename(path)
        assert "NVDA" in filename
        assert "signal" in filename

    def test_save_briefing_no_symbol(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path))
        path = store.save("briefing", "tw-premarket", "# Briefing")
        filename = os.path.basename(path)
        assert "briefing" in filename
        assert "tw-premarket" in filename

    def test_cleanup_removes_old_directories(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path), retention_days=0)
        # Create a fake old directory
        old_dir = tmp_path / "2020-01-01"
        old_dir.mkdir()
        (old_dir / "report.md").write_text("old")
        store.cleanup()
        assert not old_dir.exists()

    def test_cleanup_keeps_recent_directories(self, tmp_path):
        store = ReportStore(base_dir=str(tmp_path), retention_days=30)
        today = datetime.now().strftime("%Y-%m-%d")
        today_dir = tmp_path / today
        today_dir.mkdir()
        (today_dir / "report.md").write_text("recent")
        store.cleanup()
        assert today_dir.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd . && python -m pytest tests/test_report_store.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement ReportStore**

```python
# quantforge/monitor/report_store.py
"""Save analysis reports to local filesystem with auto-cleanup."""
import logging
import os
import shutil
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ReportStore:
    def __init__(self, base_dir: str = "~/.quantforge/reports",
                 retention_days: int = 30):
        self.base_dir = os.path.expanduser(base_dir)
        self.retention_days = retention_days

    def save(self, report_type: str, label: str, content: str) -> str:
        """Save a report to disk.

        Args:
            report_type: "signal", "briefing", or "recalc"
            label: symbol name or briefing type (e.g., "NVDA", "tw-premarket")
            content: full markdown report content

        Returns:
            Absolute path to saved file.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H%M%S")
        day_dir = os.path.join(self.base_dir, today)
        os.makedirs(day_dir, exist_ok=True)

        filename = f"{label}-{time_str}-{report_type}.md"
        filepath = os.path.join(day_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)
        logger.info("Report saved: %s", filepath)
        return filepath

    def cleanup(self) -> int:
        """Remove report directories older than retention_days.

        Returns:
            Number of directories removed.
        """
        if not os.path.exists(self.base_dir):
            return 0
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        removed = 0
        for name in os.listdir(self.base_dir):
            dir_path = os.path.join(self.base_dir, name)
            if not os.path.isdir(dir_path):
                continue
            try:
                dir_date = datetime.strptime(name, "%Y-%m-%d")
                if dir_date < cutoff:
                    shutil.rmtree(dir_path)
                    logger.info("Cleaned up old reports: %s", name)
                    removed += 1
            except ValueError:
                continue
        return removed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd . && python -m pytest tests/test_report_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantforge/monitor/report_store.py tests/test_report_store.py
git commit -m "feat: add ReportStore for local report persistence with auto-cleanup"
```

---

## Task 3: ReportBuilder

**Files:**
- Create: `quantforge/monitor/report_builder.py`
- Test: `tests/test_report_builder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_report_builder.py
from quantforge.monitor.report_builder import ReportBuilder
from quantforge.core.models import QuantSignal, EdgeScores, FactorScore, Regime


def _make_signal(symbol="NVDA", quant_score=78.5, advisor_bonus=6.2,
                 regime=Regime.BULL_TREND) -> QuantSignal:
    edge = EdgeScores(
        technical=FactorScore("technical", 3.0, 0.75, 0.45),
        chipflow=None,
        crossmarket=FactorScore("crossmarket", 1.0, 0.50, 0.20),
        sentiment=FactorScore("sentiment", 0.64, 0.82, 0.35),
    )
    return QuantSignal(
        symbol=symbol, market="US", quant_score=quant_score,
        advisor_bonus=advisor_bonus, regime=regime,
        edge_scores=edge, timestamp="2026-04-27T08:35:00",
    )


class TestReportBuilder:
    def test_build_signal_returns_summary_and_full(self):
        signal = _make_signal()
        llm_result = {"content": "Strong data center demand.", "_provider": "claude"}
        summary, full = ReportBuilder.build_signal(signal, llm_result, trigger="MA20 crossover up")
        assert isinstance(summary, str)
        assert isinstance(full, str)

    def test_summary_contains_symbol_and_score(self):
        signal = _make_signal()
        llm_result = {"content": "Analysis text.", "_provider": "claude"}
        summary, _ = ReportBuilder.build_signal(signal, llm_result, trigger="RSI oversold")
        assert "NVDA" in summary
        assert "78.5" in summary

    def test_full_report_contains_all_sections(self):
        signal = _make_signal()
        llm_result = {"content": "Detailed analysis.", "_provider": "claude"}
        _, full = ReportBuilder.build_signal(signal, llm_result, trigger="RSI oversold")
        assert "# NVDA Analysis Report" in full
        assert "Edge Scores" in full
        assert "Regime" in full
        assert "LLM Analysis" in full
        assert "Detailed analysis." in full

    def test_summary_short_enough_for_telegram(self):
        signal = _make_signal()
        llm_result = {"content": "Short.", "_provider": "claude"}
        summary, _ = ReportBuilder.build_signal(signal, llm_result, trigger="test")
        lines = summary.strip().split("\n")
        assert len(lines) <= 5

    def test_build_signal_without_llm(self):
        signal = _make_signal()
        summary, full = ReportBuilder.build_signal(signal, llm_result=None, trigger="test")
        assert "NVDA" in summary
        assert "N/A" in full or "No LLM" in full

    def test_build_briefing(self):
        signals = [_make_signal("NVDA", 78.5), _make_signal("AAPL", 65.0)]
        llm_result = {"content": "Market overview text.", "_provider": "claude"}
        summary, full = ReportBuilder.build_briefing(
            "tw_premarket", signals, regime=Regime.BULL_TREND,
            vix=18.2, llm_result=llm_result,
        )
        assert "NVDA" in summary
        assert "AAPL" in summary
        assert "BULL_TREND" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd . && python -m pytest tests/test_report_builder.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement ReportBuilder**

```python
# quantforge/monitor/report_builder.py
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
        """Build Telegram summary + full markdown report for a signal.

        Returns:
            (summary, full_report) tuple of strings.
        """
        level = signal.signal_level
        llm_text = llm_result["content"] if llm_result else "No LLM analysis"
        provider = llm_result.get("_provider", "N/A") if llm_result else "N/A"

        # Telegram short summary (3-5 lines)
        llm_oneliner = llm_text[:80].replace("\n", " ")
        summary = (
            f"{signal.symbol} — {level} "
            f"(Quant: {signal.quant_score} + Advisor: {signal.advisor_bonus:+.1f})\n"
            f"Regime: {signal.regime.value} | "
            f"Trigger: {trigger}\n"
            f"LLM: {llm_oneliner}"
        )

        # Full markdown report
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
        """Build Telegram summary + full report for a scheduled briefing.

        Returns:
            (summary, full_report) tuple of strings.
        """
        title = BRIEFING_TITLES.get(briefing_type, briefing_type)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        llm_text = llm_result["content"] if llm_result else "No LLM analysis"

        # Sort by quant_score descending
        ranked = sorted(signals, key=lambda s: s.quant_score, reverse=True)

        # Telegram summary
        lines = [f"QuantForge {title} — {ts}",
                 f"Regime: {regime.value} | VIX: {vix:.1f}", ""]
        for s in ranked:
            level = s.signal_level
            if level == "NO_SIGNAL":
                lines.append(f"  {s.symbol:6s} {s.quant_score:5.1f}  —")
            else:
                lines.append(f"  {s.symbol:6s} {s.quant_score:5.1f}  {level}")
        summary = "\n".join(lines)

        # Full report
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd . && python -m pytest tests/test_report_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantforge/monitor/report_builder.py tests/test_report_builder.py
git commit -m "feat: add ReportBuilder for Telegram summaries and full markdown reports"
```

---

## Task 4: FinBERT Analyzer

**Files:**
- Create: `quantforge/finbert/__init__.py`
- Create: `quantforge/finbert/analyzer.py`
- Create: `quantforge/finbert/download.py`
- Test: `tests/test_finbert.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_finbert.py
import pytest
from unittest.mock import patch, MagicMock
from quantforge.finbert.analyzer import FinBERTAnalyzer, ScoredArticle


class TestFinBERTAnalyzer:
    def test_score_returns_float_in_range(self):
        """Mock the model to test scoring logic."""
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
        """Negative articles should be weighted 1.5x in batch mode."""
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd . && python -m pytest tests/test_finbert.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create finbert package init**

```python
# quantforge/finbert/__init__.py
```

- [ ] **Step 4: Implement FinBERTAnalyzer**

```python
# quantforge/finbert/analyzer.py
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
```

- [ ] **Step 5: Implement download CLI**

```python
# quantforge/finbert/download.py
"""CLI to pre-download FinBERT model."""

def main():
    print("Downloading ProsusAI/finbert model (~400MB)...")
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        AutoTokenizer.from_pretrained("ProsusAI/finbert")
        AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
        print("FinBERT model downloaded successfully.")
    except Exception as e:
        print(f"Download failed: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd . && python -m pytest tests/test_finbert.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add quantforge/finbert/__init__.py quantforge/finbert/analyzer.py quantforge/finbert/download.py tests/test_finbert.py
git commit -m "feat: add FinBERT sentiment analyzer with lazy loading and batch scoring"
```

---

## Task 5: NewsScraper

**Files:**
- Create: `quantforge/monitor/news_scraper.py`
- Test: `tests/test_news_scraper.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_news_scraper.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from quantforge.monitor.news_scraper import NewsScraper, Article


class TestNewsScraper:
    def test_article_dataclass(self):
        a = Article(title="Test", text="Content", symbol="AAPL",
                    source="yahoo", url="http://example.com",
                    published="2026-04-27T08:00:00")
        assert a.symbol == "AAPL"
        assert a.source == "yahoo"

    def test_match_symbols_filters_by_watchlist(self):
        scraper = NewsScraper.__new__(NewsScraper)
        scraper.symbols = ["AAPL", "NVDA", "2330"]
        entries = [
            {"title": "AAPL earnings beat", "summary": "Apple reported...", "link": "http://a.com", "published": "now"},
            {"title": "Random stock news", "summary": "Nothing relevant", "link": "http://b.com", "published": "now"},
            {"title": "NVDA surges", "summary": "NVIDIA up 5%", "link": "http://c.com", "published": "now"},
        ]
        matched = scraper._match_symbols(entries)
        assert len(matched) == 2
        symbols = [a.symbol for a in matched]
        assert "AAPL" in symbols
        assert "NVDA" in symbols

    @pytest.mark.asyncio
    async def test_fetch_source_returns_articles(self):
        scraper = NewsScraper.__new__(NewsScraper)
        scraper.symbols = ["AAPL"]
        fake_feed = MagicMock()
        fake_feed.entries = [
            {"title": "AAPL up", "summary": "Apple rises", "link": "http://x.com", "published": "now"},
        ]
        with patch("quantforge.monitor.news_scraper.feedparser.parse", return_value=fake_feed):
            articles = await scraper._fetch_source("yahoo_finance", "http://example.com/rss")
        assert len(articles) == 1
        assert articles[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_fetch_all_aggregates_sources(self):
        scraper = NewsScraper(symbols=["AAPL"])
        with patch.object(scraper, "_fetch_source", new_callable=AsyncMock) as mock:
            mock.return_value = [
                Article("T", "C", "AAPL", "yahoo", "http://x.com", "now"),
            ]
            articles = await scraper.fetch_all()
        assert len(articles) >= 1  # at least from one source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd . && python -m pytest tests/test_news_scraper.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement NewsScraper**

```python
# quantforge/monitor/news_scraper.py
"""Fetch news from 6 RSS sources, filter for watchlist symbols."""
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import feedparser

logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    text: str
    symbol: str
    source: str
    url: str
    published: str


# RSS source URLs — some may need adjustment for actual feeds
SOURCES = [
    ("yahoo_finance", "https://finance.yahoo.com/news/rssindex"),
    ("finviz", "https://finviz.com/news_export.ashx?v=3"),
    ("google_news", "https://news.google.com/rss/search?q=stock+market"),
    ("cnyes", "https://news.cnyes.com/rss"),
    ("moneydj", "https://www.moneydj.com/rss/rsscategory.djrss?a=latest"),
    ("twse", "https://mops.twse.com.tw/mops/web/ajax_t05st01"),
]


class NewsScraper:
    """Fetch and filter news articles from multiple RSS sources."""

    def __init__(self, symbols: list[str] = None, sources: list[tuple] = None):
        self.symbols = [s.upper() for s in (symbols or [])]
        self.sources = sources or SOURCES

    async def fetch_all(self) -> list[Article]:
        """Fetch from all sources in parallel, filter for watchlist symbols."""
        tasks = [
            self._fetch_source(name, url)
            for name, url in self.sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Source fetch failed: %s", type(result).__name__)
                continue
            articles.extend(result)
        return articles

    async def _fetch_source(self, source_name: str, url: str) -> list[Article]:
        """Fetch and parse a single RSS source."""
        try:
            feed = await asyncio.to_thread(feedparser.parse, url)
            entries = feed.entries if hasattr(feed, "entries") else []
            return self._match_symbols(entries, source_name)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", source_name, type(e).__name__)
            return []

    def _match_symbols(self, entries: list, source_name: str = "") -> list[Article]:
        """Filter RSS entries to those mentioning watchlist symbols."""
        articles = []
        for entry in entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            combined = f"{title} {summary}".upper()
            for sym in self.symbols:
                if sym in combined:
                    articles.append(Article(
                        title=title,
                        text=summary,
                        symbol=sym,
                        source=source_name,
                        url=entry.get("link", ""),
                        published=entry.get("published", ""),
                    ))
                    break  # one article matches one symbol
        return articles
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd . && python -m pytest tests/test_news_scraper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantforge/monitor/news_scraper.py tests/test_news_scraper.py
git commit -m "feat: add NewsScraper with 6-source RSS fetching and symbol filtering"
```

---

## Task 6: EventDetector

**Files:**
- Create: `quantforge/monitor/event_detector.py`
- Test: `tests/test_event_detector.py`

- [ ] **Step 1: Write failing tests**

```python
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
        # Second call within cooldown window — should be blocked
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
                assert len(events) == 0  # daily limit reached
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd . && python -m pytest tests/test_event_detector.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement EventDetector**

```python
# quantforge/monitor/event_detector.py
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
    trigger: str  # finbert_extreme, keyword, article_cluster, score_delta, regime_change, vix_crisis
    detail: str
    timestamp: str


class EventDetector:
    """Detect critical events that warrant instant edge recalculation."""

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
        self._cooldowns: dict[str, datetime] = {}  # symbol -> last trigger time
        self._daily_count: int = 0
        self._daily_reset_date: Optional[datetime] = None

    def detect_from_news(self, scored_articles: list[ScoredArticle]) -> list[CriticalEvent]:
        """Detect critical events from scored news articles."""
        events = []
        now = datetime.now()

        for article in scored_articles:
            # FinBERT extreme score
            if article.sentiment >= self.finbert_pos or article.sentiment <= self.finbert_neg:
                event = CriticalEvent(
                    symbol=article.symbol, trigger="finbert_extreme",
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
                        symbol=article.symbol, trigger="keyword",
                        detail=f"Keyword '{kw}': {article.text[:60]}",
                        timestamp=now.isoformat(),
                    )
                    if self._cooldown_ok(article.symbol):
                        events.append(event)
                    break

        # Article cluster detection
        symbol_articles: dict[str, list] = {}
        for a in scored_articles:
            symbol_articles.setdefault(a.symbol, []).append(a)

        for symbol, arts in symbol_articles.items():
            if len(arts) >= self.cluster_count:
                directions = [1 if a.sentiment > 0 else -1 for a in arts]
                if abs(sum(directions)) == len(directions):  # all same direction
                    event = CriticalEvent(
                        symbol=symbol, trigger="article_cluster",
                        detail=f"{len(arts)} same-direction articles",
                        timestamp=now.isoformat(),
                    )
                    if self._cooldown_ok(symbol):
                        events.append(event)

        return events

    def detect_from_scores(self, current_scores: dict[str, float]) -> list[CriticalEvent]:
        """Detect score delta events by comparing with last scan."""
        events = []
        now = datetime.now()
        for symbol, score in current_scores.items():
            prev = self._last_scores.get(symbol)
            if prev is not None and abs(score - prev) > SCORE_DELTA_THRESHOLD:
                event = CriticalEvent(
                    symbol=symbol, trigger="score_delta",
                    detail=f"Score changed {prev:.1f} → {score:.1f} (delta={score-prev:+.1f})",
                    timestamp=now.isoformat(),
                )
                if self._cooldown_ok(symbol):
                    events.append(event)
        self._last_scores = dict(current_scores)
        return events

    def detect_regime_change(self, current_regime: Regime,
                             vix: float) -> list[CriticalEvent]:
        """Detect regime transitions and VIX crisis."""
        events = []
        now = datetime.now()

        if current_regime == Regime.CRISIS and vix > 30:
            events.append(CriticalEvent(
                symbol="MARKET", trigger="vix_crisis",
                detail=f"VIX={vix:.1f} — crisis mode",
                timestamp=now.isoformat(),
            ))

        if (self._last_regime is not None
                and current_regime != self._last_regime
                and current_regime != Regime.CRISIS):
            events.append(CriticalEvent(
                symbol="MARKET", trigger="regime_change",
                detail=f"{self._last_regime.value} → {current_regime.value}",
                timestamp=now.isoformat(),
            ))

        self._last_regime = current_regime
        return events

    def _cooldown_ok(self, symbol: str) -> bool:
        """Check if symbol is past cooldown and daily limit not exceeded."""
        now = datetime.now()

        # Reset daily counter at midnight
        today = now.date()
        if self._daily_reset_date is None or self._daily_reset_date != today:
            self._daily_count = 0
            self._daily_reset_date = today

        # Daily limit
        if self._daily_count >= self.daily_limit:
            logger.info("Daily recalc limit reached (%d)", self.daily_limit)
            return False

        # Per-symbol cooldown
        last = self._cooldowns.get(symbol)
        if last and (now - last) < timedelta(minutes=self.cooldown_minutes):
            logger.debug("Cooldown active for %s", symbol)
            return False

        self._cooldowns[symbol] = now
        self._daily_count += 1
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd . && python -m pytest tests/test_event_detector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantforge/monitor/event_detector.py tests/test_event_detector.py
git commit -m "feat: add EventDetector with news/price/regime triggers and cooldown"
```

---

## Task 7: AnalysisPipeline

**Files:**
- Create: `quantforge/monitor/pipeline.py`
- Test: `tests/test_pipeline.py` (overwrite — current file tests old pipeline)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from quantforge.monitor.pipeline import AnalysisPipeline
from quantforge.core.models import QuantSignal, EdgeScores, FactorScore, Regime
from quantforge.signals.engine import Signal


def _make_quant_signal(symbol="NVDA", score=78.5):
    edge = EdgeScores(
        technical=FactorScore("technical", 3.0, 0.75, 0.45),
        chipflow=None,
        crossmarket=FactorScore("crossmarket", 1.0, 0.50, 0.20),
        sentiment=FactorScore("sentiment", 0.64, 0.82, 0.35),
    )
    return QuantSignal(symbol=symbol, market="US", quant_score=score,
                       advisor_bonus=0.0, regime=Regime.BULL_TREND,
                       edge_scores=edge, timestamp="2026-04-27T08:35:00")


@pytest.fixture
def config():
    return {
        "watchlist": {"US": ["NVDA", "AAPL"], "TW": []},
        "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                     "rsi_overbought": 80, "rsi_oversold": 20},
        "monitor": {
            "monitor_mode": "lite",
            "reports": {"output_dir": "/tmp/qf-test-reports", "retention_days": 1},
        },
    }


class TestAnalysisPipeline:
    def test_should_analyze_high_signal(self, config):
        pipeline = AnalysisPipeline(config, notifier=MagicMock(),
                                     llm_router=MagicMock())
        signal = Signal("NVDA", "rsi_oversold", "HIGH", "RSI low")
        assert pipeline._should_analyze(signal) is True

    def test_should_analyze_critical_signal(self, config):
        pipeline = AnalysisPipeline(config, notifier=MagicMock(),
                                     llm_router=MagicMock())
        signal = Signal("NVDA", "test", "CRITICAL", "test")
        assert pipeline._should_analyze(signal) is True

    def test_should_not_analyze_medium_signal(self, config):
        pipeline = AnalysisPipeline(config, notifier=MagicMock(),
                                     llm_router=MagicMock())
        signal = Signal("NVDA", "test", "MEDIUM", "test")
        assert pipeline._should_analyze(signal) is False

    def test_should_not_analyze_low_signal(self, config):
        pipeline = AnalysisPipeline(config, notifier=MagicMock(),
                                     llm_router=MagicMock())
        signal = Signal("NVDA", "test", "LOW", "test")
        assert pipeline._should_analyze(signal) is False

    @pytest.mark.asyncio
    async def test_run_calls_llm_on_high_signal(self, config):
        notifier = MagicMock()
        notifier.send_text = MagicMock(return_value=True)
        llm = MagicMock()
        llm.has_providers = MagicMock(return_value=True)
        llm.analyze = AsyncMock(return_value={"content": "Analysis", "_provider": "claude"})

        pipeline = AnalysisPipeline(config, notifier=notifier, llm_router=llm)
        pipeline._score_symbol = MagicMock(return_value=_make_quant_signal())

        signal = Signal("NVDA", "rsi_oversold", "HIGH", "RSI low")
        await pipeline.run(signal)

        llm.analyze.assert_called_once()
        notifier.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_skips_llm_on_medium_signal(self, config):
        notifier = MagicMock()
        llm = MagicMock()
        llm.analyze = AsyncMock()

        pipeline = AnalysisPipeline(config, notifier=notifier, llm_router=llm)
        signal = Signal("NVDA", "test", "MEDIUM", "test")
        await pipeline.run(signal)

        llm.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_briefing(self, config):
        notifier = MagicMock()
        notifier.send_text = MagicMock(return_value=True)
        llm = MagicMock()
        llm.has_providers = MagicMock(return_value=True)
        llm.analyze = AsyncMock(return_value={"content": "Briefing", "_provider": "claude"})

        pipeline = AnalysisPipeline(config, notifier=notifier, llm_router=llm)
        pipeline._score_symbol = MagicMock(return_value=_make_quant_signal())

        await pipeline.run_briefing("tw_premarket")
        llm.analyze.assert_called_once()
        notifier.send_text.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd . && python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement AnalysisPipeline**

```python
# quantforge/monitor/pipeline.py
"""AnalysisPipeline: orchestrates signal → scoring → LLM → report → notify."""
import asyncio
import logging
from typing import Optional

from quantforge.core.models import QuantSignal, Regime
from quantforge.data.yfinance_provider import YFinanceProvider
from quantforge.monitor.report_builder import ReportBuilder
from quantforge.monitor.report_store import ReportStore
from quantforge.notify.telegram import TelegramNotifier
from quantforge.providers.router import LLMRouter
from quantforge.regime.detector import RegimeDetector
from quantforge.scanner import QuantScanner
from quantforge.signals.engine import Signal

logger = logging.getLogger(__name__)

SIGNAL_ANALYSIS_PROMPT = """You are a quantitative trading analyst. Analyze the following stock signal data and provide:
1. Event interpretation — what is driving this signal
2. Risk factors — what could go wrong
3. Confidence assessment — how reliable is this signal
Keep your analysis concise (under 200 words). Use percentages, not absolute dollar amounts."""

BRIEFING_PROMPT = """You are a market briefing analyst. Given the following watchlist scores and market regime data, produce a concise pre-market briefing:
1. Market environment summary (2-3 sentences)
2. Top opportunities with reasoning
3. Key risks to watch today
Keep it under 300 words. Use percentages, not absolute dollar amounts."""


class AnalysisPipeline:
    """Orchestrate scoring → LLM analysis → report generation → notification."""

    def __init__(self, config: dict, notifier: TelegramNotifier,
                 llm_router: LLMRouter, finbert=None):
        self.config = config
        self.notifier = notifier
        self.llm = llm_router
        self.finbert = finbert
        self.scanner = QuantScanner()
        self.data_provider = YFinanceProvider()
        self.regime_detector = RegimeDetector()

        monitor_cfg = config.get("monitor", {})
        reports_cfg = monitor_cfg.get("reports", {})
        self.report_store = ReportStore(
            base_dir=reports_cfg.get("output_dir", "~/.quantforge/reports"),
            retention_days=reports_cfg.get("retention_days", 30),
        )
        self._semaphore = asyncio.Semaphore(3)

    def _should_analyze(self, signal: Signal) -> bool:
        """Only analyze HIGH and CRITICAL signals."""
        return signal.priority in ("HIGH", "CRITICAL")

    def _score_symbol(self, symbol: str, market: str = "US",
                      sentiment_data: dict = None) -> Optional[QuantSignal]:
        """Run QuantScanner on a single symbol."""
        try:
            ohlcv = self.data_provider.get_ohlcv(symbol, period="6mo")
            if ohlcv.empty:
                return None
            return self.scanner.score_stock(
                symbol=symbol, market=market, ohlcv=ohlcv,
                sentiment_data=sentiment_data,
            )
        except Exception as e:
            logger.error("Scoring failed for %s: %s", symbol, type(e).__name__)
            return None

    async def run(self, signal: Signal) -> None:
        """Analyze a detected signal: score → LLM → report → notify."""
        if not self._should_analyze(signal):
            return

        async with self._semaphore:
            logger.info("Analyzing signal: [%s] %s %s",
                        signal.priority, signal.symbol, signal.type)

            market = self._detect_market(signal.symbol)
            quant_signal = self._score_symbol(signal.symbol, market)
            if quant_signal is None:
                logger.warning("Could not score %s — skipping", signal.symbol)
                return

            llm_result = None
            if self.llm and self.llm.has_providers():
                try:
                    llm_result = await self.llm.analyze(SIGNAL_ANALYSIS_PROMPT, {
                        "symbol": signal.symbol,
                        "signal_type": signal.type,
                        "quant_score": quant_signal.quant_score,
                        "regime": quant_signal.regime.value,
                        "signal_level": quant_signal.signal_level,
                    })
                except Exception as e:
                    logger.warning("LLM analysis failed: %s", type(e).__name__)

            summary, full = ReportBuilder.build_signal(
                quant_signal, llm_result, trigger=signal.type)
            self.report_store.save("signal", signal.symbol, full)
            self.notifier.send_text(summary)
            logger.info("Analysis complete for %s: %s",
                        signal.symbol, quant_signal.signal_level)

    async def run_briefing(self, briefing_type: str) -> None:
        """Generate scheduled briefing for all watchlist symbols."""
        async with self._semaphore:
            logger.info("Generating %s briefing", briefing_type)
            watchlist = self.config.get("watchlist", {})
            all_symbols = [(s, "US") for s in watchlist.get("US", [])]
            all_symbols += [(s, "TW") for s in watchlist.get("TW", [])]

            signals = []
            for symbol, market in all_symbols:
                qs = self._score_symbol(symbol, market)
                if qs:
                    signals.append(qs)

            regime = signals[0].regime if signals else Regime.NEUTRAL
            vix = 15.0  # default; will be fetched from data in production

            llm_result = None
            if self.llm and self.llm.has_providers():
                try:
                    llm_result = await self.llm.analyze(BRIEFING_PROMPT, {
                        "briefing_type": briefing_type,
                        "regime": regime.value,
                        "vix": vix,
                        "signals": [
                            {"symbol": s.symbol, "score": s.quant_score,
                             "level": s.signal_level}
                            for s in signals
                        ],
                    })
                except Exception as e:
                    logger.warning("LLM briefing failed: %s", type(e).__name__)

            summary, full = ReportBuilder.build_briefing(
                briefing_type, signals, regime, vix, llm_result)
            self.report_store.save("briefing", briefing_type, full)
            self.notifier.send_text(summary)
            logger.info("Briefing %s complete", briefing_type)

    async def run_recalc(self, symbol: str, trigger: str) -> None:
        """Instant edge recalculation — always runs full analysis."""
        async with self._semaphore:
            logger.info("Instant recalc for %s (trigger: %s)", symbol, trigger)
            market = self._detect_market(symbol)
            quant_signal = self._score_symbol(symbol, market)
            if quant_signal is None:
                return

            llm_result = None
            if self.llm and self.llm.has_providers():
                try:
                    llm_result = await self.llm.analyze(SIGNAL_ANALYSIS_PROMPT, {
                        "symbol": symbol,
                        "signal_type": f"recalc:{trigger}",
                        "quant_score": quant_signal.quant_score,
                        "regime": quant_signal.regime.value,
                        "signal_level": quant_signal.signal_level,
                    })
                except Exception as e:
                    logger.warning("LLM recalc failed: %s", type(e).__name__)

            summary, full = ReportBuilder.build_signal(
                quant_signal, llm_result, trigger=f"recalc:{trigger}")
            self.report_store.save("recalc", symbol, full)
            self.notifier.send_text(summary)

    def _detect_market(self, symbol: str) -> str:
        """Detect if symbol is US or TW based on watchlist config."""
        tw_list = self.config.get("watchlist", {}).get("TW", [])
        return "TW" if symbol in tw_list else "US"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd . && python -m pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantforge/monitor/pipeline.py tests/test_pipeline.py
git commit -m "feat: add AnalysisPipeline orchestrating scoring → LLM → report → notify"
```

---

## Task 8: Enhanced TradeMonitor

**Files:**
- Modify: `quantforge/monitor/monitor.py`
- Modify: `tests/test_monitor.py`

- [ ] **Step 1: Write failing tests for new monitor features**

```python
# tests/test_monitor.py — replace entire file
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from quantforge.monitor.monitor import TradeMonitor


@pytest.fixture
def lite_config():
    return {
        "watchlist": {"US": ["AAPL"], "TW": []},
        "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                     "rsi_overbought": 80, "rsi_oversold": 20},
        "notification": {"sensitivity": "medium"},
        "monitor": {
            "monitor_mode": "lite",
            "scan_interval_minutes": 15,
            "reports": {"output_dir": "/tmp/qf-test-reports", "retention_days": 1},
        },
    }


@pytest.fixture
def full_config():
    return {
        "watchlist": {"US": ["AAPL"], "TW": []},
        "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                     "rsi_overbought": 80, "rsi_oversold": 20},
        "notification": {"sensitivity": "medium"},
        "monitor": {
            "monitor_mode": "full",
            "scan_interval_minutes": 15,
            "briefing_timezone": "Asia/Taipei",
            "briefing_schedule": ["08:30", "14:00", "21:00"],
            "cooldown": {"same_symbol_minutes": 120, "daily_recalc_limit": 5},
            "event_detector": {
                "finbert_threshold_pos": 0.9, "finbert_threshold_neg": -0.85,
                "keywords": ["earnings"], "article_cluster_count": 3,
                "article_cluster_window_min": 15,
            },
            "reports": {"output_dir": "/tmp/qf-test-reports", "retention_days": 1},
        },
    }


class TestTradeMonitorInit:
    def test_init_lite(self, lite_config):
        monitor = TradeMonitor(lite_config)
        assert monitor.mode == "lite"
        assert monitor.pipeline is not None

    def test_init_full_without_finbert_falls_back_to_lite(self, full_config):
        with patch("quantforge.monitor.monitor.FinBERTAnalyzer") as mock_fb:
            mock_fb.side_effect = Exception("no model")
            monitor = TradeMonitor(full_config)
            assert monitor.mode == "lite"

    def test_init_full_without_llm_falls_back_to_lite(self, full_config):
        with patch("quantforge.monitor.monitor.LLMRouter") as mock_llm:
            instance = mock_llm.return_value
            instance.has_providers.return_value = False
            monitor = TradeMonitor(full_config)
            assert monitor.mode == "lite"

    def test_scan_interval_from_config(self, lite_config):
        monitor = TradeMonitor(lite_config)
        assert monitor.scan_interval == 900  # 15 * 60


class TestTradeMonitorStartup:
    def test_startup_warnings_no_telegram(self, lite_config):
        monitor = TradeMonitor(lite_config)
        warnings = monitor._startup_check()
        telegram_warns = [w for w in warnings if "Telegram" in w]
        assert len(telegram_warns) > 0

    def test_startup_summary_format(self, lite_config):
        monitor = TradeMonitor(lite_config)
        summary = monitor._startup_summary()
        assert "QuantForge Monitor started" in summary
        assert "lite" in summary or "Lite" in summary


class TestTradeMonitorStop:
    @pytest.mark.asyncio
    async def test_stop(self, lite_config):
        monitor = TradeMonitor(lite_config)
        monitor._running = True
        await monitor.stop()
        assert monitor._running is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd . && python -m pytest tests/test_monitor.py -v`
Expected: FAIL — `monitor.mode` attribute, `_startup_check` etc. don't exist

- [ ] **Step 3: Rewrite monitor.py with mode switching and startup checks**

Replace the full content of `quantforge/monitor/monitor.py`:

```python
# quantforge/monitor/monitor.py
"""QuantForge Background Monitor — main entry point.

Modes:
  lite: Scan every 15 min. On HIGH/CRITICAL signal → LLM analysis.
  full: Lite + scheduled briefings + news scraping + FinBERT + event detection.

Usage:
    python -m quantforge.monitor.monitor --config ~/.quantforge/config.yaml
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

from quantforge.config import load_config, validate_monitor_config
from quantforge.monitor.secure_logger import setup_logging
from quantforge.monitor.scanner import WatchlistScanner
from quantforge.monitor.alpaca_stream import AlpacaStream
from quantforge.monitor.pipeline import AnalysisPipeline
from quantforge.monitor.report_store import ReportStore
from quantforge.notify.telegram import TelegramNotifier
from quantforge.providers.router import LLMRouter
from quantforge.secrets import SecretManager
from quantforge.safe_exceptions import install_exception_hooks

logger = logging.getLogger(__name__)


class TradeMonitor:
    """Background monitor with Lite/Full mode switching."""

    def __init__(self, config: dict):
        self.config = config
        monitor_cfg = validate_monitor_config(config.get("monitor", {}))
        self.requested_mode = monitor_cfg["monitor_mode"]
        self.scan_interval = monitor_cfg["scan_interval_minutes"] * 60
        self.briefing_schedule = monitor_cfg.get("briefing_schedule", [])
        self.briefing_tz = monitor_cfg.get("briefing_timezone", "Asia/Taipei")

        # Core components (always available)
        self.scanner = WatchlistScanner(config)
        self.alpaca = AlpacaStream()

        token = SecretManager.get("TELEGRAM_BOT_TOKEN")
        chat_id = SecretManager.get("TELEGRAM_CHAT_ID")
        sensitivity = config.get("notification", {}).get("sensitivity", "medium")
        self.notifier = TelegramNotifier(token, chat_id, sensitivity)

        # LLM router
        self.llm_router = LLMRouter()

        # FinBERT (Full mode only)
        self.finbert = None
        self.news_scraper = None
        self.event_detector = None

        # Determine actual mode (may downgrade from full → lite)
        self.mode = self._resolve_mode(monitor_cfg)

        # Analysis pipeline
        self.pipeline = AnalysisPipeline(
            config, notifier=self.notifier,
            llm_router=self.llm_router, finbert=self.finbert,
        )

        # Full mode components
        if self.mode == "full":
            self._init_full_mode(monitor_cfg)

        self._running = False
        self._briefing_fired: dict[str, str] = {}  # type -> date string

    def _resolve_mode(self, monitor_cfg: dict) -> str:
        """Check if full mode requirements are met, fallback to lite if not."""
        if self.requested_mode != "full":
            return "lite"

        # Full mode requires LLM
        if not self.llm_router.has_providers():
            logger.error(
                "Full mode requires LLM provider (Claude or Gemini). "
                "Set ANTHROPIC_API_KEY or GOOGLE_AI_API_KEY in ~/.quantforge/.env. "
                "Falling back to lite mode."
            )
            return "lite"

        # Full mode requires FinBERT
        try:
            from quantforge.finbert.analyzer import FinBERTAnalyzer
            self.finbert = FinBERTAnalyzer()
            self.finbert._load()
        except Exception:
            logger.error(
                "Full mode requires FinBERT model. "
                "Install: python -m quantforge.finbert.download. "
                "Or switch to lite mode: monitor_mode: lite. "
                "Falling back to lite mode."
            )
            self.finbert = None
            return "lite"

        return "full"

    def _init_full_mode(self, monitor_cfg: dict):
        """Initialize Full mode components: news scraper, event detector."""
        from quantforge.monitor.news_scraper import NewsScraper
        from quantforge.monitor.event_detector import EventDetector

        watchlist = self.config.get("watchlist", {})
        all_symbols = watchlist.get("US", []) + watchlist.get("TW", [])
        self.news_scraper = NewsScraper(symbols=all_symbols)

        event_cfg = monitor_cfg.get("event_detector", {})
        cooldown_cfg = monitor_cfg.get("cooldown", {})
        self.event_detector = EventDetector(event_cfg, cooldown_cfg)

    def _startup_check(self) -> list[str]:
        """Check all components and return warning messages."""
        warnings = []

        if not self.notifier.is_configured():
            warnings.append(
                "WARNING: Telegram not configured — alerts will only appear in logs. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in ~/.quantforge/.env"
            )

        if not self.llm_router.has_providers():
            warnings.append(
                "WARNING: No LLM provider available — running quant-only mode "
                "(no advisor analysis). "
                "Set ANTHROPIC_API_KEY in ~/.quantforge/.env"
            )

        if not self.alpaca.is_configured():
            warnings.append(
                "WARNING: Alpaca not configured — no real-time US streaming, "
                "using polling only. "
                "Set ALPACA_DATA_KEY and ALPACA_DATA_SECRET in ~/.quantforge/.env"
            )

        if self.requested_mode == "full" and self.mode == "lite":
            warnings.append(
                "WARNING: Requested full mode but requirements not met — "
                "running in lite mode."
            )

        return warnings

    def _startup_summary(self) -> str:
        """Generate startup summary message."""
        watchlist = self.config.get("watchlist", {})
        us_count = len(watchlist.get("US", []))
        tw_count = len(watchlist.get("TW", []))

        providers = self.llm_router.available_providers
        llm_status = f"LLM: {', '.join(providers)}" if providers else "LLM: none"

        lines = [
            f"QuantForge Monitor started ({self.mode} mode)",
            f"{'Y' if self.notifier.is_configured() else 'N'} Telegram",
            f"{'Y' if providers else 'N'} {llm_status}",
            f"{'Y' if self.finbert else 'N'} FinBERT",
            f"{'Y' if self.alpaca.is_configured() else 'N'} Alpaca real-time",
            f"Watchlist: {us_count} US + {tw_count} TW",
            f"Scan interval: {self.scan_interval // 60} min",
        ]
        return "\n".join(lines)

    async def run(self):
        """Start the monitor. Runs until stopped."""
        self._running = True

        # Startup checks
        for warning in self._startup_check():
            logger.warning(warning)

        summary = self._startup_summary()
        logger.info(summary)
        self.notifier.send_text(summary)

        # Cleanup old reports
        self.pipeline.report_store.cleanup()

        # Build task list
        tasks = [self._scheduled_loop()]

        if self.mode == "full":
            tasks.append(self._briefing_loop())
            tasks.append(self._event_detector_loop())

        if self.alpaca.is_configured():
            us_symbols = self.config.get("watchlist", {}).get("US", [])
            if us_symbols:
                self.alpaca.subscribe_bars(us_symbols, handler=self._on_realtime_bar)
                tasks.append(self.alpaca.run())

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Monitor shutting down...")
        finally:
            self._running = False
            await self.alpaca.stop()

    async def stop(self):
        self._running = False
        await self.alpaca.stop()

    async def _scheduled_loop(self):
        """Scan watchlist every scan_interval seconds."""
        while self._running:
            await self._run_scheduled_scan()
            await asyncio.sleep(self.scan_interval)

    async def _run_scheduled_scan(self):
        """Run full watchlist scan and trigger analysis on signals."""
        logger.info("Running scheduled watchlist scan...")
        try:
            signals = self.scanner.scan_all()
            if signals:
                logger.info("Found %d signals", len(signals))
                for signal in signals:
                    # Basic notification always
                    self.notifier.send_signal(signal)
                    # Trigger deep analysis for HIGH/CRITICAL
                    asyncio.create_task(self.pipeline.run(signal))
            else:
                logger.info("No signals detected")
        except Exception as e:
            logger.error("Scan error: %s", type(e).__name__)

    async def _briefing_loop(self):
        """Full mode: scheduled briefings at configured times."""
        while self._running:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")

            for scheduled_time in self.briefing_schedule:
                fire_key = f"{scheduled_time}"
                already_fired = self._briefing_fired.get(fire_key)

                if current_time == scheduled_time and already_fired != today:
                    self._briefing_fired[fire_key] = today
                    briefing_type = self._briefing_type_for_time(scheduled_time)
                    asyncio.create_task(
                        self.pipeline.run_briefing(briefing_type))

            await asyncio.sleep(30)

    async def _event_detector_loop(self):
        """Full mode: detect critical events from news and price changes."""
        while self._running:
            try:
                # Fetch news
                articles = await self.news_scraper.fetch_all()
                if articles and self.finbert:
                    scored = self.finbert.score_batch([
                        {"text": a.text, "symbol": a.symbol,
                         "source": a.source, "published": a.published}
                        for a in articles
                    ])
                    events = self.event_detector.detect_from_news(scored)
                    for event in events:
                        asyncio.create_task(
                            self.pipeline.run_recalc(event.symbol, event.trigger))
            except Exception as e:
                logger.error("Event detection error: %s", type(e).__name__)

            await asyncio.sleep(self.scan_interval)

    async def _on_realtime_bar(self, bar: dict):
        """Handle real-time bar from Alpaca stream."""
        symbol = bar.get("symbol", "")
        try:
            signals = self.scanner.scan_symbol(symbol, market="US")
            for signal in signals:
                self.notifier.send_signal(signal)
                asyncio.create_task(self.pipeline.run(signal))
        except Exception as e:
            logger.error("Real-time scan error for %s: %s", symbol, type(e).__name__)

    @staticmethod
    def _briefing_type_for_time(time_str: str) -> str:
        """Map scheduled time to briefing type."""
        hour = int(time_str.split(":")[0])
        if hour < 12:
            return "tw_premarket"
        elif hour < 18:
            return "tw_close"
        else:
            return "us_premarket"


def main():
    parser = argparse.ArgumentParser(description="QuantForge Background Monitor")
    parser.add_argument("--config",
                        default=os.path.expanduser("~/.quantforge/config.yaml"))
    parser.add_argument("--log-dir",
                        default=os.path.expanduser("~/.quantforge/logs"))
    args = parser.parse_args()

    install_exception_hooks()
    setup_logging(log_dir=args.log_dir)

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        logger.error("Config not found: %s — run install.sh first", args.config)
        sys.exit(1)

    monitor = TradeMonitor(config)
    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd . && python -m pytest tests/test_monitor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add quantforge/monitor/monitor.py tests/test_monitor.py
git commit -m "feat: enhance TradeMonitor with Lite/Full modes, startup checks, briefing and event loops"
```

---

## Task 9: install.sh Update + Integration Test

**Files:**
- Modify: `install.sh`
- Create: `tests/test_integration_monitor.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration_monitor.py
"""Smoke test: monitor initializes in lite mode without any API keys."""
import pytest
from unittest.mock import patch
from quantforge.monitor.monitor import TradeMonitor


class TestMonitorIntegration:
    def test_lite_mode_no_keys_starts_ok(self):
        """Monitor should start in lite mode even without any API keys."""
        config = {
            "watchlist": {"US": ["AAPL", "NVDA"], "TW": ["2330"]},
            "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                         "rsi_overbought": 80, "rsi_oversold": 20},
            "notification": {"sensitivity": "medium"},
            "monitor": {"monitor_mode": "lite", "scan_interval_minutes": 15,
                         "reports": {"output_dir": "/tmp/qf-test", "retention_days": 1}},
        }
        monitor = TradeMonitor(config)
        assert monitor.mode == "lite"
        assert monitor.scan_interval == 900
        warnings = monitor._startup_check()
        assert len(warnings) > 0  # should warn about missing keys

    def test_full_mode_downgrades_without_llm(self):
        config = {
            "watchlist": {"US": ["AAPL"], "TW": []},
            "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                         "rsi_overbought": 80, "rsi_oversold": 20},
            "notification": {"sensitivity": "medium"},
            "monitor": {"monitor_mode": "full", "scan_interval_minutes": 15,
                         "reports": {"output_dir": "/tmp/qf-test", "retention_days": 1}},
        }
        # Without API keys, full mode should downgrade to lite
        monitor = TradeMonitor(config)
        assert monitor.mode == "lite"

    def test_startup_summary_has_correct_format(self):
        config = {
            "watchlist": {"US": ["AAPL", "NVDA"], "TW": ["2330"]},
            "signals": {"ma_crossover": [20, 60], "volume_spike_ratio": 2.0,
                         "rsi_overbought": 80, "rsi_oversold": 20},
            "monitor": {"monitor_mode": "lite", "scan_interval_minutes": 15,
                         "reports": {"output_dir": "/tmp/qf-test", "retention_days": 1}},
        }
        monitor = TradeMonitor(config)
        summary = monitor._startup_summary()
        assert "2 US" in summary
        assert "1 TW" in summary
        assert "15 min" in summary
```

- [ ] **Step 2: Run integration test**

Run: `cd . && python -m pytest tests/test_integration_monitor.py -v`
Expected: PASS

- [ ] **Step 3: Update install.sh**

Add FinBERT download step after step 5 (trading experience system). Add to `install.sh` before the git hooks section:

```bash
# 5b. Download FinBERT model (optional, needed for Full mode)
echo "[5b/7] FinBERT model..."
if [ "${SKIP_FINBERT:-}" = "1" ]; then
    echo "  Skipping FinBERT download (SKIP_FINBERT=1)"
else
    source "$QUANTFORGE_HOME/.venv/bin/activate"
    if python3 -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('ProsusAI/finbert')" 2>/dev/null; then
        echo "  FinBERT model already downloaded"
    else
        echo "  Downloading FinBERT model (~400MB)..."
        python3 -m quantforge.finbert.download || echo "  WARNING: FinBERT download failed — Full mode unavailable. Install later: python -m quantforge.finbert.download"
    fi
fi
```

Also update the "Next steps" section at the end:
```bash
echo "  5. Start monitor: nohup python -m quantforge.monitor.monitor --config \$QUANTFORGE_HOME/config.yaml > \$QUANTFORGE_HOME/logs/monitor.log 2>&1 &"
```

- [ ] **Step 4: Run full test suite**

Run: `cd . && python -m pytest tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add install.sh tests/test_integration_monitor.py
git commit -m "feat: update install.sh with FinBERT download, add integration tests"
```

---

## Task Summary

| Task | Component | New Files | Tests |
|------|-----------|-----------|-------|
| 1 | Config foundation | — | test_config.py |
| 2 | ReportStore | report_store.py | test_report_store.py |
| 3 | ReportBuilder | report_builder.py | test_report_builder.py |
| 4 | FinBERT | finbert/ (3 files) | test_finbert.py |
| 5 | NewsScraper | news_scraper.py | test_news_scraper.py |
| 6 | EventDetector | event_detector.py | test_event_detector.py |
| 7 | AnalysisPipeline | pipeline.py | test_pipeline.py |
| 8 | Enhanced Monitor | monitor.py (rewrite) | test_monitor.py |
| 9 | Integration | install.sh update | test_integration_monitor.py |

Tasks 1-6 are independent and can be parallelized. Task 7 depends on 2, 3. Task 8 depends on 4, 5, 6, 7. Task 9 depends on 8.
