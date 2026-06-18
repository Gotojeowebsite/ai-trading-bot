# Project: APEX AI Trading Bot Features (R1-R5)

## Architecture
The APEX AI trading bot consists of a core trading loop, a data client, technical indicators, pre-market scanner, news sentiment client, politician disclosures tracker, and a tiered LLM brain. The new components add a Morning Deep Research Engine, Interactive Brokers integration, dashboard upgrades (research panels, interactive charts, configuration pages, analytics), cross-platform setup wizards (GUI for Windows, CLI for Linux), holiday awareness, rate limiting, and macro context calculation.

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|--------------|--------|-----------------|
| E2E | E2E Testing Track | Design E2E test infra, write Tiers 1-4 tests for all new requirements, publish `TEST_READY.md` | None | IN_PROGRESS | TBD |
| M1 | API Mismatch & Cleanup | Fix existing E2E test failures, resolve sentiment/politician API mismatches, fix settings DB, fix test syntax/port conflicts, cleanup requirements.txt | None | IN_PROGRESS | TBD |
| M2 | Morning Deep Research Engine | Choose/evaluate AI reasoning model, build research module for market/macro/catalyst/insider trade analysis, run schedule, store results | M1 | PLANNED | TBD |
| M3 | Enhanced Trading Engine | Support Alpaca & Interactive Brokers, holiday calendar awareness, rate limiting, EOD close by 3:55 PM, compute macro_context, default paper trading | M1, M2 | PLANNED | TBD |
| M4 | Premium Dashboard | Morning research findings panel, interactive charts (zoom/pan), settings page, trade analytics (win rate, average P&L, Sharpe), glassmorphism | M1, M2, M3 | PLANNED | TBD |
| M5 | Cross-Platform Distribution | Windows GUI setup wizard / PyInstaller .exe, Linux CLI setup wizard / binary, validate keys, links | M1, M2, M3, M4 | PLANNED | TBD |
| M6 | Integration & Hardening | Final integration, pass 100% E2E tests, Tier 5 adversarial coverage hardening, user guide & documentation | E2E, M1-M5 | PLANNED | TBD |

## Interface Contracts
### `engine/research_engine.py`
- `def run_morning_research() -> dict`: Executes deep research via AI reasoning model and returns a dictionary of macro, catalyst, and insider findings.
- `def get_today_research() -> dict`: Retrieves today's research findings from storage (JSON/SQLite).

### `execution/ib_executor.py` (New)
- `class IBExecutor(BaseExecutor)`: Implements order execution, position queries, and bracket orders for Interactive Brokers API.

### `execution/order_manager.py` (Updated)
- `def execute_bracket_order(ticker: str, side: str, qty: int, take_profit: float, stop_loss: float, broker: str = "alpaca") -> str`: Delegates execution to either Alpaca or Interactive Brokers based on configuration.
- `def close_all_positions(broker: str = "alpaca") -> None`: Closes positions on the active broker.

### `automation/trading_loop.py` (Updated)
- `def is_market_holiday(date) -> bool`: Checks if the date is a US stock market holiday.
- `def calculate_macro_context() -> float`: Returns a score between -1.0 and 1.0 representing macro market environment.

### `dashboard/app.py` (Updated)
- `/api/research`: Endpoint returning today's morning research findings.
- `/api/analytics`: Endpoint returning performance metrics (win rate, average P&L, Sharpe).
- `/api/settings`: GET/POST for configuration parameters.

## Code Layout
- `automation/`: Ingestion, indicators, pre-market scanning, market holiday checks
- `sentiment/`: News gathering, FinBERT analysis
- `politician/`: Politician copy trading data and signals
- `engine/`: Tiered LLM decision pipeline, morning deep research engine
- `execution/`: Order placing (Alpaca + IB), risk compliance, watchdog
- `dashboard/`: Web dashboard server and templates
- `distribution/`: Windows GUI Setup Wizard, Linux CLI Setup Wizard, build scripts
- `config/`: Config files and `.env` loader
- `tests/`: Integrated E2E testing and unit test suites
