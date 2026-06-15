# AI Day-Trading Bot — Handoff Document
**Last updated:** 2026-06-15 00:00 UTC
**Project location:** `/home/mint/Desktop/ai-trading-bot`

---

## Project Summary

Fully autonomous AI day-trading bot with:
- Tiered LLM brain (Gemini Flash for screening, GPT-4o for decisions, Gemini 1.5 Pro fallback)
- Real-time market data via Alpaca WebSocket + yfinance fallback
- FinBERT news sentiment analysis (with keyword fallback)
- Politician Trade Copy Mode (STOCK Act congressional disclosures via Quiver Quant)
- Fully automated bracket order execution via Alpaca Markets REST API
- Premium dark glassmorphism web dashboard (FastAPI + WebSocket + Chart.js)
- Telegram + email notifications for trades, circuit breakers, daily summaries
- Time-aware scheduling: pre-market scan → trading hours → EOD auto-close → overnight sleep
- Zero human intervention during trading hours

---

## Status: FULLY BUILT ✅

### All Modules — Production-Ready

| Module | File | Description |
|--------|------|-------------|
| **Trading Loop** | `automation/trading_loop.py` | Master controller with time-aware scheduling, circuit breaker, notifications |
| **Market Data** | `automation/data_client.py` | Alpaca WebSocket streaming + yfinance polling fallback |
| **Indicators** | `automation/indicators.py` | VWAP, MACD, RSI, Bollinger Bands, EMA, RVOL |
| **Scanner** | `automation/scanner.py` | Pre-market gap%, volume, news catalyst scanner |
| **LLM Brain** | `engine/llm_brain.py` | Tiered: Gemini Flash (Tier 1) → GPT-4o (Tier 2) → Gemini 1.5 Pro (fallback) |
| **Decision Engine** | `engine/decision_engine.py` | Legacy standalone decision engine (kept for compatibility) |
| **Order Executor** | `execution/order_manager.py` | Alpaca REST API: bracket orders, position close, account info, demo mode |
| **Sentiment** | `sentiment/finbert_client.py` | NewsAPI headlines → FinBERT scoring → keyword fallback |
| **Politician Tracker** | `politician/copy_mode.py` | Quiver Quant API, politician alpha scoring, recency decay |
| **Notifications** | `notifications/alerts.py` | Telegram + email: trade alerts, circuit breaker, daily summary |
| **Dashboard Backend** | `dashboard/app.py` | FastAPI + WebSocket, REST APIs for all data |
| **Dashboard Frontend** | `dashboard/index.html` | Dark glassmorphism UI: charts, heatmap, LLM reasoning, politician feed |
| **CLI Orchestrator** | `main.py` | Unified entry point: `bot`, `dashboard`, `scan`, `status` commands |
| **Config** | `config/config.yaml` | Full YAML config: watchlist, risk, LLM tiers, broker, notifications |

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env with your keys

# 3. Start the trading bot (autonomous)
python main.py bot

# 4. In another terminal, start the dashboard
python main.py dashboard
# Then open http://localhost:8080

# 5. One-shot pre-market scan
python main.py scan --force

# 6. Check system status
python main.py status

# Alternative module-style launch:
python -m automation           # trading bot
python -m dashboard            # dashboard
```

---

## Key Design Decisions
- **Tiered LLM**: Gemini Flash (Tier 1) → GPT-4o (Tier 2). Fallback: Gemini 1.5 Pro
- **Broker**: Alpaca Markets (free paper, commission-free live)
- **Day trading only**: Close all by 3:55 PM EST
- **Politician data**: Legal — STOCK Act public disclosures
- **Paper trading default**: Must explicitly switch to live in config
- **Demo mode**: All modules gracefully degrade when API keys are missing
- **Time-aware scheduling**: Automatic pre-market scan, trading hours, EOD close, overnight sleep
- **Circuit breaker**: 2% daily loss limit → auto-close all positions + notify
