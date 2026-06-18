# pytest Suite Run and Failure Analysis Report

## 1. Observation
I executed the pytest suite in the workspace `/home/umanzor/ai-trading-bot` from the root of the workspace.
- **Command used**: `PYTHONPATH=. PATH="/home/umanzor/ai-trading-bot/.venv/bin:$PATH" .venv/bin/pytest tests/`
- **Overall Result**: 84 passed, 18 failed, 10 skipped, 10 warnings (112 collected tests in total)
- **Port Conflict Observations**: When running pytest without cleaning ports or when parallel runners are executing, E2E tests raise setup errors:
  `OSError: [Errno 98] Address already in use` at:
  `http_server = HTTPServer(("127.0.0.1", 8001), MockHTTPRequestHandler)` in `tests/e2e/conftest.py:63`

Verbatim failures and details:

### A. Mixed Timezone Index / DST transitions
- **File**: `tests/unit/test_stress.py`
- **Test**: `test_scanner_dst_transitions`
- **Error**:
  ```
  ERROR    automation.scanner:scanner.py:126 Error scanning AAPL: 'Index' object has no attribute 'tzinfo'
  ...
  KeyError: 'previous_close'
  ```
  In `automation/scanner.py` line 71-72:
  ```python
  df.index = pd.to_datetime(df.index, utc=True)
  df_est = df.tz_convert('US/Eastern')
  ```
  Since the test inputs `timestamps_spring` contain mixed offsets (`-05:00` and `-04:00`), `pd.to_datetime` returns a standard `Index` of `object` dtype. Accessing `.tzinfo` or converting timezone on an object Index raises an AttributeError, causing the scanner to log the error and return a dict that does not contain the `previous_close` key.

### B. Politician Signal Recency Decay
- **Files**: `tests/e2e/test_r1_r5_e2e.py`, `tests/e2e/test_tier1_feature.py`, `tests/e2e/test_tier2_boundary.py`
- **Tests**: `test_r5_production_politician_signals`, `test_politician_happy_path`, `test_politician_scoring_weight`, `test_politician_corrupt_data`, `test_politician_future_disclosed_date`, `test_politician_duplicate_trades`, `test_politician_missing_fields`, `test_politician_historic_trades`
- **Error**:
  ```
  assert res["signal_score"] == 0.95
  E       assert 0.286 == 0.95
  ```
  The politician copy mode in `politician/copy_mode.py` uses a recency decay factor:
  `recency_factor = max(0.0, 1.0 - (days_ago / recency_window))`
  The mock trade has a hardcoded transaction date of `2026-06-10`. Because the tests are evaluated relative to `datetime.now().date()` (today is `2026-06-18`), `days_ago` is non-zero (8 days), and the expected score of `0.95` is decayed to `0.286`, failing the assertions.

### C. News Sentiment Fallback Mismatch
- **Files**: `tests/e2e/test_tier1_feature.py`, `tests/e2e/test_tier2_boundary.py`
- **Tests**: `test_sentiment_happy_path` (and other sentiment tests)
- **Error**:
  ```
  assert score == pytest.approx(0.85)
  E       assert 0.0 == 0.85 ± 8.5e-07
  ```
  In offline mode (`CODE_ONLY`), heavy ML libraries `torch` and `transformers` are missing. The news client gracefully falls back to keyword-based scoring (`_score_with_keywords`), which evaluates the mock headlines to `0.0` instead of the expected `0.85` from the FinBERT pipeline.

### D. WebSocket Route Handshake Mismatch
- **Files**: `tests/e2e/test_tier1_feature.py`, `tests/e2e/test_tier2_boundary.py`
- **Tests**: `test_dash_websocket_updates`, `test_dash_websocket_flood`, `test_dash_empty_db_state`, `test_dash_concurrent_connections`
- **Error**:
  ```
  websocket._exceptions.WebSocketBadStatusException: Handshake status 404 Not Found
  ```
  The E2E tests attempt to connect to `ws://localhost:8000/ws` to assert real-time websocket updates. However, the legacy dashboard server started by `main.py --mode dashboard` in the fixture only implements `/ws/updates`, resulting in a `404 Not Found` during the `/ws` handshake.

### E. Dashboard Portfolio Endpoint Mismatch
- **File**: `tests/e2e/test_r1_r5_e2e.py`
- **Test**: `test_r3_dashboard_existing_portfolio_endpoint`
- **Error**:
  ```
  assert 'account' in {'cash': '100000.0', 'equity': '100000.0', 'buying_power': '400000.0'}
  ```
  The test expects the key `"account"` to be in the response dictionary, but due to port conflicts or fallback routes, the raw account dictionary is returned directly.

### F. Outage Recovery ConnectionError Not Propagated
- **File**: `tests/e2e/test_tier4_scenarios.py`
- **Test**: `test_scenario_extended_api_outage_recovery`
- **Error**:
  ```
  Failed: DID NOT RAISE ConnectionError
  ```
  The test expects a `ConnectionError` when Alpaca API returns a 503 (outage). However, the order manager in `execution/order_manager.py` catches exceptions, logs `Order failed: 503`, and returns `None` instead of propagating `ConnectionError`.

---

## 2. Logic Chain
1. **Pandas Index Type**: In pandas, when timestamps have mixed tz-offsets, `pd.to_datetime()` returns a generic index of `object` dtype (Observation A). Calling `.tz_convert()` on a DataFrame with an object Index raises an AttributeError/TypeError (Observation A), which prevents the scanner from completing the scan and returning the `previous_close` key.
2. **Dynamic Decay Calculations**: The recency decay factor uses `datetime.now().date()` to determine how many days have elapsed since the trade date (Observation B). Because the mock trade dates are hardcoded to `2026-06-10`, the days elapsed will change daily, causing the score to decay to `0.286` (on 2026-06-18) and mismatching the static test assertion of `0.95`.
3. **Environment Limitations**: Since the runtime environment is offline, `torch` and `transformers` are not installed. The client falls back to keyword-based scoring which returns `0.0` (Observation C), failing the sentiment tests that expect a static FinBERT score of `0.85`.
4. **WebSocket Route Discrepancy**: The legacy dashboard server runs on port 8000 via `main.py --mode dashboard` (Observation D). The E2E tests attempt to connect to `/ws`, but the legacy server only defines `/ws/updates` or `/ws` handshake is unsupported (Observation D), leading to 404 Handshake failures.
5. **Exception Handling**: The order executor handles Alpaca API responses inside a `try/except` block, logging errors rather than raising/propagating them to callers, meaning `ConnectionError` is never raised when a 503 is returned (Observation F).

---

## 3. Caveats
- No source code or tests were modified during this investigation.
- Port binding conflicts occurred due to parallel/concurrent test runner executions in the environment. E2E tests require ports 8001, 8002, 8000, and 7497 to be free.

---

## 4. Conclusion
Out of 112 collected tests, 84 pass, 18 fail, and 10 are skipped. The failures are due to structural timezone index handling in pandas, dynamic time-dependent recency decay calculations, missing ML packages in the offline environment, incorrect route stubs, and swallowed exception blocks.

---

## 5. Verification Method
To reproduce the test runs, navigate to the root directory `/home/umanzor/ai-trading-bot` and run:
```bash
# Clean ports first
fuser -k 8001/tcp 8002/tcp 7497/tcp 8000/tcp || true

# Run the tests with PYTHONPATH and PATH set correctly
PYTHONPATH=. PATH="/home/umanzor/ai-trading-bot/.venv/bin:$PATH" .venv/bin/pytest tests/
```
The files containing the failing test cases are:
- `tests/unit/test_stress.py` (DST timezone index)
- `tests/e2e/test_r1_r5_e2e.py` (politician signals, portfolio API)
- `tests/e2e/test_tier1_feature.py` (news sentiment fallback, politician happy path, websocket updates)
- `tests/e2e/test_tier2_boundary.py` (politician boundary dates, websocket flood/concurrency)
- `tests/e2e/test_tier4_scenarios.py` (extended outage recovery)
