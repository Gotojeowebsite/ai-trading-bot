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
