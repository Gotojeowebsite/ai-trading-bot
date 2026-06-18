# Handoff Report — worker_m1_test_run

## 1. Observation
We ran the pytest suite on the current workspace status.
- **Command executed**: `PATH="/home/umanzor/ai-trading-bot/.venv/bin:$PATH" .venv/bin/pytest tests/`
- **Result**: `84 passed, 18 failed, 10 skipped, 9 warnings in 95.50s (0:01:35)`

Below are the details of the failures and the verbatim traceback segments:

### A. Dashboard portfolio key mismatch
- **File**: `tests/e2e/test_r1_r5_e2e.py`
- **Test**: `test_r3_dashboard_existing_portfolio_endpoint`
- **Error**:
  ```
  assert 'account' in {'cash': '100000.0', 'equity': '100000.0', 'buying_power': '400000.0'}
  ```
  The test expects the key `"account"` to be present in the returned JSON dict, which only contains `"cash"`, `"equity"`, and `"buying_power"`.

### B. Fallback news sentiment scoring mismatch
- **File**: `tests/e2e/test_tier1_feature.py`
- **Test**: `test_sentiment_happy_path`
- **Error**:
  ```
  assert score == pytest.approx(0.85)
  E       assert 0.0 == 0.85 ± 8.5e-07
  ```
  Since the environment is restricted to offline mode (`CODE_ONLY`), installing the heavyweight `torch` and `transformers` packages from PyPI timed out/was unreachable. The application gracefully degrades to keyword-based scoring (`_score_with_keywords`), which evaluates to `0.0` instead of the expected `0.85` from the FinBERT pipeline.

### C. Politician Signal Time/Recency Decay
- **Files**: `tests/e2e/test_r1_r5_e2e.py`, `tests/e2e/test_tier1_feature.py`, `tests/e2e/test_tier2_boundary.py`
- **Tests**: `test_r5_production_politician_signals`, `test_politician_happy_path`, `test_politician_scoring_weight`, `test_politician_corrupt_data`, `test_politician_future_disclosed_date`, `test_politician_duplicate_trades`, `test_politician_missing_fields`, `test_politician_historic_trades`
- **Error**:
  ```
  assert res["signal_score"] == 0.95
  E       assert 0.286 == 0.95
  ```
  The politician copy mode calculates scores using a recency decay factor: `recency_factor = max(0.0, 1.0 - (days_ago / recency_window))`. Since the tests use fixed trade dates (e.g. `2026-06-10`) and today is `2026-06-18`, the calculated score is decayed to `0.286` instead of the static `0.95` expected by the test cases.

### D. WebSocket 404 Route mismatch
- **Files**: `tests/e2e/test_tier1_feature.py`, `tests/e2e/test_tier2_boundary.py`
- **Tests**: `test_dash_websocket_updates`, `test_dash_websocket_flood`, `test_dash_empty_db_state`, `test_dash_concurrent_connections`
- **Error**:
  ```
  websocket._exceptions.WebSocketBadStatusException: Handshake status 404 Not Found -+-+- {'server': 'BaseHTTP/0.6 Python/3.12.3', 'date': 'Thu, 18 Jun 2026 15:15:46 GMT', ...}
  ```
  The test cases connect to `ws://localhost:8000/ws` (the production dashboard websocket path), but the test fixture `dashboard_server` starts the legacy server via `main.py --mode dashboard`, which only supports `/ws/updates` and returns a 404 Not Found for `/ws`.

### E. Scanner DST transition mixed timezone Index
- **File**: `tests/unit/test_stress.py`
- **Test**: `test_scanner_dst_transitions`
- **Error**:
  ```
  ERROR    automation.scanner:scanner.py:126 Error scanning AAPL: 'Index' object has no attribute 'tzinfo'
  ...
  KeyError: 'previous_close'
  ```
  Under newer pandas versions, parsing mixed standard/daylight offsets using `pd.to_datetime` returns a generic index of objects instead of a `DatetimeIndex`. The scanner's timezone check `df.index.tzinfo` raises `'Index' object has no attribute 'tzinfo'`.

### F. Outage recovery ConnectionError not raised
- **File**: `tests/e2e/test_tier4_scenarios.py`
- **Test**: `test_scenario_extended_api_outage_recovery`
- **Error**:
  ```
  Failed: DID NOT RAISE ConnectionError
  ```
  The test expects a `ConnectionError` when the Alpaca API is down, but the order manager logs `Order failed: 503` and returns gracefully instead of propagating the error to the caller.

---

## 2. Logic Chain
1. **Dependency management**: We observed that installing `torch` and `transformers` failed due to network unreachable timeouts under the `CODE_ONLY` constraint (Observation). However, the codebase handles missing `transformers` gracefully by falling back to keyword scoring. We successfully installed all other requirements + `pytest` (Observation).
2. **Subprocess pathing**: When tests run CLI commands, they call `python3 main.py`. Prepending `.venv/bin` to the `PATH` environment variable ensures that these subprocesses resolve to the virtual environment's python which contains `pandas` and other dependencies.
3. **Pandas versioning**: In pandas 3.0.x, passing mixed timezones to `pd.to_datetime` raises `ValueError: Mixed timezones detected`. We downgraded pandas to `2.3.3` to allow parsing mixed timezones, which resolved this specific exception, but the resulting object Index lacks `.tzinfo`, causing the subsequent scanner attribute error.
4. **Time/date dependency**: The date-based score decay calculations are based on the system date `datetime.now().date()` (Observation). Because the mock trade dates are hardcoded to fixed values (e.g. `2026-06-10`), running the tests on `2026-06-18` results in non-zero decay (`days_ago = 8`), altering the expected score from `0.95` to `0.286`.

---

## 3. Caveats
- No source code was modified during this verification process, adhering strictly to the constraints of this run.
- Heavy dependencies `torch` and `transformers` could not be installed in the offline sandbox environment, which directly caused the news sentiment tests to fall back to keyword scoring and fail.

---

## 4. Conclusion
Out of 112 collected tests, 84 tests pass, 18 fail, and 10 are skipped. The failures are structural mismatches between the E2E mock server implementation, time-dependent recency decay calculations, and environmental restrictions (lack of `transformers` and `torch` in offline mode).

---

## 5. Verification Method
To reproduce the test runs, navigate to the root directory `/home/umanzor/ai-trading-bot` and run:
```bash
PATH="/home/umanzor/ai-trading-bot/.venv/bin:$PATH" .venv/bin/pytest tests/
```
The files to inspect are:
- `tests/e2e/test_tier1_feature.py` and `tests/e2e/test_tier2_boundary.py` (for WebSocket route and sentiment mock mismatches)
- `tests/unit/test_stress.py` (for timezone parsing and scanner attribute error)
- `politician/copy_mode.py` (for recency decay score calculations)
