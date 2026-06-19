# 🧠 APEX AI — Autonomous Day Trading Bot

A fully autonomous AI-powered day trading bot with a **tiered LLM brain** (Gemini Flash + GPT-4o), real-time market data, news sentiment analysis, **Politician Trade Copy Mode** (tracking congressional STOCK Act disclosures), and a premium dark glassmorphism web dashboard.

> ⚠️ **Disclaimer**: Day trading is high risk. ~90% of day traders lose money. This bot does not guarantee profit. Never risk money you cannot afford to lose. Always start with paper trading.

---

## 🚀 Installation & Setup Guide

### 1. Prerequisites
Ensure you have the following installed on your system:
- **Python 3.10+** (Recommended: 3.11 or 3.12)
- **Git**

### 2. Clone the Repository
Clone the project to your local machine:
```bash
git clone https://github.com/yourusername/ai-trading-bot.git
cd ai-trading-bot
```

### 3. Install Dependencies
It is highly recommended to use a virtual environment to avoid conflicts:
```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install the required packages
pip install -r requirements.txt
```

### 4. Configuration & API Keys
The bot requires API keys to function. The easiest way to configure everything is using the built-in [Setup Wizard](setup_wizard/gui_wizard.py):

```bash
python main.py setup
```
*(This launches an interactive GUI or CLI wizard that will prompt you for your keys and save them securely to `.env` and `config/config.yaml`.)*

Alternatively, you can manually copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | ✅ Yes (Tier 1 LLM) |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | ✅ Yes (Tier 2 LLM) |
| `ALPACA_API_KEY` & `SECRET` | [alpaca.markets](https://alpaca.markets) | ✅ Yes (if using Alpaca) |
| `IB_ACCOUNT_ID` | [interactivebrokers.com](https://www.interactivebrokers.com/) | ✅ Yes (if using IBKR) |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) | Optional (news sentiment) |
| `QUIVER_QUANT_API_KEY` | [quiverquant.com](https://www.quiverquant.com) | Optional (politician data) |

### 5. Running the Bot

The bot has two primary components: the autonomous trading loop and the web dashboard. Open two terminal windows and run:

**Terminal 1 (Trading Engine):**
```bash
python main.py bot
```
*(This starts the autonomous [Trading Loop](automation/trading_loop.py) which scans the market, evaluates signals, and executes trades.)*

**Terminal 2 (Dashboard):**
```bash
python main.py dashboard
```
*(This starts the [FastAPI Dashboard Backend](dashboard/app.py). Open **http://localhost:8080** in your browser to view the live interface.)*

---

## 🧠 How It Works

The APEX AI Trading Bot uses a **Tiered Decision Engine** to analyze the market and execute trades autonomously:

1. **Pre-market Research**: Before the market opens, the [Research Engine](engine/research_engine.py) uses an LLM (OpenAI/Anthropic) to analyze macro trends, VIX, and sector outlooks, generating a baseline `macro_context` score.
2. **Live Data & Indicators**: The [Data Client](automation/data_client.py) streams real-time pricing for your watchlist and computes technical indicators (RSI, MACD, VWAP) via the [Indicators Module](automation/indicators.py).
3. **Sentiment & Politician Tracking**: The bot fetches live news sentiment via FinBERT ([Finbert Client](sentiment/finbert_client.py)) and tracks US Congressional trades via the [Copy Mode Module](politician/copy_mode.py).
4. **Tier 1 LLM Screening**: The aggregated signals are fed into a fast, cheap LLM (Gemini Flash) in the [LLM Brain](engine/llm_brain.py) for initial screening. 
5. **Tier 2 LLM Reasoning**: If Tier 1 identifies a high-probability setup, the data is escalated to a premium LLM (GPT-4o or Claude 3.5 Sonnet) for deep reasoning and final trade conviction.
6. **Execution & Risk Management**: If conviction is high, the [Order Manager](execution/order_manager.py) sends a bracket order (with strict stop-loss and take-profit) to Alpaca or Interactive Brokers. All positions are forcefully liquidated at 3:55 PM EST to avoid overnight risk.

---

## 🤖 LLM Recommendations by Process

APEX AI uses a multi-agent, tiered approach. You can mix and match models in `config/config.yaml` to optimize for speed, intelligence, and cost. Here are the recommended models for each specific task:

### 1. Pre-market Research Engine (Deep Thinking & Extended Reasoning)
**Goal:** Ingest heavy financial data, conduct deep multi-step reasoning to establish macro trends, and output structured JSON to inform the bot's trading parameters for the day.
* **🥇 Top Pick:** `o1` / `o3-mini` (OpenAI with "high" reasoning effort) or `claude-3-7-sonnet` (Anthropic with extended thinking enabled). These models are designed specifically to "think" deeply before answering, making them perfect for analyzing complex pre-market news, catalysts, and sector trends.
* **🥈 Alternative:** `gemini-2.0-flash-thinking` (Google). Excellent reasoning capabilities with a very large context window for pulling in historical macro reports.

### 2. Tier 1 LLM Engine (High-Frequency Screening)
**Goal:** Extremely low latency, high throughput, and cost efficiency. This model runs continuously on a loop, filtering out the noise.
* **🥇 Top Pick:** `gemini-2.0-flash` (Google). The absolute best combination of lightning-fast latency and incredibly cheap API costs, making it ideal for processing thousands of tickers a day.
* **🥈 Alternative:** `gpt-4o-mini` (OpenAI) or `claude-3-5-haiku` (Anthropic). Fast and cheap, suitable for initial binary screening (Trade / Pass).

### 3. Tier 2 LLM Engine (Final Execution Conviction)
**Goal:** State-of-the-art intelligence, low hallucination, and complex financial logic. Runs only when Tier 1 approves a trade setup, so cost and latency are less critical here.
* **🥇 Top Pick:** `gpt-4o` (OpenAI) or `claude-3-5-sonnet-20241022` (Anthropic). These flagship models provide the highest reasoning capabilities and are excellent at respecting strict risk-management guardrails before executing capital.
* **🥈 Alternative:** `gemini-1.5-pro` (Google). Extremely strong reasoning with a massive context window if you inject large amounts of historical price action context.

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
│   ├── order_manager.py          # 💹 Broker abstraction
│   └── ib_executor.py            # 💹 Interactive Brokers executor
├── notifications/
│   └── alerts.py                 # 📱 Telegram/email alerts
├── setup_wizard/
│   ├── cli_wizard.py             # 🪄 Setup wizard CLI
│   └── gui_wizard.py             # 🪄 Setup wizard GUI
├── dashboard/
│   ├── app.py                    # FastAPI backend
│   └── index.html                # Premium web dashboard
├── main.py                       # 🚀 Main entry point CLI
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
