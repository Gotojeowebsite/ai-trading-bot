# Original User Request

## Initial Request — 2026-06-18T06:24:17Z

Build a **production-ready**, fully autonomous AI day trading bot ("APEX AI") that operates in two phases each trading day: (1) **Morning Deep Research** using advanced AI reasoning models to analyze market conditions, company news/catalysts, and known insider/politician trades, then (2) **Autonomous Day Trading** that buys and sells stocks by itself using the research findings, technical analysis, and day trading strategies — with a premium UI dashboard, newbie-friendly setup wizard, and distributable packages for Windows (.exe with GUI wizard) and Linux (binary with CLI wizard).

An existing codebase exists at the working directory with all core modules already implemented (trading loop, indicators, scanner, LLM brain, order executor, sentiment analysis, politician tracker, notifications, premium dashboard). The primary gaps to address are: (1) no deep morning research capability, (2) no distribution packaging, (3) no setup wizard, (4) only Alpaca broker support (needs Interactive Brokers too), (5) test/production API mismatches that cause test failures, and (6) no macro/sector analysis despite being in the config.

Working directory: /workspaces/ai-trading-bot
Integrity mode: development

## Requirements

### R1. Morning Deep Research Engine
The bot must perform comprehensive pre-market research using advanced AI reasoning models. The team should **evaluate and select the best AI models** for deep market analysis — candidates include Gemini Deep Think (thinking mode), OpenAI o3/o4-mini, Claude with extended thinking, or other advanced reasoning models. The research must cover:
- Overall market conditions and macro analysis (VIX, sector rotation, major indices)
- Company-specific catalyst detection (earnings releases, FDA approvals, product launches, M&A, analyst upgrades/downgrades scheduled for today)
- Insider and politician trade tracking (SEC Form 4 filings, STOCK Act congressional disclosures)
- Sector sentiment and trending themes
- Calendar-aware analysis (knowing what's happening TODAY specifically)

Research findings must be stored in a structured format and feed directly into the trading engine's decision pipeline, replacing or augmenting the current basic Tier 1 screening. The research must run automatically on a configurable schedule before market open.

### R2. Enhanced Autonomous Trading Engine
Extend the existing trading engine to:
- Support **both Alpaca Markets AND Interactive Brokers** as broker backends (user-selectable)
- Integrate the morning deep research signals into the decision pipeline alongside existing technical indicators and sentiment
- Fix the existing test/production API contract mismatches (get_sentiment returning dict vs float, get_politician_signals schema mismatch, execute_bracket_order demo mode bypass)
- Add market holiday calendar awareness
- Implement the macro_context signal that's configured but not computed
- Add rate limiting for LLM API calls
- Ensure all positions auto-close by 3:55 PM EST
- Default to paper trading for safety

### R3. Premium Dashboard Enhancements
Enhance the existing premium dashboard (which is already 8.5/10 quality) to add:
- Morning research findings panel showing today's AI analysis, catalysts, and market outlook
- Interactive charts (zoom, pan, timeframe selection)
- Settings/configuration page accessible from the dashboard
- Trade performance analytics (win rate, average P&L, Sharpe ratio)
- Responsive and visually stunning — maintain the existing dark glassmorphism aesthetic

### R4. Cross-Platform Distribution
Create distributable packages:
- **Windows**: .exe via PyInstaller with a **GUI setup wizard** (walks user through API key entry, broker selection, risk configuration)
- **Linux**: binary or AppImage with a **CLI setup wizard** (same guided setup flow but terminal-based)
- Both must be newbie-friendly — explain what each API key is for, link to signup pages, validate inputs
- Include proper version pinning in requirements
- Remove unused dependencies (beautifulsoup4, aiohttp, apscheduler, websockets)

### R5. Comprehensive Testing & Documentation
- Fix all test/production API mismatches so the full test suite passes
- Add tests for the new morning research engine
- Add tests for Interactive Brokers integration
- Add integration tests for the setup wizard
- Clear README and user guide explaining: what the bot does, how the research works, how to set up, how to monitor, risk warnings

## Acceptance Criteria

### Research Engine
- [ ] A dedicated research module performs pre-market analysis using an advanced AI reasoning model
- [ ] Research covers market conditions, company catalysts, insider trades, and sector analysis
- [ ] Research output is structured (JSON or DB) and consumed by the trading engine
- [ ] Research runs on a schedule before market open (configurable time)
- [ ] The chosen AI model and rationale are documented

### Trading Engine
- [ ] Bot can execute trades through both Alpaca and Interactive Brokers (user selects in config)
- [ ] Morning research signals influence trade decisions (demonstrated via logging/dashboard)
- [ ] Risk management works: stop-loss triggers, circuit breaker halts trading, positions close by 3:55 PM
- [ ] Paper trading mode is the default and works end-to-end
- [ ] Market holiday calendar prevents trading on holidays

### Dashboard
- [ ] Dashboard shows a "Morning Research" panel with today's AI analysis
- [ ] Charts support at least zoom and timeframe selection
- [ ] Dashboard maintains premium visual quality (dark glassmorphism, animations)
- [ ] Performance analytics are displayed (win rate, P&L stats)

### Distribution
- [ ] `pyinstaller` (or equivalent) successfully builds a Windows .exe
- [ ] A Linux binary is buildable
- [ ] Windows GUI setup wizard walks through: API keys → broker selection → risk config → explanation
- [ ] Linux CLI setup wizard provides the same guided flow
- [ ] Setup wizard validates API key format and provides signup links

### Testing
- [ ] All existing unit tests pass without modification to production code contracts
- [ ] All e2e tests pass (fix the test/production API mismatches)
- [ ] New tests exist for the research engine, IB integration, and setup wizard
- [ ] `python main.py status` runs without errors and shows system health
- [ ] Running `python main.py bot` in paper mode starts without crashes

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
