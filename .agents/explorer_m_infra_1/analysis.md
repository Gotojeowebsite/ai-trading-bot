# E2E Test Infrastructure & Runner Design Strategy

This document outlines the architectural design and implementation strategy for the End-to-End (E2E) testing framework of the AI Trading Bot. It addresses mock server requirements, test runner configurations, SQLite isolated database structures, and skeleton stubs for the core contract functions.

---

## 1. E2E Test Directory Structure Design

To support systematic and deterministic testing without external dependencies, we use the following directory layout inside `tests/e2e/`:

```text
tests/
└── e2e/
    ├── __init__.py
    ├── conftest.py             # Shared pytest fixtures, mock server management, DB setup
    ├── mocks/                  # Custom HTTP/WS simulators
    │   ├── __init__.py
    │   ├── alpaca_mock.py      # Alpaca REST API & WebSockets server simulator
    │   ├── llm_mock.py         # OpenAI (GPT-4o) and Google (Gemini) API simulator
    │   └── feeds_mock.py       # news, FinBERT scoring API, & congressional disclosures simulator
    ├── test_tier1_feature_coverage.py  # Happy paths for all 6 features (30 test cases)
    ├── test_tier2_boundary_cases.py    # Error handling, rate limits, corrupt data, timeouts (30 cases)
    ├── test_tier3_cross_feature.py      # Combined flows (circuit breaker pauses scanner, etc.) (6 cases)
    └── test_tier4_real_world.py        # Day-in-the-life workloads and outages (5 cases)
```

### Purpose of Directory Components:
- **`conftest.py`**: Configures global environment overrides, spins up mock servers in background threads, and handles SQLite test database schema creation/cleanup.
- **`mocks/`**: Contains Python standard library-based HTTP/WS servers running on local ports to intercept all external client SDK network traffic.
- **Tiers 1-4 Test Files**: Organize E2E testing linearly from unit-level feature checks to complex real-world day-in-the-life workloads.

---

## 2. Mock Server Design & Setup

A crucial architectural constraint is the **Opaque-Box / Subprocess execution model**. Because E2E tests run `main.py` as an external subprocess:
1. Python-level mocks (such as `unittest.mock.patch`) inside the pytest test process will **not** affect the subprocess running `main.py`.
2. All external APIs must be mocked at the **network/HTTP socket layer**.
3. Overrides must be injected using environment variables passed to the subprocess.

### Local Ports Mapping
- **Alpaca REST Mock Server**: `http://127.0.0.1:8001`
- **Alpaca WS Stream Mock Server**: `ws://127.0.0.1:8002`
- **LLM APIs (OpenAI/Gemini) Mock Server**: `http://127.0.0.1:8003`
- **News / Congress Disclosures Mock Server**: `http://127.0.0.1:8004`

### Mock Implementation Highlights:
1. **Alpaca REST & WebSocket Simulation**: Uses a `ThreadingHTTPServer` to mimic trade placements, account status, and portfolio query endpoints. The WebSocket server is built using raw python socket frames (saving dependency weight) to accept handshakes and broadcast mock trade updates.
2. **LLM Simulation**: Simulates the OpenAI `/v1/chat/completions` API structure returning structured JSON decisions, and the Gemini `/v1beta/models/gemini-2.0-flash:generateContent` endpoint returning screening scores.
3. **Feed Data Simulation**: Serves static/dynamic JSON files mimicking Congressional Stock Watcher feeds and mock FinBERT NLP sentiment classification arrays.

These simulators have been written to `proposed_tests_e2e_mocks_alpaca_mock.py`, `proposed_tests_e2e_mocks_llm_mock.py`, and `proposed_tests_e2e_mocks_feeds_mock.py` respectively inside the agent working directory.

---

## 3. Core Contract Stubs and `main.py` Design

To ensure the test runner can run without import errors and successfully verify CLI behavior, we have designed the core files as stubs with functional logic.

### 3.1 `main.py` Orchestrator
Processes three execution modes:
- `--mode scan`: Initializes an isolated SQLite database, creates a dummy price history, computes technical indicators, and saves values to the `scanned_tickers` table.
- `--mode trade`: Runs a sequential trading loop fetching cached signals, evaluating sentiment, checking political trades, screening via Tier 1 LLM, making decisions via Tier 2 LLM, and dispatching orders via the execution module.
- `--mode dashboard`: Runs a `FastAPI` instance with WebSocket support (`/ws/updates`) and REST API endpoints (`/api/portfolio`, `/api/trades`, `/api/signals`) for the dashboard UI.

### 3.2 Core Contract Implementations
- **`automation/indicators.py`**: Computes `VWAP`, `RSI`, `MACD`, `Bollinger Bands`, `EMA`, and `RVOL` using pure pandas and numpy operations. It handles low volume and edge data without NaN propagation.
- **`sentiment/finbert_client.py`**: Interacts with local database cache (2-hour TTL) and falls back to news fetches and FinBERT endpoint API queries, clipping values strictly to `[-1.0, 1.0]`.
- **`politician/copy_mode.py`**: Ingests Capitol stock trade transaction logs and performs linear-exponential decay scoring based on trade sizes and recency (limited to 180-day lookback).
- **`engine/decision_engine.py`**: Executes structured HTTP requests to local OpenAI/Gemini endpoints, checks JSON schemas, and applies boundary constraints to stop-loss/take-profit values.
- **`execution/order_manager.py`**: Dispatches Alpaca bracket order payloads and updates local trade logs under the `trade_logs` SQLite table.

---

## 4. Implementation Strategy

To successfully bring this infrastructure to a 100% pass rate:
1. **Copy Proposed Files**: Move the files from `/home/mint/Desktop/ai-trading-bot/.agents/explorer_m_infra_1/proposed_...` into their target project directories:
   - `main.py` -> `main.py`
   - `proposed_automation_indicators.py` -> `automation/indicators.py`
   - `proposed_sentiment_finbert_client.py` -> `sentiment/finbert_client.py`
   - `proposed_politician_copy_mode.py` -> `politician/copy_mode.py`
   - `proposed_engine_decision_engine.py` -> `engine/decision_engine.py`
   - `proposed_execution_order_manager.py` -> `execution/order_manager.py`
   - `proposed_tests_e2e_conftest.py` -> `tests/e2e/conftest.py`
   - `proposed_tests_e2e_mocks_alpaca_mock.py` -> `tests/e2e/mocks/alpaca_mock.py`
   - `proposed_tests_e2e_mocks_llm_mock.py` -> `tests/e2e/mocks/llm_mock.py`
   - `proposed_tests_e2e_mocks_feeds_mock.py` -> `tests/e2e/mocks/feeds_mock.py`
   - `proposed_tests_e2e_test_tier1_feature_coverage.py` -> `tests/e2e/test_tier1_feature_coverage.py`
2. **Add Dependencies**: Ensure that standard dependencies are installed:
   - `pytest`
   - `fastapi`
   - `uvicorn`
   - `pandas`
   - `numpy`
   - `requests`
3. **Execute Test Runner**: Execute `pytest tests/e2e/` from the root of the project.
4. **Iterative Hardening**: Implement the specific Tier 1, Tier 2, Tier 3, and Tier 4 E2E cases in their respective test files using the provided mock server endpoints.
