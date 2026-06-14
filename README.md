# 🧠 APEX AI — Autonomous Day Trading Bot

A fully autonomous AI-powered day trading bot with a **tiered LLM brain** (Gemini Flash + GPT-4o), real-time market data, news sentiment analysis, **Politician Trade Copy Mode** (tracking congressional STOCK Act disclosures), and a premium dark glassmorphism web dashboard.

> ⚠️ **Disclaimer**: Day trading is high risk. ~90% of day traders lose money. This bot does not guarantee profit. Never risk money you cannot afford to lose. Always start with paper trading.

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
cd ai-trading-bot
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy the example env file and add your keys:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | ✅ Yes (Tier 1 LLM) |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | ✅ Yes (Tier 2 LLM) |
| `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` | [alpaca.markets](https://alpaca.markets) | ✅ Yes (broker) |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) | Optional (news) |
| `QUIVER_QUANT_API_KEY` | [quiverquant.com](https://www.quiverquant.com) | Optional (politician data) |
| `TELEGRAM_BOT_TOKEN` | [@BotFather on Telegram](https://t.me/botfather) | Optional (alerts) |

### 3. Edit Config (Optional)

Edit `config/config.yaml` to customize:
- **Watchlist** — which stocks to trade
- **Risk profile** — stop-loss %, take-profit %, max position size
- **LLM providers** — switch between Gemini/OpenAI/Anthropic

### 4. Run the Bot

```bash
# Start the trading bot (runs fully automated)
python -m automation.trading_loop

# In another terminal, start the dashboard
python -m dashboard.app
```

Then open **http://localhost:8080** in your browser.

---

## 🏗 Architecture

```
Market Data (yfinance) ──┐
News (NewsAPI + FinBERT) ─┤
Politician (STOCK Act) ───┤──→ Signal Aggregator ──→ Tier 1 LLM (Gemini Flash)
Macro (VIX, sectors) ─────┘                              │
                                                    High score?
                                                         │ Yes
                                                    Tier 2 LLM (GPT-4o)
                                                         │
                                                    Risk Manager
                                                         │
                                                    Alpaca Bracket Order
                                                         │
                                                    Auto-close @ 3:55 PM
```

## 📂 Project Structure

```
ai-trading-bot/
├── .env                          # API keys (never commit)
├── config/config.yaml            # Bot configuration
├── automation/
│   ├── trading_loop.py           # 🤖 Main bot (run this)
│   ├── data_client.py            # Market data client
│   ├── indicators.py             # Technical indicators
│   └── scanner.py                # Pre-market scanner
├── engine/
│   ├── llm_brain.py              # 🧠 Tiered LLM decision engine
│   └── decision_engine.py        # Legacy decision engine
├── sentiment/
│   └── finbert_client.py         # 📰 News sentiment (FinBERT)
├── politician/
│   └── copy_mode.py              # 🏛️ Congressional trade tracker
├── execution/
│   └── order_manager.py          # 💹 Alpaca order executor
├── notifications/
│   └── alerts.py                 # 📱 Telegram/email alerts
├── dashboard/
│   ├── app.py                    # FastAPI backend
│   └── index.html                # Premium web dashboard
└── requirements.txt
```

## 🏛️ Politician Copy Mode

The bot tracks U.S. congressional stock trade disclosures (STOCK Act) and uses them as trading signals:

- Polls Quiver Quantitative API for new filings
- Scores politicians by historical trading alpha (e.g., Pelosi = 92nd percentile)
- Weights trades by dollar amount and recency
- Blends into the composite signal score

This is **100% legal** — STOCK Act disclosures are public record.

## ⚙️ Configuration

Key settings in `config/config.yaml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `broker.mode` | `paper` | `paper` or `live` — **defaults to paper** |
| `stop_loss_pct` | `0.75` | Stop loss % below entry |
| `take_profit_pct` | `1.5` | Take profit % above entry |
| `max_concurrent_positions` | `3` | Max open positions |
| `politician_mode.enabled` | `true` | Toggle politician signals |

## ⚠️ Risk Warnings

- **PDT Rule**: US accounts under $25,000 are limited to 3 day trades per 5 business days
- **Always start with paper trading** — the bot defaults to Alpaca's paper trading endpoint
- **LLM costs**: ~$3-6/day with the tiered approach (Gemini Flash + GPT-4o)
- **No guarantees**: Past performance does not predict future results
