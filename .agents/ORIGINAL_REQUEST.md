# Original User Request

## Initial Request — 2026-06-14T08:32:55Z

Build a **production-quality, fully autonomous AI day-trading bot** that runs the entire trading day without human intervention. The bot ingests real-time market data, financial news, and U.S. congressional stock trade disclosures. It uses a **tiered LLM architecture** (cheap fast model for continuous scanning, premium model for actual trade decisions) to reason through all signals and autonomously execute buy/sell orders via the Alpaca Markets API. The system includes a **premium dark glassmorphism web dashboard** that displays live portfolio data, the LLM's reasoning for each trade, a politician trades feed, and signal visualizations.

Working directory: /home/mint/Desktop/ai-trading-bot
Integrity mode: development

## Requirements

### R1. Real-Time Market Data & Technical Analysis
The bot must connect to live market data (via Alpaca Markets WebSocket API or yfinance) and continuously compute day-trading-optimized technical indicators on a per-ticker basis, including at minimum: VWAP, MACD, RSI, Bollinger Bands, EMA crossovers, and Relative Volume (RVOL). It must also run a pre-market scanner each morning (before 9:30 AM EST) that identifies the top stocks to watch based on gap percentage, volume, and news catalysts.

### R2. News Sentiment Analysis
The bot must ingest financial news headlines from at least one news API (e.g., NewsAPI, Finnhub) and compute per-ticker sentiment scores using an NLP model suitable for financial text (e.g., FinBERT). Sentiment scores must be continuously updated and fed into the decision pipeline.

### R3. Politician Trade Copy Mode
The bot must track U.S. congressional stock trade disclosures (STOCK Act filings) via a public data source (e.g., Quiver Quantitative API, Capitol Trades, or web scraping of public records). It must score each politician's historical trading performance, weight their trades by recency and dollar amount, and blend this signal into the overall decision pipeline. The dashboard must have a dedicated panel showing the latest congressional trades and their influence on bot decisions.

### R4. Tiered LLM Decision Engine
The bot must implement a two-tier LLM architecture:
- **Tier 1 (screening)**: A fast, cost-effective model (e.g., Gemini 2.0 Flash) that runs frequently (every 30–60 seconds per stock) to identify whether a signal warrants deeper analysis.
- **Tier 2 (decision)**: A premium reasoning model (e.g., GPT-4o) that is called only when Tier 1 flags a high-confidence opportunity. Tier 2 receives a full structured market briefing (technicals, sentiment, politician data, portfolio state) and returns a structured JSON decision with: action (BUY/SELL/HOLD), confidence score, entry price, stop-loss, take-profit, position size, and a natural-language reasoning explanation.

The system must support configurable LLM providers via API keys stored in a `.env` file, and must include a fallback mechanism if the primary LLM API is unavailable.

### R5. Fully Automated Order Execution
The bot must autonomously execute trades via the Alpaca Markets API with zero human intervention:
- Place **bracket orders** (entry + stop-loss + take-profit) so that exits are managed server-side by Alpaca.
- Automatically close all open positions before market close (by 3:55 PM EST) — no overnight holds.
- Enforce risk management rules: maximum single-position size, daily loss circuit breaker, and PDT rule awareness.
- Support both **paper trading** (default) and **live trading** modes, switchable via configuration.
- Include a watchdog/error-recovery mechanism that ensures positions are never left unmanaged if the bot crashes.

### R6. Premium Web Dashboard
The bot must serve a web-based dashboard with a **dark glassmorphism aesthetic** (frosted glass panels, deep navy/purple palette, smooth animations, modern typography). The dashboard must include:
- Live portfolio value chart and today's P&L
- The LLM's reasoning explanation for each trade decision (displayed verbatim)
- A Capitol Hill / Politician trades feed panel
- Signal breakdown visualization per stock (showing each indicator's contribution)
- A trade log with full history
- A control panel to toggle Politician Copy Mode, adjust risk level, and manage the watchlist
- Real-time updates via WebSocket

### R7. Configuration & Notifications
The bot must be configurable via YAML config files and a `.env` file for API keys. It must support optional Telegram and/or email notifications for: trade executions, daily P&L summary, and circuit breaker alerts. Include clear setup instructions so a user can configure API keys and start the bot.

## Acceptance Criteria

### Core Automation
- [ ] Running `python -m automation.trading_loop` (or equivalent entry point) starts the full bot loop without requiring any interactive input
- [ ] The bot connects to a market data source and receives price updates for at least one ticker
- [ ] Technical indicators (at minimum VWAP, RSI, MACD) are computed and update on new price data
- [ ] The Tier 1 LLM is called with signal data and returns a screening score
- [ ] When Tier 1 flags an opportunity, the Tier 2 LLM is called with a full market briefing and returns a structured JSON decision
- [ ] The bot places bracket orders via the Alpaca API (paper mode) when the LLM decides BUY
- [ ] The bot automatically closes all positions before market close
- [ ] A watchdog mechanism detects crashes and prevents positions from being left unmanaged

### Intelligence Layers
- [ ] News headlines are fetched from at least one source and sentiment scores are computed per ticker
- [ ] Politician trade data is fetched from a public source and integrated into the signal pipeline
- [ ] The LLM briefing prompt includes technicals, sentiment, politician data, and portfolio state
- [ ] The LLM's natural-language reasoning is captured and stored for each decision

### Dashboard
- [ ] Running the dashboard serves a web page accessible at `http://localhost:<port>`
- [ ] The dashboard uses a dark color scheme with glassmorphism-style design elements (frosted glass, blur effects, gradients)
- [ ] The dashboard displays live portfolio data, trade log, and LLM reasoning text
- [ ] The dashboard includes a politician trades feed panel
- [ ] The dashboard updates in real-time via WebSocket (no manual page refresh needed)

### Configuration & Setup
- [ ] API keys are loaded from a `.env` file (not hardcoded)
- [ ] A `config.yaml` (or similar) controls watchlist, risk parameters, and LLM provider selection
- [ ] A README with setup instructions is provided
- [ ] The bot defaults to paper trading mode and requires explicit configuration change to enable live trading

### Verification
- [ ] All Python files pass syntax checking (`python -m py_compile <file>`)
- [ ] The project has a `requirements.txt` (or equivalent) and dependencies install without errors via `pip install -r requirements.txt`
- [ ] The dashboard HTML/CSS/JS loads without console errors in a browser

## Follow-up — 2026-06-18T14:51:47Z

Continue building the existing **APEX AI** autonomous day-trading bot into the absolute best trading bot possible. The existing codebase at the working directory is fully built with all core modules (trading loop, indicators, scanner, tiered LLM brain, order executor, sentiment analysis, politician tracker, notifications, premium dashboard). The primary goals are: (1) add a deep morning research engine, (2) elevate the dashboard to Bloomberg Terminal-grade quality, (3) add full Interactive Brokers support alongside Alpaca, (4) create distributable packages for Windows (.exe with GUI wizard) and Linux (binary with CLI wizard), and (5) fix all test failures and add comprehensive new tests.

Working directory: /home/umanzor/ai-trading-bot
Integrity mode: development

## Requirements

### R1. Morning Deep Research Engine
The bot must perform comprehensive pre-market research using advanced AI reasoning models. The existing tiered LLM system supports Gemini, OpenAI, and Claude — the team should leverage the best model for deep analysis (candidates: Gemini 2.5 Pro with thinking, OpenAI o3/o4-mini, Claude with extended thinking). The research must cover:
- Overall market conditions and macro analysis (VIX, sector rotation, major indices)
- Company-specific catalyst detection (earnings, FDA approvals, M&A, analyst actions scheduled for today)
- Insider and politician trade tracking (SEC Form 4, STOCK Act congressional disclosures)
- Sector sentiment and trending themes
- Calendar-aware analysis (knowing what's happening TODAY specifically)

Research findings must be stored as structured JSON and feed directly into the trading engine's decision pipeline. The research must run automatically on a configurable schedule before market open.

### R2. Enhanced Trading Engine
Extend the existing trading engine to:
- Support **both Alpaca Markets AND Interactive Brokers** as broker backends (user-selectable in config), using the `ib_insync` library for IB integration with full order execution
- Integrate the morning research signals into the decision pipeline alongside existing technical indicators and sentiment
- Fix the existing test/production API contract mismatches (get_sentiment returning dict vs float, get_politician_signals schema mismatch, execute_bracket_order demo mode bypass)
- Add market holiday calendar awareness
- Implement the macro_context signal that's configured but not computed
- Add rate limiting for LLM API calls
- Ensure all positions auto-close by 3:55 PM EST
- Default to paper trading for safety

### R3. Bloomberg Terminal-Grade Dashboard
Elevate the existing premium dashboard (dark glassmorphism, FastAPI backend, WebSocket) to an absolute **10/10 Bloomberg Terminal-grade trading interface**:
- Morning research findings panel showing today's AI analysis, catalysts, and market outlook
- Interactive candlestick charts with zoom, pan, and timeframe selection
- Real-time P&L tracker with live animations and smooth number transitions
- Trade performance analytics (win rate, Sharpe ratio, max drawdown, average P&L per trade, equity curve)
- Heatmap visualization for watchlist performance
- Settings/configuration page accessible from the dashboard
- Particle effects, gradient animations, and micro-interactions throughout
- Live WebSocket updates with smooth data transitions (no page refreshes)
- Responsive layout that works beautifully on desktop and tablet
- Maintain and enhance the existing dark glassmorphism aesthetic

### R4. Cross-Platform Distribution
Create distributable packages:
- **Windows**: .exe via PyInstaller with a **GUI setup wizard** (Tkinter or similar) that walks users through API key entry, broker selection (Alpaca vs IB), risk configuration — with explanations of what each key does and links to signup pages
- **Linux**: binary or AppImage with a **CLI setup wizard** providing the same guided setup flow in the terminal
- Both must be newbie-friendly: explain terminology, validate API key formats, provide direct signup URLs
- Proper version pinning in requirements.txt
- Remove unused dependencies (beautifulsoup4, aiohttp, apscheduler, websockets if not used)

### R5. Comprehensive Testing & Documentation
- Fix all test/production API mismatches so the existing test suite passes
- Add tests for the morning research engine
- Add tests for Interactive Brokers integration
- Add integration tests for the setup wizard
- Clear README and user guide: what the bot does, how morning research works, setup instructions, monitoring guide, risk warnings

## Acceptance Criteria

### Research Engine
- [ ] A dedicated research module performs pre-market analysis using an advanced AI reasoning model
- [ ] Research covers market conditions, company catalysts, insider trades, and sector analysis
- [ ] Research output is structured JSON consumed by the trading engine
- [ ] Research runs on a configurable schedule before market open
- [ ] The chosen AI model and rationale are documented

### Trading Engine
- [ ] Bot can execute trades through both Alpaca and Interactive Brokers (user selects in config)
- [ ] Morning research signals influence trade decisions (demonstrated via logging and dashboard)
- [ ] Risk management works: stop-loss triggers, circuit breaker halts trading, positions close by 3:55 PM
- [ ] Paper trading mode is the default and works end-to-end
- [ ] Market holiday calendar prevents trading on holidays
- [ ] `ib_insync` is used for Interactive Brokers with bracket order support

### Dashboard
- [ ] Dashboard shows a "Morning Research" panel with today's AI analysis
- [ ] Charts are interactive candlestick charts with zoom, pan, and timeframe selection
- [ ] Dashboard visual quality is Bloomberg Terminal-grade (particle effects, glassmorphism, animations)
- [ ] Performance analytics display win rate, P&L stats, Sharpe ratio, equity curve
- [ ] Settings page allows runtime configuration changes
- [ ] WebSocket delivers real-time updates with smooth animated transitions

### Distribution
- [ ] PyInstaller successfully builds a Windows .exe
- [ ] A Linux binary or AppImage is buildable
- [ ] Windows GUI setup wizard walks through: API keys → broker selection → risk config with explanations
- [ ] Linux CLI setup wizard provides the same guided flow
- [ ] Setup wizard validates API key format and provides signup links

### Testing
- [ ] All existing unit tests pass after fixing API contract mismatches
- [ ] New tests exist for research engine, IB integration, and setup wizard
- [ ] `python main.py status` runs without errors and shows system health
- [ ] `python main.py bot` in paper mode starts without crashes
