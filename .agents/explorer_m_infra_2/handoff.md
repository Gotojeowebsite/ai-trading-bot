# Handoff Report — E2E Test Infrastructure Design

## 1. Observation
The following source requirements and constraints were analyzed:
* **PROJECT.md Interface Contracts**:
  * Line 37-38: `automation/indicators.py` exposing `def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame`
  * Line 40-41: `sentiment/finbert_client.py` exposing `def get_sentiment(ticker: str) -> float`
  * Line 43-44: `politician/copy_mode.py` exposing `def get_politician_signals(ticker: str) -> dict`
  * Line 46-49: `engine/decision_engine.py` exposing `def screen_ticker(ticker: str, data: dict) -> float` and `def make_decision(ticker: str, data: dict) -> dict`
  * Line 50-52: `execution/order_manager.py` exposing `def execute_bracket_order(ticker: str, side: str, qty: int, take_profit: float, stop_loss: float) -> str` and `def close_all_positions() -> None`
* **SCOPE.md Requirements**:
  * Line 5-6: "Opaque-box / requirement-driven approach: Tests run the bot's CLI or API entry points as external processes or clients..."
  * Line 7-10: "Mocks and Simulators: Mock Alpaca API server (mocking REST order placement and WS trade events). Mock LLM responses (simulating Tier 1 screening and Tier 2 JSON decisions). Mock News and Politician trade feeds. Offline database configuration for test isolation."
  * Line 21-30: CLI entry points (`main.py --mode scan`, `--mode trade`, `--mode dashboard`) and dashboard endpoints.
* **TEST_INFRA.md Requirements**:
  * Line 18-28: Specifies the pytest configuration, directory layout (`tests/e2e/conftest.py`, `tests/e2e/mocks/`), and testing SQLite database `test_trading.db`.

---

## 2. Logic Chain
1. **Opaque-box Testing & Subprocesses**: Because the E2E tests run the bot's entry points (`main.py`) as external processes (via subprocesses as specified in `SCOPE.md` line 5), standard Python in-process mocking libraries (like `unittest.mock.patch` or `responses`) cannot intercept or modify network calls made inside these spawned processes.
2. **Local Mock Server Requirement**: Therefore, the test infrastructure must run a real, local HTTP and TCP/WebSocket server on `localhost` during tests to intercept all outgoing API requests from the subprocesses (supporting `SCOPE.md` lines 7-10).
3. **Environment Configurable Base URLs**: To redirect the client SDKs (OpenAI, Gemini, Alpaca, yfinance) to this local mock server, the application's configuration must read base URL overrides from environment variables (e.g., `ALPACA_API_BASE_URL`, `OPENAI_API_BASE`).
4. **Dynamic Testing Capability**: To simulate network failures, timeouts, and HTTP 429 rate limit exceptions (as required by Tier 2 boundary cases in `TEST_INFRA.md`), the mock server must support a control endpoint (e.g., `/mock_control`) allowing tests to dynamically update mock response states.
5. **No External Dependencies**: Using standard python modules (`http.server` and `socket`) ensures the test infrastructure remains lightweight, compliant with the offline constraint, and runs with zero external package dependencies.

---

## 3. Caveats
* **WebSocket Handshake Protocol**: The custom WebSocket simulator in `mock_server.py` uses basic TCP socket programming to complete the WebSocket RFC 6455 handshake. While sufficient for simulating connection drops and streaming events, it does not support full WebSocket control frames (like Ping/Pong) out of the box, which should be added if the real client libraries require them.
* **Database Isolation**: The SQLite file path is overridden to `test_trading.db` via environment variables. The codebase must correctly fetch the DB path using `os.environ.get("DATABASE_PATH", "trading.db")` to respect this isolation.

---

## 4. Conclusion
We have designed a complete E2E testing framework, directory structure, mock servers, and modular stubs in `analysis.md`. The design fulfills the offline, opaque-box, and boundary condition testing requirements. The implementation strategy is detailed enough to serve as a drop-in reference for the implementer agent.

---

## 5. Verification Method
1. **Artifact Verification**:
   * Inspect `/home/mint/Desktop/ai-trading-bot/.agents/explorer_m_infra_2/analysis.md` to review the full code designs for `conftest.py`, `mocks/mock_server.py`, and the stubs for `main.py` and other modules.
2. **Execution Verification**:
   * Once the files are written to the workspace by the implementer, run the test command:
     ```bash
     pytest tests/e2e/
     ```
   * Invalidation Conditions: If any network requests leak to external endpoints (e.g., `api.alpaca.markets`, `api.openai.com`) or if unit-testing mocks fail to intercept subprocess calls, the verification fails.
