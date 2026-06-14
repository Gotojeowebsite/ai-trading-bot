# Scope: E2E Testing Track

## Architecture
- The E2E testing framework uses `pytest` for orchestrating and running all test cases.
- Opaque-box / requirement-driven approach: Tests run the bot's CLI or API entry points as external processes or clients, feeding them mock market and sentiment data and checking their database/logs/API side-effects.
- Mocks and Simulators:
  - Mock Alpaca API server (mocking REST order placement and WS trade events).
  - Mock LLM responses (simulating Tier 1 screening and Tier 2 JSON decisions).
  - Mock News and Politician trade feeds.
  - Offline database configuration for test isolation.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M_INFRA | E2E Test Infra & Runner | Pytest configuration, mock servers/fixtures, entry point schema, and folder setup under `tests/e2e/`. | None | PLANNED |
| M_TIER1 | Tier 1: Feature Coverage | Implement 30 test cases (5 per feature) covering FEAT-SCAN, FEAT-SENT, FEAT-POLY, FEAT-LLM, FEAT-EXEC, FEAT-DASH. | M_INFRA | PLANNED |
| M_TIER2 | Tier 2: Boundary & Corner Cases | Implement 30 test cases (5 per feature) covering error conditions, rate limits, empty responses, API timeouts, invalid payloads. | M_TIER1 | PLANNED |
| M_TIER3 | Tier 3: Cross-Feature Combinations | Implement 6 test cases for pairwise feature interactions. | M_TIER2 | PLANNED |
| M_TIER4 | Tier 4: Real-World Scenarios | Implement 5 comprehensive end-to-end trading day simulations and workloads. | M_TIER3 | PLANNED |

## Interface Contracts
The E2E tests target the following system entry points:
1. `main.py --mode scan`: Pre-market scan, outputs selected tickers to DB or file.
2. `main.py --mode trade`: Core trading loop (ingests signals, calls LLM, places orders).
3. `main.py --mode dashboard`: Dashboard server (FastAPI/Flask) listening on port 8000.
4. Dashboard endpoints:
   - `GET /api/portfolio`: Current value, cash, positions.
   - `GET /api/trades`: Trade logs.
   - `GET /api/signals`: Live NLP, technical, and Capitol trade scores.
   - `WS /ws/updates`: Real-time WebSocket connection for dashboard UI.
