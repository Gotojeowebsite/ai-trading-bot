# Scope: E2E Testing Track

## Architecture
The E2E test suite acts as an opaque-box testing framework that verifies the system's requirements (R1-R5) without relying on internal implementation details. The test suite operates using:
1. **Mock Services**: Simulates APIs for Alpaca, Interactive Brokers, news sources, politician disclosures, LLM brain reasoning models, and morning deep research.
2. **CLI Runner**: Simulates launching the application in various modes (`bot`, `scan`, `status`, `dashboard`).
3. **Web Interface Client**: Simulates interacting with REST and WebSocket endpoints on the dashboard.
4. **Setup Wizard Drivers**: Simulates interactive console inputs for the Linux CLI wizard and GUI key configurations for the Windows setup wizard.

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|--------------|--------|-----------------|
| S1 | E2E Design & Mock Extensions | Design test cases for R1-R5 (Tiers 1-4) and expand `mocks/mock_server.py` to support IB, morning research, and wizard inputs | None | DONE | b24f45f6-41a7-40df-92d6-b8d127d2383d |
| S2 | Tier 1 Feature Coverage Tests | Implement Tier 1 tests for Morning Research, IB backend selection, dashboard analytics, settings configuration, and setup wizards | S1 | VERIFYING | b0ca6ae8-730f-45a2-962d-9bf7487ae93e |
| S3 | Tier 2 Boundary & Corner Tests | Implement Tier 2 tests for rate limiting, missing config, holiday trade blocking, and invalid setup wizard credentials | S2 | VERIFYING | b0ca6ae8-730f-45a2-962d-9bf7487ae93e |
| S4 | Tier 3 & 4 E2E Scenarios | Implement Tier 3 (cross-feature) and Tier 4 (full day trading lifecycle) tests including morning research and IB execution | S3 | VERIFYING | b0ca6ae8-730f-45a2-962d-9bf7487ae93e |
| S5 | Final Suite Validation & Publication | Run E2E test suite, ensure 100% passes, and publish `TEST_READY.md` to project root | S4 | PLANNED | TBD |

## Interface Contracts
### E2E Test Framework
- Test runner invocation: `pytest tests/e2e`
- Config file: `config/config.yaml` / environment variables
- Database file: `test_trading.db`
