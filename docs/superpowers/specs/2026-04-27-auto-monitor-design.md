# Auto Monitor: Enhanced Background Monitor with LLM Analysis

**Date:** 2026-04-27
**Status:** Draft
**Author:** QuantForge Contributors

---

## 1. Overview

Enhance the existing `TradeMonitor` to automatically trigger LLM deep analysis when signals are detected, generate scheduled briefings, and perform instant edge recalculation on critical events — all without manual user input.

### 1.1 Goals

- Fully automated stock market monitoring with LLM advisory layer
- Two switchable modes (Lite / Full) via `config.yaml`
- Telegram push notifications (short summary) + local report storage (full detail)
- Graceful degradation when components are unavailable

### 1.2 Modes

| Mode | Behavior | Estimated Cost |
|------|----------|----------------|
| **Lite** | Scan every 15 min. On HIGH/CRITICAL signal → trigger LLM analysis | ~$15-25/month |
| **Full** | Lite + scheduled briefings (3x/day) + news scraping + FinBERT + real-time critical event recalculation | ~$63/month |

Mode is set in `config.yaml` via `monitor.monitor_mode: lite | full`.

---

## 2. Architecture

Single-process enhancement of existing `TradeMonitor`. All new work runs as async tasks within the same event loop.

```
TradeMonitor (enhanced)
│
├── _scheduled_loop()              [existing, changed to 15 min]
│   └── WatchlistScanner           [existing]
│       └── on HIGH/CRITICAL signal:
│           └── AnalysisPipeline.run(signal)          [NEW]
│
├── _briefing_loop()               [NEW, Full mode only]
│   └── 08:30 / 14:00 / 21:00 (TST)
│       └── AnalysisPipeline.run_briefing()
│
├── _event_detector_loop()         [NEW, Full mode only]
│   └── NewsScraper (6 RSS sources)
│   └── FinBERT sentiment scoring
│   └── Critical event detection
│       └── AnalysisPipeline.run_recalc()
│
├── AlpacaStream                   [existing]
│   └── real-time bar → scan_symbol → on signal → AnalysisPipeline
│
└── AnalysisPipeline               [NEW, core component]
    ├── QuantScanner               [existing]
    ├── LLMRouter                  [existing]
    ├── ReportBuilder              [NEW]
    ├── ReportStore                [NEW]
    └── TelegramNotifier           [existing]
```

Non-blocking: LLM analysis runs via `asyncio.create_task()`. Semaphore limits to max 3 concurrent analysis tasks.

---

## 3. AnalysisPipeline

Core new component that chains: signal → full factor scoring → LLM analysis → report.

### 3.1 Signal-Triggered Analysis (`run`)

```
1. QuantScanner.score_stock() → 4-layer factor scoring (~5 sec)
2. Check _should_analyze gate
3. LLMRouter.analyze() → deep analysis (~60 sec)
4. ReportBuilder.build() → short summary + full report
5. TelegramNotifier.send_text(summary)
6. ReportStore.save(full_report)
```

### 3.2 LLM Trigger Gate (`_should_analyze`)

| Condition | Call LLM? |
|-----------|-----------|
| CRITICAL signal | Always |
| HIGH signal | Always |
| MEDIUM / LOW signal | Never |

### 3.3 Scheduled Briefing (`run_briefing`)

```
1. QuantScanner.score_stock() for all watchlist symbols
2. RegimeDetector → current market regime
3. LLMRouter → generate briefing with dedicated prompt
4. ReportBuilder → format briefing
5. Telegram push (short) + local save (full)
```

### 3.4 Instant Recalculation (`run_recalc`)

Same as `run()` but skips the `_should_analyze` gate — always performs full analysis.

### 3.5 Cooldown Rules (configurable in config.yaml)

- Same symbol: 120 minutes minimum interval (default)
- System-wide: max 5 recalculations per day (default)
- Non-trading hours: accumulate for next briefing

---

## 4. NewsScraper

Fetches news from 6 RSS sources, filters for watchlist-relevant articles.

### 4.1 Sources

| Source | Market | URL Pattern |
|--------|--------|-------------|
| Yahoo Finance RSS | US | `finance.yahoo.com/rss/` |
| Finviz | US | `finviz.com/news_export.ashx` |
| Google News | Both | `news.google.com/rss/` |
| CnYes (鉅亨網) | TW | `news.cnyes.com/rss/` |
| MoneyDJ | TW | `moneydj.com/rss/` |
| TWSE/MOPS (公開資訊觀測站) | TW | `mops.twse.com.tw/` |

### 4.2 Interface

```python
class NewsScraper:
    SOURCES = [...]

    async def fetch_all(self, symbols: list[str]) -> list[Article]:
        """Fetch from all sources in parallel, filter for watchlist symbols."""

    async def fetch_symbol(self, symbol: str) -> list[Article]:
        """Fetch news for a specific symbol."""
```

### 4.3 Polling Frequency

- Normal mode: every 15 minutes (aligned with scan interval)
- High-freq mode (Full only): every 2 minutes, auto-activated 5 min before scheduled events, deactivated 30 min after

---

## 5. FinBERT Integration

Local sentiment classification model. Deterministic — same input always produces same output.

### 5.1 Interface

```python
class FinBERTAnalyzer:
    def __init__(self):
        # Model: ProsusAI/finbert from HuggingFace (~400MB)
        # Lazy-loaded on first use

    def score(self, text: str) -> float:
        """Returns -1.0 (bearish) to +1.0 (bullish)"""

    def score_batch(self, articles: list[Article]) -> list[ScoredArticle]:
        """Batch scoring. Negative news weighted 1.5x."""
```

### 5.2 Dual Role

1. **Factor input:** Feeds into SentimentFactor (Edge Layer 4, 20-35% weight) during regular scans
2. **Event trigger:** Extreme scores (>0.9 or <-0.85) trigger instant recalculation

---

## 6. EventDetector

Full mode only. Detects critical events from both price data and news.

### 6.1 Trigger Conditions

| Source | Condition | Action |
|--------|-----------|--------|
| FinBERT | score > 0.9 or < -0.85 on watchlist stock | Instant recalc |
| Keywords | earnings, merger, investigation, delisting, upgrade, downgrade, CEO change | Instant recalc |
| Article density | Same stock, 3+ same-direction articles within 15 min | Instant recalc |
| Price | quant_score change > 15 vs last scan | Instant recalc |
| Regime | VIX > 30 or regime transition | Instant recalc |

### 6.2 Score Delta Detection

Maintains `_last_scores: dict[str, float]` to track quant_score changes between scans.

### 6.3 Cooldown (configurable)

- Same symbol: 120 min (default)
- System-wide: 5 per day (default)
- Non-trading hours: accumulate for next briefing

---

## 7. ReportBuilder

Produces two output formats from analysis results.

### 7.1 Telegram Short Summary (3-5 lines)

```
NVDA — BUY (Quant: 78.5 + Advisor: +6.2)
Regime: BULL_TREND | Tech: 8/10 | Sent: 7/10
LLM: Q3 data center revenue beat, supply chain tightening
Stop: $112.30 (2xATR) | Size: 5% x 0.7
```

### 7.2 Local Full Report (Markdown)

```markdown
# NVDA Analysis Report — 2026-04-27 08:35

## Signal
- Trigger: MA20 crossover up (HIGH)
- Quant Score: 78.5 → BUY
- Advisor Bonus: +6.2 → Combined: 84.7

## Edge Scores
| Factor       | Raw  | Normalized | Weight | Contribution |
|-------------|------|-----------|--------|-------------|
| Technical   | 3/4  | 0.75      | 45%    | 33.75       |
| CrossMarket | 1/2  | 0.50      | 20%    | 10.0        |
| Sentiment   | 0.82 | 0.82      | 35%    | 28.7        |

## Regime: BULL_TREND
- ADX: 32.1 (>25, trending)
- Price > MA60
- VIX: 18.2

## LLM Analysis
[Full text from Claude/Gemini]

## Risk
- Stop-loss: $112.30 (2xATR)
- Position size: 5% x 0.7 = 3.5% of capital
- Correlation with holdings: 0.45 (OK)

## Meta
- Provider: claude
- Analysis time: 58s
- Mode: full
```

### 7.3 Briefing Format (Telegram)

```
QuantForge TW Pre-Market — 2026-04-27 08:30
Regime: BULL_TREND | VIX: 18.2

Top signals:
  NVDA  78.5  BUY   MA20 cross up
  2330  65.2  WATCH Vol spike
No signal: AAPL, MSFT, TSLA, 2317, 2454

Overnight: SPY +0.8%, SOX +1.2%
Events today: NVDA earnings (after close)
```

---

## 8. ReportStore

### 8.1 Storage Structure

```
~/.quantforge/reports/
├── 2026-04-27/
│   ├── NVDA-083500-signal.md
│   ├── briefing-0830-tw-premarket.md
│   ├── briefing-1400-tw-close.md
│   └── briefing-2100-us-premarket.md
├── 2026-04-28/
│   └── ...
```

### 8.2 Retention

- Default: 30 days
- Configurable via `monitor.reports.retention_days`
- Auto-cleanup on monitor startup

---

## 9. Configuration Changes

### 9.1 New config.yaml Fields

```yaml
monitor:
  monitor_mode: full              # lite | full
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

### 9.2 New requirements.txt Additions

```
transformers>=4.30
torch>=2.0
feedparser>=6.0
```

---

## 10. Startup Requirements

### 10.1 Mode-Dependent Requirements

| Component | Lite mode | Full mode |
|-----------|-----------|-----------|
| Telegram | Optional (warn) | Optional (warn) |
| LLM provider | Optional (warn, quant-only if missing) | **Required** |
| FinBERT model | Not needed | **Required** |
| Alpaca keys | Optional (warn, polling only) | Optional (warn) |

### 10.2 Startup Self-Check

On startup, the monitor checks all components and prints status:

**Lite mode:** Missing components produce warnings with remediation instructions. System continues in degraded mode.

```
WARNING: Telegram not configured — alerts will only appear in logs.
  → Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in ~/.quantforge/.env
```

```
WARNING: No LLM provider available — running quant-only mode (no advisor analysis).
  → Set ANTHROPIC_API_KEY in ~/.quantforge/.env
```

```
WARNING: Alpaca not configured — no real-time US streaming, using 15min polling only.
  → Set ALPACA_DATA_KEY and ALPACA_DATA_SECRET in ~/.quantforge/.env
```

**Full mode:** LLM provider and FinBERT are required. If missing, refuse to start in full mode and fall back to lite.

```
ERROR: Full mode requires LLM provider (Claude or Gemini).
  → Set ANTHROPIC_API_KEY or GOOGLE_AI_API_KEY in ~/.quantforge/.env
  → Or switch to lite mode: monitor_mode: lite
Falling back to lite mode.
```

```
ERROR: Full mode requires FinBERT model.
  → Install: python -m quantforge.finbert.download
  → Or switch to lite mode: monitor_mode: lite
Falling back to lite mode.
```

### 10.3 Startup Summary (Telegram push if configured)

```
QuantForge Monitor started (full mode)
✓ Telegram
✓ LLM: claude (claude-sonnet-4-6)
✓ FinBERT
✓ Alpaca real-time
Watchlist: 5 US + 3 TW
Next briefing: 14:00 TST (TW close)
```

---

## 11. New Files to Create

| File | Purpose |
|------|---------|
| `quantforge/monitor/pipeline.py` | AnalysisPipeline — orchestrates scoring → LLM → report |
| `quantforge/monitor/event_detector.py` | EventDetector — critical event detection from price + news |
| `quantforge/monitor/news_scraper.py` | NewsScraper — 6-source RSS fetcher |
| `quantforge/monitor/report_builder.py` | ReportBuilder — formats short summary + full report |
| `quantforge/monitor/report_store.py` | ReportStore — saves reports to local filesystem |
| `quantforge/finbert/analyzer.py` | FinBERTAnalyzer — local sentiment model wrapper |
| `quantforge/finbert/download.py` | CLI to download FinBERT model |
| `quantforge/finbert/__init__.py` | Package init |

### 11.1 Modified Files

| File | Changes |
|------|---------|
| `quantforge/monitor/monitor.py` | Add briefing_loop, event_detector_loop, mode switching, startup self-check, integrate AnalysisPipeline |
| `quantforge/monitor/scanner.py` | Feed FinBERT scores into sentiment factor |
| `quantforge/config.py` | Validate new monitor config fields |
| `config.yaml.example` | Add monitor section with defaults |
| `requirements.txt` | Add transformers, torch, feedparser |
| `install.sh` | Add FinBERT model download step |

---

## 12. Deployment

Local machine, run with nohup or tmux:

```bash
source ~/.quantforge/.venv/bin/activate
nohup python -m quantforge.monitor.monitor \
  --config ~/.quantforge/config.yaml \
  > ~/.quantforge/logs/monitor.log 2>&1 &
```

No Docker, no systemd. Keep it simple.
