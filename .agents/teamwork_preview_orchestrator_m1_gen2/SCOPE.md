# Scope: M1: API Mismatch & Cleanup

## Architecture
The bot contains:
- `sentiment/finbert_client.py`: news sentiment analyzer.
- `politician/copy_mode.py`: congressional politician copy-trading tracker.
- `main.py`: LLM brain screening/decision loop.
- `execution/order_manager.py`: bracket order executor.
- `dashboard/`: FastAPI web server and websocket updates.

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|--------------|--------|-----------------|
| 1 | Fix Failing Tests | Fix the 9 failing unit/E2E tests and ensure all compile/pass. | None | IN_PROGRESS | a0af88bf-9fee-41a4-90df-1e448102a009 |

## Local Tasks (Decomposition)
- **Task 1: Politician Client Quiver Error Fallback**: Fix `politician/copy_mode.py` so that status code errors on congress disclosures fetch return empty list `[]` instead of falling back to demo trades, resolving `test_politician_corrupt_data` and `test_llm_tier1_screening`.
- **Task 2: Politician Client Date Check Bypass**: Fix `politician/copy_mode.py` date validation bypass where `RecencyScore` causes future/historic trades to bypass date validation, resolving `test_politician_future_disclosed_date` and `test_politician_historic_trades`.
- **Task 3: Dashboard REST Portfolio Endpoint Mismatch**: Fix `dashboard` endpoint or test `test_dash_rest_portfolio` to align key structure (e.g. flat cash vs nested account cash).
- **Task 4: Dashboard Empty DB State /api/trades Endpoint Mismatch**: Check `test_dash_empty_db_state` and ensure the `/api/trades` route exists or is correctly called, returning 200.
- **Task 5: Dashboard Websocket Paths Mismatch**: Check `test_dash_websocket_updates` and `test_comb_bracket_order_update_reflects_in_dashboard` websocket connection endpoints. Align FastAPI websocket paths with test connections.
- **Task 6: Combinatorial Scanner Sentiment Monkeypatch Subprocess Issue**: Fix `test_comb_scanner_to_sentiment` where pytest monkeypatch doesn't affect subprocess `main.py` execution.
