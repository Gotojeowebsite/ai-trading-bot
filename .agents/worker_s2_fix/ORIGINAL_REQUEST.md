## 2026-06-18T06:40:28Z
You are worker_s2_fix (archetype: teamwork_preview_worker).
Your working directory is `/workspaces/ai-trading-bot/.agents/worker_s2_fix`.
Your mission is to execute a complete rewrite and redesign of the E2E test suite to address the review feedback and ensure complete integrity:

1. **Do NOT modify any production source code** (specifically, do not modify `dashboard/app.py` or any other file outside the `tests/` directory).
2. **Implement Database Isolation**: In `tests/e2e/conftest.py`, add a monkey-patch override for `dashboard.app.get_db` to make it return `sqlite3.connect(os.environ.get("DATABASE_PATH", "test_trading.db"))`. This isolates the dashboard database connections during test runs.
3. **Correct Test Database Schema**: In `tests/e2e/conftest.py` inside the `clean_database` fixture, update the SQL schemas to drop and recreate modern tables (`scanned_tickers`, `trades`, `decisions`, `portfolio_snapshots`, `signals`, `settings`) matching the structure queried by the dashboard app.
4. **Fix Legacy Server Test Regressions**: In `tests/e2e/test_tier1_feature.py`, revert `/api/trades` to `/trades` and `/ws` to `/ws/updates` (adding a timeout parameter to websocket connection) to restore compatibility with the legacy server running on port 8000.
5. **Fix Mock Server Lock Contention & Add Endpoints**: In `tests/e2e/mocks/mock_server.py`:
   - Decouple lock during socket I/O by adding a fine-grained `self.clients_lock` on `MockWebSocketServer` and copying the clients list to broadcast messages outside of the lock.
   - Add routes for Interactive Brokers client portal HTTP endpoints (`/iserver/accounts`, `/portfolio/{accountId}/meta`, `/portfolio/{accountId}/positions`, `/iserver/account/{accountId}/orders`, `/iserver/account/{accountId}/order/{orderId}`).
   - Add supports for reasoning models like Gemini Deep Think and OpenAI o3-mini returning structured pre-market research JSON.
6. **Rewrite `tests/e2e/test_r1_r5_e2e.py`**:
   - **Delete all local stub classes and functions** (like `IBExecutor`, `MockCLISetupWizard`, `MockGUISetupWizard`, `run_morning_research`, etc.).
   - **Delete all dynamic route decorations** on `dashboard_fastapi_app`.
   - Write genuine E2E test cases targeting the expected production modules (importing classes/functions from `execution.order_manager`, `engine.llm_brain`, `sentiment.finbert_client`, `politician.copy_mode`).
   - Use dynamic imports (`try-except`) and `pytest.mark.skipif` to check if unimplemented modules or FastAPI endpoints exist. Skip them cleanly if not found so the test suite passes 100% right now, while remaining fully prepared to execute once implemented.
7. **Run `pytest tests/e2e`** and verify that all E2E tests pass 100% without hanging.
8. Write a detailed handoff report in `/workspaces/ai-trading-bot/.agents/worker_s2_fix/handoff.md`.

MANDATORY INTEGRITY WARNING: DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work.
