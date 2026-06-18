# Scope: M1: API Mismatch & Cleanup

## Architecture
The APEX AI trading bot integrates data client scanner, news sentiment client, congressional politician disclosures copy trading tracker, LLM brain for screening and decisions, order manager for bracket orders, and a FastAPI web dashboard.
The API mismatch issues lie in:
- `sentiment/finbert_client.py`: The `get_sentiment(ticker)` function returns a dictionary, but unit/E2E tests expect a float directly.
- `politician/copy_mode.py`: The `get_politician_signals(ticker, config)` function returns a dictionary lacking schema keys expected by the tests (`ticker`, `signal_score`, `trade_type`).
- `execution/order_manager.py` / `tests/e2e/conftest.py`: The order manager falls back to demo mode instead of contacting the mock server because of missing Alpaca API keys in the environment.
- Settings database table: The tests attempt to write to the `settings` table, which is not initialized correctly or exists under a different context. We will ensure the `settings` table is created in database setups.
- Monkeypatch namespace: In `test_sentiment_cache`, the monkeypatching of `sentiment.finbert_client.get_sentiment` is ineffective because `test_tier1_feature.py` imports `get_sentiment` directly.
- Syntax Error: `test_llm_context_window_overflow` has a dictionary multiplication syntax bug.
- Port contention: Port 8000 is occupied by an orphaned python process, causing dashboard tests to fail.

## Milestones
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|--------------|--------|-----------------|
| 1 | Fix API Mismatches & Code Cleanup | Fix the 9 failing tests and clean up requirements.txt | None | PLANNED | TBD |

## Local Tasks (Decomposition)
- **Task 1: Sentiment Client API Mismatch**: Create `SentimentResult` class inheriting from `float` that supports dict-like key-value lookup for backward compatibility and test validation, and return it from `get_sentiment`.
- **Task 2: Politician Client API Schema Mismatch**: Update `get_politician_signals` to return a dictionary containing both the production keys (`composite_score`, `trades`, `direction`) and test-expected keys (`ticker`, `signal_score`, `trade_type`).
- **Task 3: Order Manager Demo Fallback**: Inject dummy `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` into the environment inside `tests/e2e/conftest.py` mock server setup to prevent the executor from falling back to demo mode.
- **Task 4: Settings DB Table Initialization**: Ensure the `settings` table is properly defined and created in `tests/e2e/conftest.py` (which is already there, but we will verify why it's missing or if there's any other DB init that needs it).
- **Task 5: Monkeypatch Namespace Resolution**: Adjust `test_sentiment_cache` to patch `"tests.e2e.test_tier1_feature.get_sentiment"` instead of `"sentiment.finbert_client.get_sentiment"`.
- **Task 6: Context Window Overflow Syntax Fix**: Correct `large_context = {"indicators": {"vwap": 1.0} * 1000}` to a valid dict comprehension `large_context = {"indicators": {f"vwap_{i}": 1.0 for i in range(1000)}}`.
- **Task 7: Port 8000 Conflict Resolution**: Update `dashboard_server` fixture in `tests/e2e/conftest.py` to kill any process currently occupying port 8000 using `fuser` before launching the dashboard server.
- **Task 8: Clean up requirements.txt**: Remove unused dependencies (`beautifulsoup4`, `aiohttp`, `apscheduler`, `websockets`) from `requirements.txt`.
