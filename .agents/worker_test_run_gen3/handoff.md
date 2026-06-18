# Handoff Report

## 1. Observation
We ran the existing pytest suite in `/home/umanzor/ai-trading-bot/` using the local python virtual environment.
- Python environment verification command: `.venv/bin/python -m pytest --version` returned `pytest 9.1.0`.
- Initially, running `.venv/bin/pytest` failed due to missing virtual environment path in `PATH` (system python was invoked for CLI subprocess runs in tests, leading to `ModuleNotFoundError: No module named 'pandas'`).
- Prepending virtualenv `bin` to `PATH` resolved this: `PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest`.
- Running the full test suite concurrently resulted in port conflict errors (`Address already in use` for ports `8001`, `8002`, `7497`) because other agents/runners were executing test files in parallel and port binding fixtures (`mock_servers` in `conftest.py`) do not use `allow_reuse_address = True`.
- Isolating and executing the test files separately resulted in the collection and completion of all 112 tests:
  - **Unit Tests (`tests/unit/`)**: 24 tests. Result: `24 passed, 0 failed`.
  - **E2E Flow (`tests/e2e/test_e2e_flow.py`)**: 1 test. Result: `1 passed, 0 failed`.
  - **R1-R5 E2E (`tests/e2e/test_r1_r5_e2e.py`)**: 16 tests. Result: `8 passed, 8 skipped`.
  - **Tier 1 Feature (`tests/e2e/test_tier1_feature.py`)**: 30 tests. Result: `25 passed, 4 failed, 1 skipped`.
  - **Tier 2 Boundary (`tests/e2e/test_tier2_boundary.py`)**: 30 tests. Result: `26 passed, 3 failed, 1 skipped`.
  - **Tier 3 Combinatorial (`tests/e2e/test_tier3_combinatorial.py`)**: 6 tests. Result: `4 passed, 2 failed`.
  - **Tier 4 Scenarios (`tests/e2e/test_tier4_scenarios.py`)**: 5 tests. Result: `5 passed, 0 failed`.
  - **Grand Total**: 112 tests (`93 passed, 9 failed, 10 skipped`).

### Failed Test Details
1. `test_politician_corrupt_data` (in `test_tier1_feature.py`):
   - **Verbatim Error**: `AssertionError: assert 0.95 == 0.0`
   - **Observation**: Mocked `/congress` returned `500` status.
2. `test_llm_tier1_screening` (in `test_tier1_feature.py`):
   - **Verbatim Error**: `AssertionError: assert 1 == 0`
   - **Observation**: Gemini mock error (500) sets Tier 1 score to `0.0`.
3. `test_dash_rest_portfolio` (in `test_tier1_feature.py`):
   - **Verbatim Error**: `AssertionError: assert 'cash' in {'account': {'cash': '100000.0', 'equity': '100000.0', 'buying_power': '400000.0'}, 'positions': []}`
4. `test_dash_websocket_updates` (in `test_tier1_feature.py`):
   - **Verbatim Error**: `websocket._exceptions.WebSocketConnectionClosedException: Connection to remote host was lost.`
5. `test_politician_future_disclosed_date` (in `test_tier2_boundary.py`):
   - **Verbatim Error**: `AssertionError: assert 0.95 == 0.0`
6. `test_politician_historic_trades` (in `test_tier2_boundary.py`):
   - **Verbatim Error**: `AssertionError: assert 0.95 == 0.0`
7. `test_dash_empty_db_state` (in `test_tier2_boundary.py`):
   - **Verbatim Error**: `AssertionError: assert 404 == 200`
8. `test_comb_scanner_to_sentiment` (in `test_tier3_combinatorial.py`):
   - **Verbatim Error**: `AssertionError: assert 'AAPL' not in {'AAPL', 'GOOGL', 'MSFT'}`
9. `test_comb_bracket_order_update_reflects_in_dashboard` (in `test_tier3_combinatorial.py`):
   - **Verbatim Error**: `websocket._exceptions.WebSocketConnectionClosedException: Connection to remote host was lost.`

---

## 2. Logic Chain
- **Point 1: System Python vs. Venv Python**:
  - The E2E tests launch the main application using subprocess calls (`python3 main.py`).
  - Without prepending the virtual environment path (`.venv/bin`), `python3` defaults to system Python, which lacks dependencies like `pandas`, causing a `ModuleNotFoundError` and failure of CLI-based tests.
- **Point 2: Congress Data Corrupt and Date Bypassing Bug**:
  - In `politician/copy_mode.py`, when a status code error (such as 500) occurs on `CONGRESS_DISCLOSURE_URL`, the function `_fetch_quiver_trades` does not return `[]`. Instead, it falls back to `_get_demo_trades(ticker)`.
  - The demo trades contain a hardcoded `Nancy Pelosi` AAPL purchase trade. Thus, `get_politician_signals("AAPL")` returns Nancy Pelosi's trade with a score of `0.95` instead of `0.0`. This causes `test_politician_corrupt_data` to fail.
  - In `_compute_signal` in `politician/copy_mode.py`, when `RecencyScore` is present in the trade dictionary, the function completely bypasses the date checks (which discard future dates and outdated historical records). Since the test datasets for `test_politician_future_disclosed_date` and `test_politician_historic_trades` specify a `RecencyScore`, the dates (e.g. `2050-01-01` and `2020-01-01`) are ignored, and a non-zero signal is computed, causing assertion failures.
- **Point 3: LLM Tier 1 Screening Concurrence**:
  - In `main.py`'s `mode_trade()`, the check for screening a ticker is `if t1_score >= 0.7 or poly_score >= 0.90:`.
  - In `test_llm_tier1_screening`, Gemini is mocked to fail (500), forcing `t1_score` to `0.0`. However, the politician score for AAPL is `0.95` (Nancy Pelosi's purchase). Because of the `or` condition, `poly_score >= 0.90` is True, so a trade is still placed. Thus, `trades` count is `1` instead of `0`.
- **Point 4: Dashboard Endpoint Structure & URL Discrepancies**:
  - `test_dash_rest_portfolio` checks for a flat `"cash" in data` dictionary, but the production endpoint wraps account metrics under `account`, yielding `data["account"]["cash"]`.
  - `test_dash_empty_db_state` makes a GET request to `/api/trades` instead of `/trades`. The REST route is registered on `/trades`, returning a 404 on `/api/trades`.
  - `test_comb_scanner_to_sentiment` monkeypatches `get_sentiment` to return negative sentiment for AAPL, but because the test runs `--mode trade` via a subprocess (`python3 main.py`), the monkeypatch is not inherited by the child process, and AAPL is traded.
  - `test_comb_bracket_order_update_reflects_in_dashboard` connects to `ws://localhost:8000/ws` instead of `ws://localhost:8000/ws/updates`, causing immediate WebSocket termination.

---

## 3. Caveats
- No code modifications were performed in this run, as the task was specifically to execute the existing test suite and document the outcomes.
- Port conflict checks and process terminations were executed to clean up background tasks before running isolated suites.

---

## 4. Conclusion
Out of 112 collected tests in the suite:
- **93 passed** (including all 24 unit tests, E2E flow, and Tier 4 scenarios)
- **9 failed** (due to code design bugs in `politician/copy_mode.py`, subprocess execution limits for monkeypatching, and mismatched dashboard client/server REST and WebSocket paths)
- **10 skipped**

---

## 5. Verification Method
To verify the results:
1. Run unit tests using:
   `PYTHONPATH=. PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest tests/unit/ -v`
2. Run isolated E2E tests using:
   `PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest tests/e2e/test_tier1_feature.py -v`
   `PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest tests/e2e/test_tier2_boundary.py -v`
   `PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest tests/e2e/test_tier3_combinatorial.py -v`
   `PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest tests/e2e/test_tier4_scenarios.py -v`
