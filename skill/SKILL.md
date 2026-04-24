---
name: trade-forge
description: >
  Multi-agent trading analysis system for US and Taiwan stocks.
  Coordinates 9 agents (Lead, Technical, Market, TW/US Flow, Sentinel,
  Quant, Risk, Executor) for signal detection, analysis, and semi-automated
  trading. Includes trajectory tracking, diagnostic codes (SIG/RGM/RSK/BHV),
  trade case studies, and learning experience system.
  Trigger: "analyze TSLA", "scan watchlist", "market brief", "/trade-forge",
  "review trade", "trade journal".
user-invocable: true
argument-hint: "[analyze <SYMBOL> | scan | brief | portfolio | review | journal | load <name>]"
---

# TradeForge: Multi-Agent Trading Analysis System

## Quick Reference

| Command | Effect |
|---------|--------|
| `/trade-forge` | New team setup wizard |
| `/trade-forge analyze <SYMBOL>` | Full analysis of a single stock |
| `/trade-forge scan` | Scan watchlist for signals |
| `/trade-forge brief` | Morning/evening market brief |
| `/trade-forge portfolio` | Show positions and P&L |
| `/trade-forge review [SYMBOL]` | Post-trade review with Socratic analysis |
| `/trade-forge journal` | View/update trading learning log |
| `/trade-forge load <name>` | Resume saved team |

## Mode Dispatch

Parse `$ARGUMENTS`:
- **(empty)** → New Team Setup wizard
- **`analyze <SYMBOL>`** → Single Stock Analysis
- **`scan`** → Watchlist Scan
- **`brief`** → Market Brief
- **`portfolio`** → Portfolio View
- **`review [SYMBOL]`** → Trade Review
- **`journal`** → Learning Journal
- **`load <name>`** → Resume Team

---

## New Team Setup

Walk through one at a time:

1. **Goal**: "What is your trading goal?"
2. **Roles**: Recommend based on goal:
   - Analyze/scan: Lead, Technical, Market, Quant
   - Full+flow: Lead, Technical, Market, TW/US Flow, Sentinel, Quant, Risk
   - Monitor: Lead, Technical, Risk, Executor
   - Deep dive: All 9
3. **Watchlist**: "Symbols? (comma-separated, or 'use config')"
4. **Confirm & Spawn**:
   - `TeamCreate({ team_name: "trade-forge-<date>" })`
   - Read `${CLAUDE_SKILL_DIR}/roles/<role>.md`, fill placeholders
   - Spawn agents, begin as Lead

---

## Single Stock Analysis (`analyze <SYMBOL>`)

Spawn Technical + Market + Risk. Analyze → synthesize → report.

---

## Trade Review (`review [SYMBOL]`)

Post-trade analysis using Socratic questioning. Flow:

1. If SYMBOL given, pull trade history from portfolio; otherwise ask user for details
2. Walk through the review using the Socratic flow from `~/.claude/notes/trading/diagnostics.md`:
   - What happened? (entry/exit/P&L)
   - What type of issue? (SIG/RGM/RSK/BHV)
   - Root cause hypothesis?
   - How to confirm?
   - What would you do differently?
3. Offer to record as case study in `~/.claude/notes/trading/cases/`
4. Check if patterns are emerging across cases

Reference files:
- `~/.claude/notes/trading/playbook.md` — decision framework
- `~/.claude/notes/trading/diagnostics.md` — diagnostic codes
- `~/.claude/notes/trading/cases.md` — case index
- `~/.claude/notes/trading/patterns.md` — confirmed patterns

---

## Learning Journal (`journal`)

View and update trading skill progression:

1. Read `~/.claude/notes/trading/learning-log.md`
2. Show current skill self-assessment
3. Ask: "Want to update any skill ratings? Or add a learning entry?"
4. If updating, walk through:
   - Which skill changed?
   - New level (1-5)?
   - What experience led to the change?
5. Save updates

---

## Lead Operating Instructions

After spawn, you ARE the Lead. See `roles/lead.md`.

Key rules:
- Coordinate, don't implement
- Enforce discipline rules (circuit breakers, anti-FOMO)
- One task per member at a time
- Ask user for confirmation before any trade action
- Track decisions via trajectory
- Prompt for trade review after each closed trade

## Trajectory Tracking

Record every trade decision via:
```bash
python3 -c "
from trade_forge.trajectory import TradeTrajectory
t = TradeTrajectory('{{TRAJECTORY_PATH}}')
t.record(symbol='XXX', direction='long/short', signal_type='technical/flow/...',
         diagnostic_code='SIG-XXX', entry_price=0, exit_price=0,
         pnl_pct=0, status='open/closed/stopped')
"
```

View history: `t.query('summary')` or `t.query('by_diagnostic')`

## Experience System Integration

The trading experience system lives at `~/.claude/notes/trading/`:

| File | Purpose |
|------|---------|
| `playbook.md` | Decision loop, signal classification, regime detection, sizing |
| `diagnostics.md` | Diagnostic codes: SIG-T/F (signals), RGM (regime), RSK (risk), BHV (behavioral) |
| `cases.md` | Trade case study index with statistics |
| `cases/case-NNN-*.md` | Individual trade case studies |
| `patterns.md` | Confirmed reusable trading patterns |
| `learning-log.md` | Skill self-assessment (12 skills, rated 1-5) |

### Diagnostic Code Quick Reference

| Code | Category | Example |
|------|----------|---------|
| SIG-T01 | Technical signal reversed | RSI oversold but price kept falling |
| SIG-T02 | MA crossover whipsaw | Choppy market, no trend |
| SIG-T03 | RSI oversold in bear market | Oversold ≠ buy in downtrend |
| SIG-F01 | Flow signal no follow-through | One-off rebalancing |
| SIG-F02 | Options unusual activity no move | Hedge, not directional |
| RGM-01 | Regime classification wrong | Used lagging indicators |
| RGM-02 | Right regime, wrong filter | Bull signals in bear regime |
| RSK-01 | Position too large | Gap risk, correlated positions |
| RSK-02 | Stop hit then recovered | Stop too tight for volatility |
| RSK-03 | Took profit too early | No trailing stop system |
| BHV-01 | Chased entry (FOMO) | Entered > 2% past signal |
| BHV-02 | Held loser too long | No stop or moved stop wider |
| BHV-03 | Overtrading | Boredom/revenge trading |
| BHV-04 | Cut winner, held loser | Loss aversion pattern |

### After Each Trade Closes

Lead must prompt:
> 要不要記錄這筆交易？我會用 `trading/cases/case-000-template.md` 建案例。

### Pattern Extraction

When 2-3 cases share a common lesson, propose extracting to `patterns.md`.

## Security Rules (ALL roles)

- NEVER read/cat .env or files with API keys
- NEVER run: echo $API_KEY, env | grep KEY, cat ~/.trade-forge/.env
- NEVER log/print secrets
- Check keys: `SecretManager.is_configured('KEY_NAME')`
- LLM data via DataSanitizer only — no absolute dollar amounts
