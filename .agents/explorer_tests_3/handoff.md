# E2E Test Suite Implementation Design Handoff Report

## 1. Observation

- **Mock Server & Port Configuration**: Direct observation of `tests/e2e/conftest.py` lines 14-30:
  ```python
  http_server = HTTPServer(("127.0.0.1", 8001), MockHTTPRequestHandler)
  ws_server = MockWebSocketServer("127.0.0.1", 8002)
  # Inject mock endpoints into environment for the test session
  os.environ["ALPACA_API_BASE_URL"] = "http://localhost:8001/alpaca"
  os.environ["ALPACA_WS_BASE_URL"] = "ws://localhost:8002"
  ...
  ```
- **CLI Commands**: Observed that `main.py` accepts `--mode` flag (choices: `scan`, `trade`, `dashboard`). In `tests/e2e/conftest.py` line 92, the `run_cli` fixture runs `main.py` using `python3 main.py` in a subprocess.
- **Database Schema**: Observed isolated SQLite database initialization in `tests/e2e/conftest.py` lines 51-69 containing:
  - `scanned_tickers` table
  - `trades` table
  - `signals` table
- **Mock State Control**: In `tests/e2e/mocks/mock_server.py` line 10, the class `MockServerState` manages orders, positions, and accounts in-process, allowing direct manipulation and observation by importing `state`.
- **Pre-Market Cutoff**: Checked `automation/scanner.py` line 159:
  ```python
  cutoff = now_est.replace(hour=9, minute=30, second=0, microsecond=0)
  if now_est >= cutoff:
      print(f"Current EST time {now_est.strftime('%H:%M:%S')} is after the 9:30 AM cutoff...")
  ```

---

## 2. Logic Chain

1. **Test process integration**: Because the mock server is started in a background thread of the pytest process (Observation 1), we can import `from tests.e2e.mocks.mock_server import state` and directly inspect or update mock status/orders in pytest tests, providing a robust mock-control mechanism.
2. **Requirements mapping**: The 71 test cases specified in `TEST_INFRA.md` test different layers of the bot (Scanner, Sentiment, Politician copying, LLM, Execution, Dashboard).
3. **Missing application features**: By comparing `TEST_INFRA.md` requirements with the actual source code (e.g., `sentiment/finbert_client.py` and `execution/order_manager.py`), we identified that caching, circuit breakers, and watchdog are currently not implemented or are placeholders. Therefore, the E2E tests must be designed such that they define the desired interface, and recommendations are provided to the implementer on how to make them pass.
4. **Subprocess isolation**: Using the `run_cli` fixture (Observation 2) allows us to run the bot end-to-end as an opaque box, validating DB and mock API side-effects.

---

## 3. Caveats

- **Websocket testing**: Real-time websocket updates in `test_dash_websocket_updates` and `test_exec_alpaca_disconnected_ws` assume that a python WebSocket client library (like `websocket-client`) is installed or uses the built-in python socket library.
- **Watchdog logic**: Assumes the watchdog is run as a separate Python thread or process monitoring the execution script.

---

## 4. Conclusion

The 71 E2E tests are structured across four files corresponding to the four tiers. The blueprints for these files are written to `analysis.md` in the agent folder, including:
- `tests/e2e/test_tier1_feature.py` (30 tests)
- `tests/e2e/test_tier2_boundary.py` (30 tests)
- `tests/e2e/test_tier3_combinatorial.py` (6 tests)
- `tests/e2e/test_tier4_scenarios.py` (5 tests)

An architectural plan was formulated to implement missing requirements (caching, circuit breakers, watchdog, JSON schema fallback) so that the test suite passes with 100% success.

---

## 5. Verification Method

To independently verify the test suite design and run:
1. View the blueprints and analysis in `/home/mint/Desktop/ai-trading-bot/.agents/explorer_tests_3/analysis.md`.
2. Inspect the existing test runner configuration in `/home/mint/Desktop/ai-trading-bot/tests/e2e/conftest.py`.
3. Run the existing E2E flow to confirm the pytest mock infrastructure works:
   `python3 -m pytest tests/e2e/test_e2e_flow.py`
