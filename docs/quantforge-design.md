# QuantForge: Quantitative Trading System Design Spec

**Date:** 2026-04-26
**Status:** Draft
**Author:** QuantForge Contributors

---

## 1. Overview

### 1.1 System Identity

- **Name:** QuantForge
- **Purpose:** Retail-grade quantitative trading system with LLM intelligence layer
- **Markets:** US stocks + Taiwan stocks (TWSE)
- **Data:** Daily OHLCV, free sources (yfinance, TWSE API, FinMind)
- **LLM:** Claude Opus for all LLM tasks (~$63/month)
- **Execution:** Level 1 (Telegram alerts) → Level 2 (semi-auto via broker API, reserved)
- **Relationship to TradeForge:** QuantForge is the core engine; TradeForge provides post-trade Socratic review and experience tracking

### 1.2 Design Principles

1. **Deterministic core:** The quant engine produces identical output for identical input. No LLM in the signal path (except FinBERT, which is deterministic).
2. **LLM as advisor, not decision-maker:** Claude Opus discovers opportunities and provides analysis, but cannot modify signals, parameters, or trigger trades.
3. **Dual-score transparency (Option C):** Every signal shows a reproducible quant score and a separate, capped advisor bonus. The user sees both.
4. **Fail-safe degradation:** If Opus is unavailable, the system runs on pure quant scores. If FinBERT is unavailable, the sentiment factor is set to 0.
5. **Edge-first design:** Strategies are built around four edge layers, not naked indicators.
6. **Self-monitoring:** The system tracks alpha decay, advisor accuracy, and behavioral discipline automatically.

---

## 2. Edge Strategy Design

### 2.1 Four Edge Layers

#### Edge Layer 1: Technical Factors (Weight: 35% TW / 45% US)

Combined conditions, not single indicators. Multi-timeframe (weekly direction + daily entry).

**Trend strategy signals:**
- Price vs MA20 direction and breakout
- MACD direction and crossover
- ADX trend strength

**Mean reversion strategy signals:**
- RSI(14) oversold/overbought
- Bollinger Band reversal
- KD crossover

**Regime determines which strategy set is active** (see Section 4).

Signal scoring: Each condition met = +1 point. Total 0–4, normalized to 0–1.

#### Edge Layer 2: Chipflow Factors — Taiwan Only (Weight: 30% TW / 0% US)

Data source: TWSE API + FinMind (free, daily).

**Buy boost conditions (each +1, max 5):**
1. Foreign institutional investors net buy ≥ 3 consecutive days
2. Investment trust buying in same direction
3. Net buy volume > 10% of daily turnover
4. Margin balance decreasing (retail capitulation)
5. Short-selling balance not significantly increasing

**Sell warning conditions:**
1. Foreign investors net sell ≥ 3 consecutive days
2. Margin balance surging (retail chasing)
3. Short-selling balance surging

Scoring: 0–5, normalized to 0–1.

LLM role: Analyze *why* institutions are buying/selling (news interpretation), but does not affect the numeric score.

#### Edge Layer 3: Cross-Market Correlation (Weight: 15% TW / 20% US)

**Models:**
1. **SOX → Taiwan semis:** Quantify overnight SOX movement → next-day Taiwan semiconductor response. Regression model on historical data to find optimal entry timing.
2. **US earnings → Taiwan supply chain:** Supply chain mapping table (maintained by Opus). Apple/NVIDIA/AMD earnings → corresponding Taiwan stocks.
3. **USD/TWD → export stocks:** Currency movement → export stock response with optimal lag (backtest to find best N-day lag).
4. **ADR spread:** ADR-implied price vs local close for dual-listed stocks.

Scoring: 0–2, normalized to 0–1.

LLM role: Maintain supply chain mapping table. Judge impact direction for ambiguous events.

#### Edge Layer 4: Event/Sentiment (Weight: 20% TW / 35% US)

Two sub-components:

**FinBERT (enters quant score — deterministic, backtestable):**
- Local model, free, same input = same output
- News text → sentiment score (-1 to +1)
- Negative news weighted 1.5× (asymmetric market impact)
- Time decay: 1–3 days of predictive power
- Feeds into quant score as a numeric factor

**Claude Opus (enters advisor bonus — non-deterministic, NOT backtestable):**
- Deep event interpretation (structural vs one-time)
- Supply chain reasoning (1st → 2nd → 3rd order effects)
- Historical event study comparison
- Advisor bonus capped at ±10 points (adjustable based on tracking)

### 2.2 Signal Synthesis

#### Weight Distribution

| Factor | Taiwan | US |
|--------|--------|----|
| Technical | 35% | 45% |
| Chipflow | 30% | — |
| Cross-market | 15% | 20% |
| FinBERT sentiment | 20% | 35% |

US stocks redistribute chipflow weight to technical and sentiment.

#### Scoring Pipeline

```
Step 1: Each factor produces a raw score, normalized to 0–1
Step 2: Weighted sum → quant score (0–100)
Step 3: Regime filter adjusts weights (see Section 4)
Step 4: Advisor bonus added (capped ±10)
Step 5: Signal determination by threshold
```

#### Signal Thresholds

| Quant Score | Advisor Combined | Action |
|-------------|-----------------|--------|
| ≥ 80 | — | Strong buy (standard position) |
| 70–79 | — | Buy (position × 0.7) |
| 60–69 | ≥ 70 | Advisor-assisted signal (position × 0.5) ⚠️ |
| 60–69 | < 70 | Watchlist only |
| < 60 | any | No buy (advisor cannot override) |
| ≤ 39 | — | Watch for sell |
| ≤ 29 | — | Strong sell |

---

## 3. Portfolio Management

### 3.1 Three-Layer Asset Allocation

#### Layer 1: Market Allocation (Dynamic, Regime-Based)

| Regime | Taiwan | US | Cash |
|--------|--------|----|------|
| Both bull | 40% | 40% | 20% |
| TW strong, US weak | 50% | 20% | 30% |
| US strong, TW weak | 20% | 50% | 30% |
| Both bear | 15% | 15% | 70% |
| Crisis (VIX > 30) | 10% | 10% | 80% |

Regime determined by: index vs MA60 + ADX + VIX (see Section 4).

#### Layer 2: Sector Allocation

- Single sector ≤ 40% (TW) / ≤ 35% (US)
- Highly correlated sectors combined ≤ 50%
- Minimum 2 sectors in portfolio

#### Layer 3: Individual Position Sizing

```
Standard position = Total capital × 5%
Adjusted by:
  × Signal strength (80pt = ×1.0, 70pt = ×0.7)
  × Regime discount (bear = ×0.5)
  × Volatility (ATR-based sizing)

ATR sizing:
  Position = Acceptable loss / (2 × ATR)
  Acceptable loss = Total capital × 1% (max 1% risk per trade)
```

### 3.2 Rebalancing

**Triggers (any one activates alert):**
1. Drift > 5% from target allocation
2. Regime change
3. Monthly scheduled review (1st trading day)
4. New signal entry (check portfolio fit before buying)

---

## 4. Regime Detection

### 4.1 Regime Classification

```
ADX(14) > 25 + Price > MA60 → Bull trend (use trend strategies)
ADX(14) > 25 + Price < MA60 → Bear trend (defensive/cash)
ADX(14) < 20              → Consolidation (use mean reversion)
VIX > 30                  → Crisis (reduce exposure 50%, no new positions)
```

### 4.2 Regime Impact on Strategy

| Regime | Strategy adjustment |
|--------|-------------------|
| Bull trend | Trend strategy weight +10% |
| Bull consolidation | Mean reversion weight +10% |
| Bear trend | Threshold raised to 85, position halved |
| Bear bounce | Mean reversion allowed, position halved |
| Crisis | All positions reduced 50%, no new entries |

---

## 5. Risk Management

### 5.1 Position-Level Controls

- **Stop-loss:** 2 × ATR(14) below entry
- **Single stock max:** 20% of total capital
- **Per-trade risk:** Max 1% of total capital

### 5.2 Portfolio-Level Controls

- **Sector concentration:** ≤ 40% (TW) / ≤ 35% (US)
- **Correlated sector combined:** ≤ 50%
- **Correlation warning:** Alert when inter-holding correlation > 0.7
- **Total exposure limit:** ≤ 60% of total capital

### 5.3 Circuit Breakers

- **Drawdown halt:** Total portfolio drawdown from peak > 15% → close all positions, stop trading for 1 month
- **Daily loss limit:** Single day loss > 3% → no new positions for rest of day
- **Strategy failure:** Consecutive 8 losses OR 3 consecutive months negative → stop strategy, review
- **VIX filter:** VIX > 30 → reduce all positions by 50%, no new entries

---

## 6. LLM Advisor System

### 6.1 Architecture

Claude Opus serves as an advisory layer with read-only + backtest access to the quant engine.

**Permitted API calls:**
- `get_price_history()`, `get_indicators()`, `get_chipflow()`
- `get_portfolio()`, `get_regime()`, `get_score_breakdown()`
- `run_backtest()`, `event_study()`, `compare_with_benchmark()`
- `scan_sector()`, `find_similar()`

**Forbidden:**
- `place_order()`, `modify_weights()`, `change_threshold()`
- Any write operation to the quant engine

### 6.2 Daily Workflow

1. News scraper (Python) fetches from 6 sources: Yahoo Finance RSS, Finviz, Google News, CnYes (鉅亨網), MoneyDJ, TWSE announcements
2. FinBERT filters ~200 articles → ~50 with sentiment signal
3. Opus analyzes filtered news: event interpretation, supply chain reasoning, candidate stock discovery
4. Opus scores existing holdings for advisor bonus (Option C)
5. Opus calls backtest engine to validate hypotheses on candidate stocks
6. Rule validation layer checks Opus output (see Section 6.4)
7. Validated candidates → watchlist; advisor scores → signal synthesis

### 6.3 Advisor Bonus (Option C — Dual Score)

**Advisor bonus composition (capped at ±10 points):**
- Event impact analysis: ±5 points
- Historical event comparison: ±3 points
- Supply chain reasoning: ±2 points

**Safety rules:**
- Quant score < 60 → advisor bonus ignored, no buy regardless
- Quant score 60–69 + advisor ≥ 70 → "advisor-assisted signal" with position × 0.5
- Every advisor-assisted trade is tagged for A/B tracking

### 6.4 Rule Validation Layer (Python, not LLM)

Checks applied to all Opus output before it enters the system:

1. **Symbol verification:** Does the stock code exist on the exchange?
2. **Fact-checking:** Compare LLM-claimed numbers against actual data (FinMind/yfinance)
3. **Logic consistency:** Bearish analysis + buy recommendation → flag contradiction
4. **Backtest reasonability:** Sharpe > 3.0 → flag as likely overfitting
5. **Duplicate validation:** Run Opus twice on same input, take intersection
6. **Historical accuracy tracking:** Track past recommendations' outcomes; auto-downweight if accuracy drops

### 6.5 LLM Cost Budget

| Item | Monthly cost |
|------|-------------|
| Opus daily analysis | $31 |
| Opus real-time news alerts | $9 |
| Opus real-time edge recalculation | $15 |
| Opus event calendar high-freq triggers | $7.5 |
| **Total** | **~$63/month** |

---

## 7. Real-Time Monitoring System

### 7.1 Three-Tier Monitoring

#### Normal Mode (default)

- Poll RSS/news sources every 15 minutes
- FinBERT quick scan on all fetched articles
- Moderate/low sentiment → accumulate for end-of-day analysis

#### High-Frequency Mode (event-scheduled)

- Poll every 2 minutes
- Auto-activated 5 minutes before scheduled events
- Auto-deactivated 30 minutes after event ends
- Triggered by Event Calendar (see Section 7.2)

#### Critical Event — Instant Edge Recalculation

**Trigger conditions (any one):**
- FinBERT score > 0.9 or < -0.85 on portfolio/watchlist stock
- Keyword match: earnings, merger, investigation, delisting, upgrade/downgrade, CEO change, major contract, policy change
- 3+ same-direction articles on same stock within 15 minutes

**Pipeline (total ~2 minutes):**
1. Fetch real-time price data (30 sec)
2. Quant engine recalculates all factors with live data (5 sec)
3. Opus deep analysis + event study + advisor score (60 sec)
4. Rule validation (1 sec)
5. Telegram push with full edge report

**Cooldown rules:**
- Same stock: max 1 trigger per 2 hours
- System-wide: max 5 triggers per day
- Non-trading hours: accumulate for pre-market briefing
- Already stopped-out stocks: no recalculation

### 7.2 Event Calendar System

**Data sources (free):**
- Yahoo Finance Earnings Calendar (US earnings dates)
- TWSE announcements (TW earnings calls, shareholder meetings, ex-dividend dates)
- MOPS (公開資訊觀測站) (TW major event notices)
- Opus supplementary (discovers events mentioned in news but not in calendars)

**Auto-maintenance:**
- Sync every Sunday for upcoming 2 weeks
- For each event: schedule high-freq monitoring + pre-event briefing

**Three phases per event:**
1. **Pre-event (T-1 day):** Push briefing with market expectations, key metrics to watch, portfolio impact assessment
2. **During event:** High-freq monitoring (every 2 min), instant edge recalculation on critical news
3. **Post-event (T+1):** Follow-up analysis in next pre-market briefing, compare actual vs expected

---

## 8. Notification Schedule

### 8.1 Daily Schedule

| Time (TST) | Type | Content |
|------------|------|---------|
| 05:30 | US market close analysis | Fetch data, run signals, Opus analysis |
| 08:30 | 🔔 TW pre-market briefing | Overnight recap, ADR conversion, today's event calendar, action items |
| 09:00 | TW market open | — |
| 13:30 | TW market close analysis | Fetch data, run signals, chipflow analysis |
| 14:00 | 📋 TW close report | Signals, holdings update, portfolio check |
| 21:00 | 🔔 US pre-market briefing | Global recap, pre-market prices, tonight's plan |
| 21:30 | US market open | — |
| All day | ⚡ Real-time alerts | Critical news + instant edge recalculation |
| Monthly 1st | 📊 Alpha health report | Factor performance, advisor tracking, rebalancing |

### 8.2 Notification Content

Each notification includes:
- Quant signals (primary) — with score breakdown by factor
- Advisor insights (secondary) — clearly separated
- Portfolio impact — how the signal affects current allocation
- Actionable recommendation — with specific price/size/stop-loss

Pre-market briefings additionally include:
- International market summary
- Today's event calendar with scheduled monitoring times
- Holdings pre-assessment (ADR conversion, overnight news impact)
- Pending actions from previous signals

---

## 9. Backtesting Engine

### 9.1 Realistic Cost Model

| Cost | Value |
|------|-------|
| Commission | 0.1425% (TW broker fee) |
| Transaction tax | 0.3% on sell (TW), 0.15% for ETF, 0.1% for day trade |
| Slippage | 0.3% (conservative estimate) |
| Market impact | 0.1% |
| **Round-trip total** | **~0.85%** |

### 9.2 Validation Methodology

1. **Data split:** Train 60% / Validate 20% / Test 20% (test set run ONCE only)
2. **Walk-forward validation:** Rolling window (e.g., train 2015–2018 → test 2019, train 2016–2019 → test 2020, ...). Every window must be profitable.
3. **Parameter robustness:** Find parameter "plateaus" not "peaks." RSI threshold 28–32 all profitable = robust. Only RSI=29 profitable = overfitting.
4. **Monte Carlo:** Randomize trade order 1000 times. Worst-case drawdown must be acceptable.
5. **Benchmark comparison:** Every strategy compared against SPY (US) or 0050 (TW). Only strategies with positive alpha proceed. Report alpha, not just absolute return.
6. **Survivorship bias:** Backtest data must include delisted stocks. FinMind data includes these — verify at data ingestion.

---

## 10. Self-Monitoring Systems

### 10.1 Alpha Decay Monitor (Monthly)

Re-backtest each factor using most recent 3 months of data.

**Per-factor monitoring:**
- Win rate decline < 5% → normal fluctuation, no action
- Win rate decline 5–10% → warning, reduce factor weight by 20%
- Win rate decline > 10% → pause factor, notify user

**Strategy-level monitoring:**
- Strategy Sharpe > benchmark Sharpe → alpha exists ✅
- 2 consecutive months alpha < 0 → observation ⚠️
- 3 consecutive months alpha < 0 → stop strategy 🚨

**Auto-adjustment:** Factor weights shift by ±5% based on recent performance (within upper/lower bounds).

**New factor exploration:** When existing factors decay, Opus proposes new candidates (e.g., director shareholding changes, ETF fund flows). Requires user approval and 3-month validation before inclusion.

### 10.2 Advisor Accuracy Tracker (Monthly)

**A/B classification:**
- Category A: Pure quant signals (quant ≥ 70, no advisor needed)
- Category B: Advisor-assisted signals (quant 60–69 + advisor ≥ 70)

**Auto-adjustment rules:**
- B avg return ≥ 80% of A → advisor helpful, maintain ±10 cap
- B avg return 50–80% of A → limited value, reduce cap to ±7
- B avg return < 50% of A → advisor hurting, reduce cap to ±3
- B consecutive 10 losses > A → auto-downgrade to Option B (advisor removed from scoring)

### 10.3 Behavioral Discipline Tracker

**Metrics tracked:**
- Stop-loss execution rate
- Signal ignore rate
- Holding time vs strategy-recommended time
- Chase rate (entry price vs signal price deviation)

**Weekly behavioral report** comparing disciplined vs undisciplined trades.

**Integration with TradeForge:** Socratic review, diagnostic codes (BHV-01 through BHV-04), case studies, pattern extraction.

---

## 11. Data Layer

### 11.1 Data Sources

| Source | Market | Data | Cost | Upgrade Path |
|--------|--------|------|------|-------------|
| yfinance | US | Daily OHLCV, company info, pre-market | Free | → Alpaca API |
| TWSE API | TW | Daily OHLCV | Free | → Fugle / Shioaji |
| FinMind | TW | 50+ datasets: institutional flow, margin, revenue, financials | Free | — |
| Yahoo Earnings | US | Earnings calendar | Free | — |
| MOPS | TW | Major announcements | Free | — |
| RSS feeds (6) | Both | News articles | Free | — |
| FinBERT | Both | Sentiment classification | Free (local) | — |

### 11.2 Storage

- **Historical prices:** Parquet format (columnar, compressed, fast)
- **Portfolio/trades:** SQLite
- **Trade trajectory:** JSON-based log
- **Event calendar:** YAML/JSON
- **News cache:** SQLite with TTL

### 11.3 Data Provider Abstraction

```python
class DataProvider(ABC):
    def get_ohlcv(symbol, interval, start, end) -> DataFrame
    def get_current_price(symbol) -> float
    def get_company_info(symbol) -> dict

class YFinanceProvider(DataProvider): ...    # Phase 1
class AlpacaProvider(DataProvider): ...      # Future upgrade
class TWSEProvider(DataProvider): ...        # Phase 1
class FinMindProvider(DataProvider): ...     # Phase 1
class FugleProvider(DataProvider): ...       # Future upgrade
```

Config-driven source selection:
```yaml
us_provider: yfinance     # changeable to alpaca
tw_provider: twse+finmind # changeable to fugle
interval: 1d              # changeable to 5m
```

---

## 12. Execution Layer

### 12.1 Level 1: Alert Only (Phase 1)

```
Signal generated → Format notification → Telegram push
User manually places order via broker app
```

### 12.2 Level 2: Semi-Automatic (Phase 3, Reserved)

```
Signal generated → Format notification with action buttons
→ User presses [Execute] → Broker API places order
→ Confirmation pushed back to user

Broker APIs:
  US: Alpaca (free, no deposit required for API key)
  TW: Shioaji (Sinopac) or Fugle TradeAPI
```

Core engine unchanged between Level 1 and Level 2. Only the notification module and broker adapter are added.

---

## 13. Project Structure

```
quantforge/
├── core/
│   ├── event_bus.py          # Event queue (MARKET, SIGNAL, ORDER, FILL)
│   ├── models.py             # Data models (Signal, Position, Order)
│   └── config.py             # YAML config loader
├── data/
│   ├── base.py               # DataProvider ABC
│   ├── yfinance_provider.py
│   ├── twse_provider.py
│   ├── finmind_provider.py
│   └── news_scraper.py       # 6-source RSS/web scraper
├── indicators/
│   └── technical.py          # MA, EMA, RSI, MACD, KD, BB, ATR, OBV, ADX
├── factors/
│   ├── technical_factor.py   # Edge Layer 1
│   ├── chipflow_factor.py    # Edge Layer 2 (TW only)
│   ├── crossmarket_factor.py # Edge Layer 3
│   ├── sentiment_factor.py   # Edge Layer 4 (FinBERT)
│   └── synthesizer.py        # Weighted combination + regime adjustment
├── strategies/
│   ├── base.py               # Strategy ABC
│   ├── trend.py              # Trend following strategy
│   └── mean_reversion.py     # Mean reversion strategy
├── regime/
│   └── detector.py           # ADX + VIX + MA60 regime classification
├── portfolio/
│   ├── manager.py            # 3-layer allocation
│   ├── position_sizer.py     # ATR-based sizing with adjustments
│   └── rebalancer.py         # Drift detection + rebalance suggestions
├── risk/
│   ├── controller.py         # All risk checks
│   ├── circuit_breaker.py    # Drawdown halt, daily loss, strategy failure
│   └── correlation.py        # Inter-holding correlation analysis
├── backtest/
│   ├── engine.py             # Event-driven backtester
│   ├── cost_model.py         # Commission, tax, slippage, impact
│   ├── walk_forward.py       # Rolling window validation
│   ├── monte_carlo.py        # Trade order randomization
│   └── analytics.py          # Sharpe, MaxDD, alpha, monthly returns
├── advisor/
│   ├── opus_client.py        # Claude Opus API wrapper
│   ├── finbert.py            # Local FinBERT sentiment classifier
│   ├── event_analyzer.py     # Event interpretation + supply chain reasoning
│   ├── candidate_finder.py   # Non-watchlist stock discovery
│   ├── validator.py          # Rule-based LLM output validation
│   └── accuracy_tracker.py   # A/B tracking of advisor vs pure quant
├── monitor/
│   ├── scheduler.py          # Daily schedule (05:30, 08:30, 14:00, 21:00)
│   ├── news_monitor.py       # 15min/2min polling with mode switching
│   ├── event_calendar.py     # Event scheduling + high-freq triggers
│   └── realtime_recalc.py    # Instant edge recalculation pipeline
├── alpha/
│   ├── decay_monitor.py      # Monthly factor performance tracking
│   ├── weight_adjuster.py    # Auto factor weight adjustment
│   └── factor_explorer.py    # New factor proposal (Opus-driven)
├── behavioral/
│   ├── tracker.py            # Stop-loss execution, signal ignore, chase rate
│   └── reporter.py           # Weekly behavioral report
├── notify/
│   ├── telegram.py           # Telegram Bot integration
│   ├── formatter.py          # Notification templates
│   └── broker_adapter.py     # Level 2: Alpaca / Shioaji (reserved)
├── supply_chain/
│   └── mapping.py            # US → TW supply chain table (Opus-maintained)
├── config/
│   ├── default.yaml          # Default configuration
│   ├── portfolio_rules.yaml  # Allocation limits and rules
│   └── watchlist.yaml        # Symbol watchlist
└── tests/
    └── ...                   # Unit + integration tests for all modules
```

---

## 14. Development Phases

### Phase 1: Core Engine (Weeks 1–4)

- Data layer (US + TW providers)
- Technical indicators
- Factor framework (4 edge layers)
- Signal synthesizer with regime detection
- Backtesting engine (walk-forward, realistic costs, benchmark)
- Risk management (all controls)
- Portfolio manager (3-layer allocation)
- Alpha decay monitor

### Phase 2: Go Live (Weeks 5–8)

- Daily scheduler (cron)
- News scraper (6 sources)
- FinBERT integration
- Opus advisor integration (daily analysis + advisor bonus)
- Rule validation layer
- Telegram Bot notifications
- Event calendar system
- Real-time monitoring (normal + high-freq modes)
- Instant edge recalculation
- Advisor accuracy tracker
- Behavioral tracker

### Phase 3: Semi-Auto Upgrade (After 3+ months of live validation)

- Broker API integration (Alpaca for US, Shioaji/Fugle for TW)
- Telegram confirmation buttons
- Auto stop-loss orders
- Performance dashboard (web UI)
- Additional strategies (momentum, multi-factor)

---

## 15. Risk Acknowledgments

1. **No live validation yet.** Backtest ≠ live performance. Run paper trading for 3 months minimum before committing real capital.
2. **Chipflow alpha may decay.** Monthly monitoring + auto-adjustment mitigates but does not eliminate this risk.
3. **Advisor bonus is non-deterministic.** A/B tracking with auto-downgrade to Option B protects against advisor degradation.
4. **Single LLM provider dependency.** Core engine runs without Opus. Advisor layer designed as pluggable (Opus → Sonnet → local model fallback).
5. **Survivorship bias.** Must verify backtest data includes delisted stocks.
6. **Event timing for daily system.** Real-time monitoring + event calendar mitigates but daily-bar strategies cannot capture intraday moves.

---

## 16. Monthly Cost Summary

| Item | Cost |
|------|------|
| Claude Opus daily analysis | $31 |
| Claude Opus real-time news alerts | $9 |
| Claude Opus instant edge recalculation | $15 |
| Claude Opus event calendar triggers | $7.5 |
| FinBERT (local) | $0 |
| Data sources (yfinance, TWSE, FinMind) | $0 |
| Telegram Bot | $0 |
| Server (local machine) | $0 |
| **Total** | **~$63/month** |
