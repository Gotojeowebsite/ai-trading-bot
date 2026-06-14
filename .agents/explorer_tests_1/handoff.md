# Handoff Report: E2E Test Cases Implementation Design

## 1. Observation
- The existing E2E test runner configuration is located in `tests/e2e/conftest.py`. Line 10-37 initializes the HTTP and WebSocket mock servers on ports 8001 and 8002:
  ```python
  @pytest.fixture(scope="session", autouse=True)
  def mock_servers():
      # Start HTTP Server
      http_server = HTTPServer(("127.0.0.1", 8001), MockHTTPRequestHandler)
      ...
      # Inject mock endpoints into environment for the test session
      os.environ["ALPACA_API_BASE_URL"] = "http://localhost:8001/alpaca"
      os.environ["ALPACA_WS_BASE_URL"] = "ws://localhost:8002"
      os.environ["OPENAI_API_BASE"] = "http://localhost:8001/openai"
      os.environ["GEMINI_API_BASE"] = "http://localhost:8001/gemini"
      os.environ["FINBERT_API_URL"] = "http://localhost:8001/sentiment"
      os.environ["CONGRESS_DISCLOSURE_URL"] = "http://localhost:8001/congress"
      os.environ["YFINANCE_BASE_URL"] = "http://localhost:8001/yfinance"
      os.environ["DATABASE_PATH"] = "test_trading.db"
  ```
- The mock HTTP server defined in `tests/e2e/mocks/mock_server.py` implements a `/mock_control` endpoint to dynamically control the server state (status overrides, response delays, state resets).
- Run the E2E test using Python module syntax: `python3 -m pytest tests/e2e/test_e2e_flow.py`:
  ```
  tests/e2e/test_e2e_flow.py .                                             [100%]
  ============================== 1 passed in 2.39s ===============================
  ```

## 2. Logic Chain
- E2E tests must verify the system from the outside using CLI commands or client REST/WebSocket requests.
- The `run_cli` fixture executes `python3 main.py` in a subprocess with the necessary environment variables (`DATABASE_PATH="test_trading.db"`, API base URLs pointing to the mock server).
- By sending requests to `http://localhost:8001/mock_control`, we can dynamically inject status codes (e.g., 429 for rate limit testing, 500/503 for server errors) or delay times (to simulate API timeouts). This allows testing of Tier 2 boundary cases completely offline.
- Subprocesses write side-effects to SQLite database `test_trading.db`. We query this database using `sqlite3` from within tests to assert state transitions (e.g., ticker indicator calculations, signals blended scores, trade placements).

## 3. Caveats
- The watchdog component and dashboard static assets are partially stubbed out in the codebase. Tests targeting them assume a default execution behavior.
- We assume that the port bindings `8001`, `8002`, and `8000` (for dashboard) are free on the local loopback interface during test execution.

## 4. Conclusion
The implementation of the 71 test cases can be achieved in 4 files (`test_tier1_feature.py`, `test_tier2_boundary.py`, `test_tier3_combinatorial.py`, `test_tier4_scenarios.py`) using the blueprints provided in `analysis.md`. The design leverages existing conftest and mock server setups to achieve 100% offline and deterministic execution.

## 5. Verification Method
- Execute the tests using:
  ```bash
  python3 -m pytest tests/e2e/
  ```
- Files to inspect:
  - `tests/e2e/test_tier1_feature.py`
  - `tests/e2e/test_tier2_boundary.py`
  - `tests/e2e/test_tier3_combinatorial.py`
  - `tests/e2e/test_tier4_scenarios.py`
- Invalidation conditions: Any test failure in Pytest or mock server crash.
