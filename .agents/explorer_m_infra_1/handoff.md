# Handoff Report - E2E Test Infra Analysis

This handoff report is prepared by M_INFRA Explorer 1 for the E2E Testing Track Orchestrator.

## 1. Observation
I directly observed the following files and workspace state:
- Workspace files: `LICENSE` and `README.md` are the only pre-existing files in the repository.
- `PROJECT.md` interface contract specifications:
  - `def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame` in `automation/indicators.py`
  - `def get_sentiment(ticker: str) -> float` in `sentiment/finbert_client.py`
  - `def get_politician_signals(ticker: str) -> dict` in `politician/copy_mode.py`
  - `def screen_ticker(ticker: str, data: dict) -> float` and `def make_decision(ticker: str, data: dict) -> dict` in `engine/decision_engine.py`
  - `def execute_bracket_order(ticker: str, side: str, qty: int, take_profit: float, stop_loss: float) -> str` and `def close_all_positions() -> None` in `execution/order_manager.py`
- `SCOPE.md` specifies the opaque-box testing model:
  - "Opaque-box / requirement-driven approach: Tests run the bot's CLI or API entry points as external processes or clients..."
- `TEST_INFRA.md` details the test layout:
  - `tests/e2e/conftest.py`
  - `tests/e2e/mocks/` (Alpaca, LLM servers)
  - `test_tier1_feature_coverage.py` etc.

## 2. Logic Chain
- **Step 1 (Subprocess constraints)**: Since `SCOPE.md` requires running CLI/API endpoints as external processes, any standard in-process patching via `unittest.mock.patch` inside the pytest environment will have no effect on the subprocess.
- **Step 2 (Network-level mocking)**: To intercept network calls made by subprocesses, we must implement socket-level HTTP/WebSocket mock servers running on local ports (`8001`, `8002`, `8003`, `8004`).
- **Step 3 (Environment overrides)**: The subprocesses must be redirected to these local servers by injecting environment overrides (e.g. `APCA_API_BASE_URL=http://127.0.0.1:8001`) during the test run.
- **Step 4 (Stubs for validation)**: To verify that the test runner can run without error, we must supply minimal functional stubs for all core contract functions that consume the mocked API endpoints, and a `main.py` CLI parser.

## 3. Caveats
- **Dependencies**: The stubs and tests assume the presence of `pandas`, `requests`, `fastapi`, `uvicorn`, and `pytest`. These must be installed in the environment for tests to pass.
- **WebSocket Protocol**: The mock Alpaca WebSocket server implements a minimal RFC 6455 handshake and framing structure. This works with standard clients but might need adjustment if using specific third-party client wrapper libraries.
- **yfinance Mocking**: Since `yfinance` has hardcoded URL hosts, we recommend using python level patching in `main.py` when `os.getenv("TESTING") == "true"` is set, bypassing the external call and returning a pre-configured pandas DataFrame.

## 4. Conclusion
The design of the E2E Test Infra is complete. I have successfully written proposed file designs and implementations in my working directory `/home/mint/Desktop/ai-trading-bot/.agents/explorer_m_infra_1/`:
- `proposed_tests_e2e_conftest.py` (Pytest environment overrides and mock server lifecycle fixtures)
- `proposed_tests_e2e_mocks_alpaca_mock.py` (REST and WebSocket simulator)
- `proposed_tests_e2e_mocks_llm_mock.py` (OpenAI and Gemini API simulator)
- `proposed_tests_e2e_mocks_feeds_mock.py` (News sentiment and Congress stock transactions simulator)
- `proposed_main.py` (CLI orchestrator and dashboard FastAPI server stub)
- `proposed_automation_indicators.py` (VWAP, RSI, MACD, Bollinger Bands, EMA, RVOL stub)
- `proposed_sentiment_finbert_client.py` (Sentiment analysis with DB cache stub)
- `proposed_politician_copy_mode.py` (Congress disclosure scraper/scoring stub)
- `proposed_engine_decision_engine.py` (Tier 1/2 LLM engine logic stub)
- `proposed_execution_order_manager.py` (Bracket order manager stub)
- `proposed_tests_e2e_test_tier1_feature_coverage.py` (Happy-path tests to verify runner)

## 5. Verification Method
To verify the E2E Test Infra:
1. Copy the proposed files to their final project destinations:
   ```bash
   mkdir -p automation sentiment politician engine execution tests/e2e/mocks
   cp .agents/explorer_m_infra_1/proposed_main.py main.py
   cp .agents/explorer_m_infra_1/proposed_automation_indicators.py automation/indicators.py
   cp .agents/explorer_m_infra_1/proposed_sentiment_finbert_client.py sentiment/finbert_client.py
   cp .agents/explorer_m_infra_1/proposed_politician_copy_mode.py politician/copy_mode.py
   cp .agents/explorer_m_infra_1/proposed_engine_decision_engine.py engine/decision_engine.py
   cp .agents/explorer_m_infra_1/proposed_execution_order_manager.py execution/order_manager.py
   cp .agents/explorer_m_infra_1/proposed_tests_e2e_conftest.py tests/e2e/conftest.py
   cp .agents/explorer_m_infra_1/proposed_tests_e2e_mocks_alpaca_mock.py tests/e2e/mocks/alpaca_mock.py
   cp .agents/explorer_m_infra_1/proposed_tests_e2e_mocks_llm_mock.py tests/e2e/mocks/llm_mock.py
   cp .agents/explorer_m_infra_1/proposed_tests_e2e_mocks_feeds_mock.py tests/e2e/mocks/feeds_mock.py
   cp .agents/explorer_m_infra_1/proposed_tests_e2e_test_tier1_feature_coverage.py tests/e2e/test_tier1_feature_coverage.py
   ```
2. Run the test command:
   ```bash
   pytest tests/e2e/
   ```
3. Invalidation Conditions: Tests will fail if target ports (8001-8004) are occupied by other local services, or if the `FastAPI` / `requests` / `pandas` packages are missing from the execution environment.
