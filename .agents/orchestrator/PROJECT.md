# Project: AI Trading Bot

## Architecture
The system consists of several independent modules coordinating to ingest data, compute indicators, analyze sentiment, track politician trades, make tiered LLM trading decisions, execute orders, and serve a premium web dashboard.

1. **Market Data & Scanner Module (`automation/`)**:
   - Ingests real-time prices via Alpaca WebSocket or yfinance.
   - Computes VWAP, RSI, MACD, Bollinger Bands, EMA, and RVOL.
   - Pre-market scanner runs daily before 9:30 AM EST.
2. **Sentiment Module (`sentiment/`)**:
   - Ingests news headlines and uses FinBERT NLP to calculate per-ticker sentiment.
3. **Politician Copy Module (`politician/`)**:
   - Discovers and scores U.S. congressional trades, weighting them by recency and size.
4. **LLM Engine Module (`engine/`)**:
   - Tier 1 screening (cheap model like Gemini 2.0 Flash) filters for opportunities.
   - Tier 2 decision (premium reasoning model like GPT-4o) evaluates context and outputs trade decisions.
5. **Execution Module (`execution/`)**:
   - Places bracket orders, tracks risk parameters, implements a daily circuit breaker, and closes positions before 3:55 PM EST.
   - Contains a watchdog process to recover from crashes.
6. **Dashboard Module (`dashboard/`)**:
   - Web server (e.g., FastAPI or Flask) with WebSocket support, styled with dark glassmorphism.
   - Displays portfolio, trade log, LLM reasoning, Capitol trades feed, and signal contributions.

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|--------------|--------|-----------------|
| E2E | E2E Testing Track | Design E2E test infra, test cases, and publish `TEST_READY.md` | None | IN_PROGRESS | b9f2644a-4824-4c9c-9046-183e108ae470 |
| M1 | Market Data & Technicals | Alpaca/yfinance ingestion, pre-market scanner, technical indicator library | None | IN_PROGRESS | c11e1ea8-9fb6-45f4-9262-e5419da6bcd1 |
| M2 | News Sentiment | News ingestion, FinBERT sentiment scoring | M1 | PLANNED | TBD |
| M3 | Politician Copy Mode | Congressional trade scraping/ingestion, trade scoring & blending | M1 | PLANNED | TBD |
| M4 | Tiered LLM Engine | Tier 1/2 LLM pipeline, fallback mechanism, prompt construction | M1, M2, M3 | PLANNED | TBD |
| M5 | Automated Execution | Alpaca bracket order client, risk controls, daily circuit breaker, pre-close logic, watchdog | M4 | PLANNED | TBD |
| M6 | Glassmorphism Dashboard | Dashboard web server, UI styling, real-time WebSockets, controls | M5 | PLANNED | TBD |
| M7 | Integration & Hardening | Final integration, pass 100% E2E tests, Tier 5 adversarial hardening | E2E, M1-M6 | PLANNED | TBD |

## Interface Contracts
### `automation/indicators.py`
- `def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame`: Computes VWAP, RSI, MACD, Bollinger Bands, EMA, and RVOL on raw OHLCV price histories.

### `sentiment/finbert_client.py`
- `def get_sentiment(ticker: str) -> float`: Returns a sentiment score between -1.0 (extremely negative) and +1.0 (extremely positive).

### `politician/copy_mode.py`
- `def get_politician_signals(ticker: str) -> dict`: Returns latest congressional trade disclosures for the ticker, scored weight, and recency.

### `engine/decision_engine.py`
- `def screen_ticker(ticker: str, data: dict) -> float`: Tier 1 screening score (0.0 to 1.0).
- `def make_decision(ticker: str, data: dict) -> dict`: Tier 2 premium JSON decision with keys: `action` (BUY/SELL/HOLD), `confidence`, `entry_price`, `stop_loss`, `take_profit`, `position_size`, and `reasoning`.

### `execution/order_manager.py`
- `def execute_bracket_order(ticker: str, side: str, qty: int, take_profit: float, stop_loss: float) -> str`: Places entry, profit-taking, and stop-loss orders on Alpaca.
- `def close_all_positions() -> None`: Immediate market orders to close out all open holdings.

## Code Layout
- `automation/`: Ingestion, indicators, pre-market scanning
- `sentiment/`: News gathering, FinBERT analysis
- `politician/`: Politician copy trading data and signals
- `engine/`: Tiered LLM decision pipeline
- `execution/`: Order placing, risk compliance, watchdog
- `dashboard/`: Web dashboard server and templates
- `config/`: Config files and `.env` loader
- `tests/`: Integrated E2E testing and unit test suites
