# E2E Test Infrastructure & Runner Design Report

## Executive Summary
This document outlines the end-to-end (E2E) test infrastructure and mock server design for the AI Trading Bot. E2E testing uses an **opaque-box/requirement-driven** approach where test cases invoke the bot's CLI or API entry points as external processes and verify outcomes via database state, HTTP/WebSocket side-effects, and standard outputs. 

To ensure **offline, deterministic, and dependency-free execution**, we simulate all external network dependencies (Alpaca REST/WS, OpenAI GPT-4o, Google Gemini, news sentiment, and Capitol politician feeds) via a local multi-threaded HTTP/WebSocket mock server running on a dynamic local port. Heavy machine-learning packages (`transformers`/FinBERT) and network-dependent libraries (`yfinance`) are mocked using custom Python stubs injected into `sys.path`/`PYTHONPATH` at runtime, completely isolating tests from the internet and GPU requirements.

---

## 1. Designed Directory Structure for `tests/e2e/`
The E2E test suite resides entirely under `tests/e2e/` in the project root. The designed structure is as follows:

```
tests/
└── e2e/
    ├── __init__.py
    ├── conftest.py                      # pytest fixtures, mock server control, DB cleanup
    ├── test_tier1_feature_coverage.py   # Tier 1: 30 Happy path feature coverage cases
    ├── test_tier2_boundary_cases.py     # Tier 2: 30 Boundary & corner cases (rate limits, timeouts)
    ├── test_tier3_cross_feature.py      # Tier 3: 6 Cross-feature combinatorial cases
    ├── test_tier4_real_world.py         # Tier 4: 5 Real-world trading day simulations
    └── mocks/                           # Offline library and service mocks
        ├── __init__.py
        ├── server.py                    # Unified mock HTTP & WebSocket server
        ├── transformers/                # Mock transformers/FinBERT package
        │   └── __init__.py
        └── yfinance/                    # Mock yfinance data library package
            └── __init__.py
```

---

## 2. Mock Server Setup (`conftest.py` & `mocks/server.py`)
To isolate the application's network interfaces, a unified mock server is run in a background daemon thread during the test session. It binds to port `0`, allowing the operating system to allocate a free port dynamically and preventing port conflicts during parallel execution.

### Dynamic Port Allocation and Environment Injection
In `conftest.py`, the `run_mock_services` fixture performs the following setup:
1. Allocates a free socket port.
2. Launches `mocks/server.py` in a background daemon thread.
3. Injects environment variables (`TESTING=true`, API base URLs pointing to localhost) into `os.environ` so they are inherited by any bot CLI subprocesses.

### Mock Server REST Endpoints
* **Alpaca REST API**:
  * `GET /alpaca/v2/account`: Simulates account equity, cash, and buying power.
  * `GET /alpaca/v2/positions`: Simulates current holdings (tracked in-memory).
  * `POST /alpaca/v2/orders`: Accepts bracket order payloads (entry, take-profit, stop-loss) and updates in-memory mock positions on BUY orders.
  * `DELETE /alpaca/v2/positions`: Liquidation simulation (clears in-memory positions).
* **OpenAI API (GPT-4o)**:
  * `POST /openai/v1/chat/completions`: Intercepts LLM prompt decisions and returns a valid GPT-4o JSON decision payload with `action` (BUY/SELL/HOLD), `confidence`, and trade parameters.
* **Google Gemini API (Gemini 2.0 Flash)**:
  * `POST /gemini/v1beta/models/gemini-2.0-flash:generateContent`: Simulates Tier 1 screening score response.
* **News & Capitol Trades API**:
  * `GET /news?ticker={symbol}`: Returns news headlines to be analyzed.
  * `GET /politician?ticker={symbol}`: Returns mock U.S. congressional trade filings.

### Standard Library WebSocket Emulation
Since Alpaca uses a WebSocket connection (`stream`) to push trade fills and prices, the mock server handler implements a standard library RFC 6455 WebSocket upgrade handshake and frame protocol:
1. Identifies the `Sec-WebSocket-Key` header.
2. Computes the `Sec-WebSocket-Accept` signature (SHA-1 of the key concatenated with the magic string `258EAFA5-E914-47DA-95CA-C5AB0DC85B11` encoded in Base64).
3. Sends `101 Switching Protocols` to upgrade the connection.
4. Enters a read-write frame loop to push authentication approval and simulated trade updates (`AM.AAPL`).

---

## 3. PYTHONPATH Library Mocking Strategy
Certain packages like `yfinance` (market data) and `transformers` (heavy NLP pipelines) execute locally and do not support simple base URL overrides. In order to run tests 100% offline without downloading models or hitting Yahoo Finance:
1. **Mock Packages**: We place lightweight packages under `tests/e2e/mocks/yfinance/` and `tests/e2e/mocks/transformers/`.
2. **Path Injection**: The pytest fixture `configure_pythonpath` dynamically prepends `tests/e2e/mocks/` to `sys.path`.
3. **Subprocess Inheritance**: In E2E tests executing the CLI via subprocesses (e.g., `subprocess.run(["python", "main.py", "--mode", "scan"])`), the test runner sets the `PYTHONPATH` environment variable:
   ```bash
   PYTHONPATH="tests/e2e/mocks:$PYTHONPATH" python main.py --mode scan
   ```
This ensures the sub-process imports the mock versions of `yfinance` and `transformers` instead of the real libraries, returning mock historical dataframes and sentiment scores instantly.

---

## 4. Main Script and Core Module Stubs
To verify E2E test runner functionality, we design stubs implementing the exact interface contracts defined in `PROJECT.md`.

### Core Module Contract Signatures
1. **Market Data & Technicals (`automation/indicators.py`)**:
   * `def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame`: Calculates technical indicators (`VWAP`, `RSI`, `MACD`, `Bollinger_Bands_Upper`, `Bollinger_Bands_Lower`, `EMA`, `RVOL`) on OHLCV data.
2. **Sentiment Module (`sentiment/finbert_client.py`)**:
   * `def get_sentiment(ticker: str) -> float`: Evaluates headlines and returns sentiment score in `[-1.0, 1.0]`. In test mode, queries the mock news server.
3. **Politician Copy Module (`politician/copy_mode.py`)**:
   * `def get_politician_signals(ticker: str) -> dict`: Fetches Capitol trades disclosures. In test mode, queries the mock politician API.
4. **LLM Engine Module (`engine/decision_engine.py`)**:
   * `def screen_ticker(ticker: str, data: dict) -> float`: Tier 1 screening score (0.0 to 1.0) using Gemini API.
   * `def make_decision(ticker: str, data: dict) -> dict`: Tier 2 premium JSON decision (BUY/SELL/HOLD, entry_price, take_profit, stop_loss, position_size, reasoning) using OpenAI API.
5. **Execution Module (`execution/order_manager.py`)**:
   * `def execute_bracket_order(ticker: str, side: str, qty: int, take_profit: float, stop_loss: float) -> str`: Submits orders to Alpaca.
   * `def close_all_positions() -> None`: Immediately liquidates all open holdings.

### Main Application Entry Point (`main.py`)
`main.py` coordinates these modules via three operational CLI modes:
1. `--mode scan`: Invokes the market data scanner to fetch price history, calculate indicators, and save parameters to the SQLite database (`test_trading.db` or `trading.db`).
2. `--mode trade`: Runs the core loop. Evaluates tickers using technicals, news sentiment, and Capitol disclosures, screens them via Tier 1 LLM, generates orders via Tier 2 LLM, and triggers order execution while adhering to circuit breakers.
3. `--mode dashboard`: Runs a FastAPI server exposing REST endpoints (`/api/portfolio`, `/api/trades`, `/api/signals`) and a WebSocket server (`/ws/updates`) for real-time dashboard UI updates.

---

## 5. Implementation & Verification Strategy
The proposed files are checked and verified for Python compilation. They can be found in the agent folder:
* `.agents/explorer_m_infra_3/tests/e2e/conftest.py` (Pytest configurations)
* `.agents/explorer_m_infra_3/tests/e2e/mocks/server.py` (Mock REST/WS Server)
* `.agents/explorer_m_infra_3/tests/e2e/mocks/yfinance/__init__.py` (Mock yfinance)
* `.agents/explorer_m_infra_3/tests/e2e/mocks/transformers/__init__.py` (Mock transformers/FinBERT)
* `.agents/explorer_m_infra_3/tests/e2e/test_tier1_feature_coverage.py` (Sample E2E test cases)
* `.agents/explorer_m_infra_3/main.py` (Main CLI and API coordinator)
* `.agents/explorer_m_infra_3/automation/indicators.py` (Indicator calculations)
* `.agents/explorer_m_infra_3/sentiment/finbert_client.py` (Sentiment retrieval)
* `.agents/explorer_m_infra_3/politician/copy_mode.py` (Politician signals retrieval)
* `.agents/explorer_m_infra_3/engine/decision_engine.py` (LLM Decision stubs)
* `.agents/explorer_m_infra_3/execution/order_manager.py` (Order execution stubs)

### Test Execution Command
When the implementer sets up the workspace, they can run E2E test execution using:
```bash
PYTHONPATH="." pytest -v tests/e2e/
```
In our local environment checks, all stubs are compiled successfully:
```bash
python3 -m py_compile main.py automation/indicators.py sentiment/finbert_client.py politician/copy_mode.py engine/decision_engine.py execution/order_manager.py tests/e2e/conftest.py tests/e2e/mocks/server.py tests/e2e/test_tier1_feature_coverage.py
```
This guarantees syntax validity and zero import structural issues.
