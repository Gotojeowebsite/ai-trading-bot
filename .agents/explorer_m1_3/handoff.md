# Handoff Report — Milestone 1 Investigation & Recommendation
**Explorer Agent 3** — 2026-06-18

This report summarizes findings and technical recommendations to address the 9 failing test cases and the requirements.txt cleanup in Milestone 1.

---

## 1. Observation

During our read-only investigation, we observed the following in the codebase:

### A. Sentiment API Mismatch
- **File**: `/workspaces/ai-trading-bot/sentiment/finbert_client.py` (lines 79-106)
  - `get_sentiment(ticker)` returns a dictionary:
    ```python
    return {"score": score, "headlines": headlines, "source": source}
    ```
- **File**: `/workspaces/ai-trading-bot/tests/e2e/test_tier1_feature.py` (lines 110-132)
  - The tests assert `score == pytest.approx(0.85)` and `-1.0 <= score <= 1.0`, expecting a float return type.
- **File**: `/workspaces/ai-trading-bot/automation/trading_loop.py` (lines 231-233)
  - The trading loop accesses keys:
    ```python
    sentiment_data = get_sentiment(ticker)
    signals["sentiment"] = sentiment_data["score"]
    signals["headlines"] = "; ".join(sentiment_data.get("headlines", [])[:3])
    ```

### B. Politician Client Schema Mismatch
- **File**: `/workspaces/ai-trading-bot/politician/copy_mode.py` (lines 134-164)
  - `get_politician_signals(ticker, config)` returns:
    ```python
    return {
        "composite_score": round(composite, 3),
        "trade_count": len(trade_details),
        "trades": trade_details,
        "direction": "BULLISH" if composite > 0.2 else "BEARISH" if composite < -0.2 else "NEUTRAL",
    }
    ```
- **File**: `/workspaces/ai-trading-bot/tests/e2e/test_tier1_feature.py` (lines 161-164)
  - The tests assert:
    ```python
    data = get_politician_signals("AAPL")
    assert data["ticker"] == "AAPL"
    assert data["signal_score"] == 0.95
    assert data["trade_type"] == "purchase"
    ```
- **File**: `/workspaces/ai-trading-bot/politician/copy_mode.py` (lines 29-46)
  - `_fetch_quiver_trades` hardcodes queries to Quiver Quantitative API and does not respect the environment variable `CONGRESS_DISCLOSURE_URL` injected by the mock server fixture.

### C. Order Manager Demo Fallback
- **File**: `/workspaces/ai-trading-bot/execution/order_manager.py` (lines 30-31)
  - `AlpacaExecutor` checks configuration using:
    ```python
    def _is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))
    ```
- **File**: `/workspaces/ai-trading-bot/tests/e2e/conftest.py` (lines 65-72)
  - In `mock_servers` fixture, `os.environ` overrides are set for APIs, but `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are not populated.

### D. Settings DB Table
- **File**: `/workspaces/ai-trading-bot/automation/trading_loop.py` (lines 61-82)
  - `init_db` initializes tables `trades`, `decisions`, `portfolio_snapshots`, and `signals` but omits the `settings` table.
- **File**: `/workspaces/ai-trading-bot/tests/e2e/conftest.py` (lines 114-118)
  - The `clean_database` fixture creates `settings` but does not seed default settings keys, leading to query failures or empty settings tables.

### E. Monkeypatch Namespace Resolution
- **File**: `/workspaces/ai-trading-bot/tests/e2e/test_tier1_feature.py` (line 147)
  - `test_sentiment_cache` contains:
    ```python
    monkeypatch.setattr("sentiment.finbert_client.get_sentiment", mock_get)
    ```
  - However, line 10 imports `get_sentiment` directly:
    ```python
    from sentiment.finbert_client import get_sentiment
    ```

### F. Context Window Syntax Bug
- **File**: `/workspaces/ai-trading-bot/tests/e2e/test_tier2_boundary.py` (line 258)
  - `test_llm_context_window_overflow` specifies:
    ```python
    large_context = {"indicators": {"vwap": 1.0} * 1000}
    ```
  - This dictionary multiplication raises `TypeError`.

### G. Port 8000 Conflict
- **File**: `/workspaces/ai-trading-bot/tests/e2e/conftest.py` (lines 156-163)
  - The `dashboard_server` fixture runs the dashboard via subprocess but does not release/kill prior processes on port 8000.

### H. Dependencies Cleanup
- **File**: `/workspaces/ai-trading-bot/requirements.txt`
  - Unused dependencies `beautifulsoup4`, `aiohttp`, `apscheduler`, and `websockets` are declared.

---

## 2. Logic Chain

1. **Sentiment API Fix**: Returning a hybrid `SentimentResult(float)` class from `get_sentiment` satisfies both the E2E tests (type comparison to float) and the trading loop (direct subscripting for keys like `"score"` and `"headlines"`).
2. **Politician Client API Fix**: Updating `_fetch_quiver_trades` to query `CONGRESS_DISCLOSURE_URL` when set allows parsing the E2E test's CSV payload. Adding keys `"ticker"`, `"signal_score"`, and `"trade_type"` to the returned dict bridges the gap between production and tests.
3. **Order Manager Key Fix**: Injecting mock keys into `os.environ` in `conftest.py` ensures the E2E tests execute orders against the HTTP mock server rather than falling back to demo mode.
4. **Settings DB Table Fix**: Creating the `settings` table in `automation/trading_loop.py`'s `init_db` and seeding default settings values in E2E database cleanups prevents query errors during circuit breaker/settings test cases.
5. **Monkeypatch Namespace Fix**: Patching the locally imported name `"tests.e2e.test_tier1_feature.get_sentiment"` resolves namespace shadowing.
6. **Syntax Error Fix**: A dictionary comprehension `{f"vwap_{i}": 1.0 for i in range(1000)}` correctly scales the context size.
7. **Port Conflict Fix**: Running `fuser -k 8000/tcp` before launching the dashboard server releases any orphaned background processes on the port.
8. **Dependency Cleanup**: Removing the 4 unused dependencies simplifies package deployment.

---

## 3. Caveats

- We assumed that `fuser` is installed in the test execution environment; if not, alternative methods like parsing `/proc/net/tcp` or using `kill` based on `lsof` can be implemented.
- We assume the database name used during E2E tests remains `test_trading.db` as defined in environment variables.

---

## 4. Conclusion

We recommend applying the following specific fixes to resolve the 9 failing test cases:

1. **`SentimentResult(float)` implementation** in `sentiment/finbert_client.py` to bridge the dict vs float return type mismatch.
2. **`CONGRESS_DISCLOSURE_URL` integration & key mapping** in `politician/copy_mode.py`.
3. **Mock Alpaca Keys injection** in `tests/e2e/conftest.py`.
4. **`settings` table initialization and seeding** in `trading_loop.py` and `conftest.py`.
5. **Correct target patching path** in `test_sentiment_cache`.
6. **Dict comprehension fix** in `test_llm_context_window_overflow`.
7. **Process cleanup execution (`fuser`)** in `dashboard_server` fixture.
8. **Removal of the 4 unused dependencies** from `requirements.txt`.

---

## 5. Verification Method

Independent verification can be executed as follows:
- Run `pytest` on the test suite:
  ```bash
  pytest tests/
  ```
- Command to verify requirements.txt matches imports:
  ```bash
  pip-check (or manually inspecting imports)
  ```
- Verification invalidation: If any technical indicators return invalid ranges, or if the dashboard server fails to boot on port 8000, the implementation is invalid.
