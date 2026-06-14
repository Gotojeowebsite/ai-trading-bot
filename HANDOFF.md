# AI Day-Trading Bot — Handoff Document
**Last updated:** 2026-06-14 08:55 UTC
**Project location:** `/home/mint/Desktop/ai-trading-bot`

---

## Project Summary

Fully autonomous AI day-trading bot with:
- Tiered LLM brain (Gemini Flash for screening, GPT-4o for decisions)
- Real-time market data via Alpaca WebSocket + yfinance fallback
- FinBERT news sentiment analysis
- Politician Trade Copy Mode (STOCK Act congressional disclosures)
- Fully automated bracket order execution via Alpaca Markets API
- Premium dark glassmorphism web dashboard
- Zero human intervention during trading hours

**Full approved plan:** `/home/mint/.gemini/antigravity/brain/e430cecf-901c-44d3-ad51-71db17d24b03/implementation_plan.md`

---

## What's DONE ✅

### Core Infrastructure (Production-Ready)
- **`automation/data_client.py`** (176 lines) — MarketDataClient: Alpaca WebSocket streaming + yfinance polling fallback, threaded, rolling cache, dedup, callbacks
- **`automation/indicators.py`** (170 lines) — VWAP, MACD, RSI, Bollinger Bands, EMA, RVOL. Handles multi-ticker grouped DataFrames
- **`automation/scanner.py`** (231 lines) — PreMarketScanner: gap%, premarket volume, news catalyst, SQLite persistence, CLI
- **`config/config.yaml`** — Full config: watchlist, risk profile, signal weights, LLM tiers, broker, dashboard, notifications
- **`.env.example`** — All API key slots with signup URLs
- **`requirements.txt`** — All production deps (google-generativeai, openai, anthropic, transformers, fastapi, etc.)
- **`test_trading.db`** — SQLite with tables: settings, scanned_tickers, signals, trades
- **`tests/`** — Unit + E2E tests (71 cases), mock servers

### Partially Built (Correct structure, but use mock HTTP endpoints — need rewrite to real APIs)
- **`engine/decision_engine.py`** (73 lines) — Tier 1 `screen_ticker()` + Tier 2 `make_decision()` with risk boundary validation
- **`execution/order_manager.py`** (52 lines) — `execute_bracket_order()`, `close_all_positions()`, `Watchdog` class
- **`sentiment/finbert_client.py`** (31 lines) — `get_sentiment()` with caching
- **`politician/copy_mode.py`** (43 lines) — `get_politician_signals()` — **⚠️ HAS SYNTAX ERROR on line ~35 (duplicate `if`)**
- **`main.py`** (334 lines) — Full pipeline wired: scan → tier1 → sentiment → blend → tier2 → bracket order. Dashboard is bare HTML placeholder

---

## What NEEDS TO BE BUILT ⬜ (in priority order)

### 1. Real LLM Integration — `engine/decision_engine.py` REWRITE
- Tier 1: `google.generativeai` SDK → Gemini 2.0 Flash
- Tier 2: `openai` SDK → GPT-4o
- Build full market briefing prompt (see implementation_plan.md for template)
- JSON response parsing, fallback chain (GPT-4o → Gemini 1.5 Pro → rules), daily call counter
- Load keys from `.env` via python-dotenv

### 2. Real Alpaca Orders — `execution/order_manager.py` REWRITE
- `alpaca-py` SDK (`alpaca.trading.client.TradingClient`)
- Real bracket orders, position liquidation, account info
- Paper vs live from config

### 3. Real Politician Tracker — `politician/copy_mode.py` REWRITE (fix syntax error first)
- Quiver Quant API (`api.quiverquant.com/beta/live/congresstrading`) or Capitol Trades scraping
- Politician alpha scoring, recency decay (45-day window), dollar amount weighting

### 4. Real Sentiment — `sentiment/finbert_client.py` REWRITE
- HuggingFace `ProsusAI/finbert` locally, or news API + FinBERT scoring

### 5. Automation Loop — `automation/trading_loop.py` NEW
- Master controller with APScheduler: pre-market 8AM, trade loop 9:30-3:50, auto-close 3:55
- Circuit breaker (2% daily loss → stop), watchdog crash recovery
- Entry point: `python -m automation.trading_loop`

### 6. Premium Dashboard — `dashboard/app.py` + `dashboard/templates/index.html` NEW
- FastAPI + WebSocket for real-time push
- Dark glassmorphism: portfolio chart, LLM reasoning feed, Capitol Hill panel, signal heatmap, trade log, control panel
- Navy/purple, frosted glass, blur, Chart.js/TradingView Lightweight Charts

### 7. Notifications — `notifications/alerts.py` NEW
- Telegram + email: trade executions, daily P&L, circuit breaker alerts

### 8. README — REWRITE (currently placeholder)
- Setup guide, API key instructions, run commands, architecture, disclaimers

---

## Known Bugs
1. `politician/copy_mode.py` line ~35: duplicate `if` statement — syntax error
2. Missing `__init__.py` in engine/, execution/, politician/, sentiment/, config/, dashboard/
3. No `.env` file — user must copy `.env.example`

---

## Key Design Decisions
- **Tiered LLM**: Gemini Flash (Tier 1) → GPT-4o (Tier 2). Fallback: Gemini 1.5 Pro
- **Broker**: Alpaca Markets (free paper, commission-free live)
- **Day trading only**: Close all by 3:55 PM EST
- **Politician data**: Legal — STOCK Act public disclosures
- **Paper trading default**: Must explicitly switch to live
- **Production quality**: User plans real money deployment

## Reference Docs
- Plan: `/home/mint/.gemini/antigravity/brain/e430cecf-901c-44d3-ad51-71db17d24b03/implementation_plan.md`
- Prompt: `/home/mint/.gemini/antigravity/brain/e430cecf-901c-44d3-ad51-71db17d24b03/prompt_draft.md`
