# Scope: E2E Testing Track

## Architecture
- **Pytest**: Running and orchestrating E2E test files.
- **Offline Mocks**: Using local HTTP servers and socket simulators to mock Alpaca, Interactive Brokers, OpenAI/Gemini, and FinBERT.
- **SQLite Isolation**: Standardized `test_trading.db` ensures database isolation for tests.

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|-------------|--------|-----------------|
| M_INFRA | E2E Test Infra & Mocks | Review existing conftest.py and mocks; verify that the test runner environment is solid and mocks are responsive. | None | PLANNED | TBD |
| M_TIER1 | Tier 1: Feature Coverage | Implement 20 tests (5 per new feature) covering FEAT-RESEARCH, FEAT-IB, FEAT-DASH-NEW, FEAT-WIZARD. | M_INFRA | PLANNED | TBD |
| M_TIER2 | Tier 2: Boundary & Corner Cases | Implement 20 tests (5 per new feature) covering rate limiting, timeouts, invalid configurations, empty inputs, and failed requests. | M_TIER1 | PLANNED | TBD |
| M_TIER3 | Tier 3: Cross-Feature Combinations | Implement 6 tests covering pairwise interactions between the new modules (e.g. Research -> IB orders, Wizard -> Settings -> Dashboard). | M_TIER2 | PLANNED | TBD |
| M_TIER4 | Tier 4: Real-World Scenarios | Implement 5 comprehensive day-long or setup-to-execution workflows verifying the system end-to-end. | M_TIER3 | PLANNED | TBD |

## Interface Contracts
- **`engine/research_engine.py`**:
  - `run_morning_research(provider, model) -> dict`
  - `get_today_research() -> dict`
- **`execution/ib_executor.py`**:
  - `class IBExecutor`: constructor, `get_account`, `get_positions`, `place_bracket_order`, `close_position`, `close_all_positions`, `cancel_all_orders`
- **`dashboard/app.py`**:
  - `/api/research` -> Returns morning research results
  - `/api/analytics` -> Returns performance statistics (win rate, Sharpe, drawdown, average P&L)
  - `/api/settings` -> GET / POST configuration parameters
- **`automation/setup_wizard.py`**:
  - `CLISetupWizard().run()`
  - `GUISetupWizard().run()`
