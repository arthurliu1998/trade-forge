# QuantForge

Retail-grade quantitative trading system with LLM intelligence layer. Monitors US and Taiwan stock markets, detects trading signals, and delivers analysis via desktop notifications, Discord, or Telegram.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    TradeMonitor (daemon)                 │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Scheduled    │  │  Briefing    │  │  Event        │  │
│  │  Scan Loop   │  │  Loop        │  │  Detector     │  │
│  │  (15 min)    │  │  (3x/day)    │  │  Loop         │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                  │          │
│         ▼                 ▼                  ▼          │
│  ┌─────────────────────────────────────────────────┐    │
│  │              AnalysisPipeline                    │    │
│  │  QuantScanner → LLMRouter → ReportBuilder       │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │                                   │
│         ┌───────────┴───────────┐                       │
│         ▼                       ▼                       │
│  ┌──────────────┐       ┌──────────────┐                │
│  │ MultiNotifier│       │  ReportStore │                │
│  │ (desktop,    │       │  (full .md)  │                │
│  │  discord,    │       └──────────────┘                │
│  │  telegram)   │                                       │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

### Signal Pipeline (4 Edge Layers)

| Layer | Factor | TW Weight | US Weight |
|-------|--------|-----------|-----------|
| 1 | Technical (MA, RSI, MACD, KD, Bollinger, ADX) | 35% | 45% |
| 2 | Chipflow (institutional flow, margin, short interest) | 30% | -- |
| 3 | Cross-Market (SOX→TW semis, ADR spread, USD/TWD) | 15% | 20% |
| 4 | Sentiment (FinBERT on news articles) | 20% | 35% |

Weighted sum → Quant Score (0-100) → Signal Level:

| Quant Score | Level | Position Size |
|-------------|-------|---------------|
| >= 80 | STRONG_BUY | 100% |
| >= 70 | BUY | 70% |
| 60-69 + advisor >= 70 | ADVISOR_ASSISTED_BUY | 50% |
| < 60 | NO_SIGNAL | -- |

LLM advisor bonus is capped at +/-10 points and **cannot override** a quant score below 60.

### Two Operating Modes

| Mode | What it does | Monthly Cost |
|------|-------------|-------------|
| **Lite** | Scan every 15 min. On HIGH/CRITICAL signal → LLM deep analysis → notify | ~$15-25 |
| **Full** | Lite + 3x/day briefings + news scraping (6 RSS) + FinBERT + critical event detection | ~$63 |

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/arthurliu1998/quant-forge.git
cd quant-forge
bash install.sh
```

This creates `~/.quantforge/` with:
- `.venv/` -- Python virtual environment
- `.env` -- API keys (empty, you fill in)
- `config.yaml` -- watchlist and settings
- `data/`, `runs/`, `logs/`, `reports/` -- data directories

### 2. Configure API Keys

Edit `~/.quantforge/.env`:

```bash
vim ~/.quantforge/.env
```

| Key | Purpose | Required? |
|-----|---------|-----------|
| `ANTHROPIC_API_KEY` | Claude LLM analysis | Lite: optional. Full: required |
| `GOOGLE_AI_API_KEY` | Gemini fallback | Optional (auto-failover if Claude fails) |
| `ALPACA_DATA_KEY` | US real-time streaming | Optional (uses polling without it) |
| `ALPACA_DATA_SECRET` | US real-time streaming | Optional (same as above) |
| `DISCORD_WEBHOOK_URL` | Discord notifications | Only if using discord backend |
| `TELEGRAM_BOT_TOKEN` | Telegram notifications | Only if using telegram backend |
| `TELEGRAM_CHAT_ID` | Telegram target | Only if using telegram backend |

### 3. Configure Watchlist

Edit `~/.quantforge/config.yaml`:

```yaml
watchlist:
  US:
    - AAPL
    - NVDA
    - TSLA
    - AMD
    - MSFT
  TW:
    - "2330"    # TSMC
    - "2317"    # Foxconn
    - "2454"    # MediaTek

signals:
  ma_crossover: [20, 60, 120]
  volume_spike_ratio: 2.0
  rsi_overbought: 80
  rsi_oversold: 20

notification:
  backends:                        # desktop | discord | telegram
    - desktop                      # Linux notify-send (no setup needed)
  sensitivity: medium

monitor:
  monitor_mode: lite              # lite | full
  scan_interval_minutes: 15
  briefing_timezone: "Asia/Taipei"
  briefing_schedule:
    - "08:30"
    - "14:00"
    - "21:00"
  cooldown:
    same_symbol_minutes: 120      # same stock min interval
    daily_recalc_limit: 5         # max recalcs per day
  reports:
    retention_days: 30
    output_dir: "~/.quantforge/reports"
```

### 4. Run Tests

```bash
source ~/.quantforge/.venv/bin/activate
cd quant-forge
python3 -m pytest tests/ -v
```

### 5. Start the Monitor

```bash
source ~/.quantforge/.venv/bin/activate

# Foreground (for testing)
python3 -m quantforge.monitor.monitor --config ~/.quantforge/config.yaml

# Background (production)
nohup python3 -m quantforge.monitor.monitor \
  --config ~/.quantforge/config.yaml \
  > ~/.quantforge/logs/monitor.log 2>&1 &

echo $!  # note the PID
```

On startup, the monitor:
1. Validates config and checks all components
2. Pushes a status summary to Telegram:
   ```
   QuantForge Monitor started (lite mode)
   Y Telegram
   Y LLM: claude
   N FinBERT
   N Alpaca real-time
   Watchlist: 5 US + 3 TW
   Scan interval: 15 min
   ```
3. Warns about missing components with remediation instructions
4. Begins scanning

---

## What Happens at Runtime

### Lite Mode

```
Every 15 minutes:
  ├── Scan all watchlist symbols (RSI, MA crossover, volume spike)
  ├── No signals → log "No signals detected"
  └── HIGH/CRITICAL signal found:
       ├── Notify: basic signal notification
       └── AnalysisPipeline (async, ~60 sec):
            ├── QuantScanner: 4-layer factor scoring
            ├── LLMRouter: Claude/Gemini deep analysis
            ├── Notify: short summary (3-5 lines)
            └── ReportStore: full report → ~/.quantforge/reports/
```

### Full Mode (adds to Lite)

```
Scheduled briefings (3x/day):
  08:30 TST — TW pre-market briefing
  14:00 TST — TW close report
  21:00 TST — US pre-market briefing
  Each: score all watchlist → LLM briefing → notify + local report

News + Event detection (every 15 min):
  ├── NewsScraper: fetch 6 RSS sources
  ├── FinBERT: sentiment score each article
  └── EventDetector triggers on:
       ├── FinBERT extreme (>0.9 or <-0.85)
       ├── Keyword match (earnings, merger, delisting...)
       ├── 3+ same-direction articles on one stock
       ├── Quant score change > 15 points
       └── Regime transition or VIX > 30
       → Instant edge recalculation → notify alert
```

### Notifications

QuantForge supports pluggable notification backends. Configure one or more in `config.yaml`:

```yaml
notification:
  backends:
    - desktop    # Linux notify-send (zero config)
    - discord    # Discord webhook (set DISCORD_WEBHOOK_URL in .env)
    - telegram   # Telegram bot (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env)
  sensitivity: medium   # high | medium | low
```

If `backends` is omitted, defaults to `["telegram"]` for backward compatibility.

**Signal alert example:**
```
NVDA — BUY (Quant: 78.5 + Advisor: +6.2)
Regime: bull_trend | Trigger: rsi_oversold
LLM: Strong data center demand driving momentum...
```

**Briefing example:**
```
QuantForge TW Pre-Market — 2026-04-27 08:30
Regime: bull_trend | VIX: 18.2

  NVDA    78.5  BUY
  AAPL    65.2  WATCHLIST
  2330    55.0  —
```

### Local Reports

Full markdown reports saved to `~/.quantforge/reports/`:
```
~/.quantforge/reports/
├── 2026-04-27/
│   ├── NVDA-083500-signal.md
│   ├── briefing-0830-tw-premarket.md
│   └── briefing-2100-us-premarket.md
├── 2026-04-28/
│   └── ...
```

Auto-cleaned after 30 days (configurable).

---

## Management

```bash
# View logs
tail -f ~/.quantforge/logs/monitor.log

# Check if running
ps aux | grep quantforge.monitor

# Stop
kill <PID>

# Restart
nohup python3 -m quantforge.monitor.monitor \
  --config ~/.quantforge/config.yaml \
  > ~/.quantforge/logs/monitor.log 2>&1 &

# Switch mode (edit config, then restart)
vim ~/.quantforge/config.yaml   # change monitor_mode: full
kill <PID> && nohup python3 -m quantforge.monitor.monitor ...

# View a report
cat ~/.quantforge/reports/2026-04-27/NVDA-083500-signal.md
```

---

## Claude Code Integration

QuantForge also provides a `/quantforge` skill for interactive analysis in Claude Code:

| Command | What it does |
|---------|-------------|
| `/quantforge` | New team setup wizard |
| `/quantforge analyze <SYMBOL>` | Full single stock analysis |
| `/quantforge scan` | Quick watchlist signal scan |
| `/quantforge scan full` | Full scan + parallel multi-agent deep analysis |
| `/quantforge brief` | Market brief |
| `/quantforge portfolio` | Portfolio view |
| `/quantforge review` | Post-trade Socratic review |
| `/quantforge journal` | Trading learning log |

The background monitor and Claude Code skill are independent -- the monitor runs 24/7 automatically, while the skill is for on-demand interactive analysis.

---

## Graceful Degradation

The system is designed to work with whatever components are available:

| Missing Component | Impact |
|-------------------|--------|
| All notification backends | Alerts only in logs |
| LLM (Claude/Gemini) | Quant-only scoring, no advisor analysis |
| FinBERT | Full mode unavailable (falls back to lite) |
| Alpaca | No real-time streaming, 15-min polling only |

Full mode **requires** both LLM and FinBERT. If either is missing, the monitor logs an error with instructions and falls back to lite mode automatically.

---

## Risk Controls

Built-in circuit breakers (configurable):

| Rule | Default | Action |
|------|---------|--------|
| Portfolio drawdown from peak | > 15% | Halt trading for 30 days |
| Single day loss | > 3% | No new positions rest of day |
| Consecutive losses | >= 8 | Stop strategy, review needed |
| Negative months in a row | >= 3 | Stop strategy, review needed |
| VIX spike | > 30 | Reduce positions 50%, no new entries |

---

## Project Structure

```
quantforge/
├── core/models.py              # QuantSignal, FactorScore, Regime
├── data/                       # Market data providers (yfinance, TWSE)
├── analysis/indicators.py      # Technical indicators (MA, RSI, MACD, etc.)
├── factors/                    # 4 edge layers + synthesizer
├── regime/detector.py          # Market regime detection (ADX + VIX + MA60)
├── signals/engine.py           # Rule-based signal detection
├── scanner.py                  # Full factor pipeline scorer
├── portfolio/                  # 3-layer manager, ATR sizer, rebalancer
├── risk/                       # Controller, circuit breakers, correlation
├── backtest/                   # Walk-forward, Monte Carlo, cost model
├── alpha/                      # Decay monitor, advisor tracker
├── behavioral/                 # Discipline tracker
├── finbert/                    # FinBERT sentiment model
│   ├── analyzer.py             # Score text → sentiment (-1 to +1)
│   └── download.py             # CLI to download model
├── monitor/                    # Background monitor system
│   ├── monitor.py              # Main daemon (Lite/Full modes)
│   ├── pipeline.py             # AnalysisPipeline orchestrator
│   ├── scanner.py              # Watchlist signal scanner
│   ├── news_scraper.py         # 6-source RSS fetcher
│   ├── event_detector.py       # Critical event detection
│   ├── report_builder.py       # Telegram + markdown report formatter
│   ├── report_store.py         # Local report storage + cleanup
│   ├── alpaca_stream.py        # Real-time US stock streaming
│   └── secure_logger.py        # Log sanitization (redacts secrets)
├── providers/                  # LLM router (Claude/Gemini auto-failover)
├── notify/                     # Pluggable notification backends
│   ├── base.py                 # BaseNotifier interface
│   ├── desktop.py              # Linux notify-send
│   ├── discord.py              # Discord webhook
│   ├── multi.py                # Fan-out to multiple backends
│   └── telegram.py             # Telegram bot
├── secrets.py                  # 3-tier secret management (keyring → env → .env)
└── safe_exceptions.py          # Exception sanitization
```

---

## Security

- Secrets managed via `SecretManager` (keyring → env → `.env` file)
- `.env`, `config.yaml`, `*.db` are gitignored
- Log sanitizer redacts API keys, dollar amounts, share counts
- LLM data sanitizer strips absolute financial amounts (only percentages sent to LLM)
- Pre-commit hook blocks commits of sensitive files
- Exception hooks redact secrets from tracebacks

---

## Tech Stack

- Python 3.10+
- pandas, numpy -- data processing
- yfinance -- US market data (free)
- feedparser -- RSS news fetching
- transformers + torch -- FinBERT sentiment model
- python-telegram-bot -- Telegram notifications (optional)
- anthropic SDK -- Claude LLM
- asyncio -- concurrent scanning and analysis

---

## License

MIT
