# Technical Analysis - Milestone 1 API Mismatch & Cleanup
**Explorer Agent 3** — 2026-06-18

This analysis documents the investigation into the 9 failing test cases and the requirements.txt cleanup under Milestone 1, recommending exact code fix strategies for each of the 8 local tasks.

---

## 1. Task Verification & Analysis

### Task 1: Sentiment Client API Mismatch
- **File**: `/workspaces/ai-trading-bot/sentiment/finbert_client.py` (around line 79-106)
- **Problem**: 
  - `get_sentiment(ticker)` returns a `Dict` representing `{"score": score, "headlines": headlines, "source": source}`.
  - The E2E tests in `/workspaces/ai-trading-bot/tests/e2e/test_tier1_feature.py` assert `score == pytest.approx(0.85)` and `-1.0 <= score <= 1.0`. These assertions expect a float directly, resulting in a type comparison failure.
  - The production loop in `/workspaces/ai-trading-bot/automation/trading_loop.py` (lines 231-232) expects a subscriptable dictionary:
    ```python
    sentiment_data = get_sentiment(ticker)
    signals["sentiment"] = sentiment_data["score"]
    signals["headlines"] = "; ".join(sentiment_data.get("headlines", [])[:3])
    ```
  - The execution loop in `/workspaces/ai-trading-bot/main.py` (line 234) handles either:
    ```python
    sentiment = sentiment_result["score"] if isinstance(sentiment_result, dict) else float(sentiment_result)
    ```
- **Fix Strategy**: 
  Create a hybrid class `SentimentResult` in `sentiment/finbert_client.py` inheriting from `float`. It overrides `__new__` to initialize as a float with the sentiment score, and implements `__getitem__` and `get()` for key-value dictionary lookup compatibility.
  ```python
  class SentimentResult(float):
      def __new__(cls, score: float, headlines: list = None, source: str = ""):
          obj = super().__new__(cls, score)
          obj.score = score
          obj.headlines = headlines or []
          obj.source = source
          return obj

      def __getitem__(self, key):
          if key == "score":
              return self.score
          elif key == "headlines":
              return self.headlines
          elif key == "source":
              return self.source
          raise KeyError(key)

      def get(self, key, default=None):
          try:
              return self[key]
          except KeyError:
              return default
  ```
  Update `get_sentiment` to return `SentimentResult(score, headlines, source)`.

---

### Task 2: Politician Client API Schema Mismatch
- **File**: `/workspaces/ai-trading-bot/politician/copy_mode.py` (around lines 29-46, and 142-164)
- **Problem**:
  - `get_politician_signals(ticker, config)` returns a dictionary containing production keys: `composite_score`, `trades`, and `direction`.
  - The tests in `/workspaces/ai-trading-bot/tests/e2e/test_tier1_feature.py` (lines 161-164, 193, 199) assert:
    - `data["ticker"] == "AAPL"`
    - `data["signal_score"] == 0.95`
    - `data["trade_type"] == "purchase"`
    - These test-expected keys are completely missing from the returned dictionary.
  - Additionally, `copy_mode.py` does not query the mock server URL set via the environment variable `CONGRESS_DISCLOSURE_URL`. In E2E tests, it falls back to demo trades and fails to fetch mock trades.
- **Fix Strategy**:
  1. Modify `_fetch_quiver_trades` to inspect the `CONGRESS_DISCLOSURE_URL` environment variable. If set, parse the CSV payload returned from that URL. Map the CSV fields `DisclosureDate` -> `TransactionDate`, `FilerName` -> `Representative`, `TradeType` -> `Transaction`.
  2. Update `get_politician_signals` to add `ticker`, `signal_score` (representing the `RecencyScore` from the mock data, or falling back to `composite_score`), and `trade_type` keys to the returned dictionary.
  ```python
  # In get_politician_signals:
  result = _compute_signal(trades, recency_window=recency)
  result["ticker"] = ticker
  matching = [t for t in trades if t.get("Ticker", "").upper() == ticker.upper()]
  if matching:
      first_trade = matching[0]
      try:
          result["signal_score"] = float(first_trade.get("RecencyScore", result["composite_score"]))
      except (ValueError, TypeError):
          result["signal_score"] = result["composite_score"]
      result["trade_type"] = first_trade.get("TradeType", first_trade.get("Transaction", "")).lower()
  else:
      result["signal_score"] = 0.0
      result["trade_type"] = None
  ```

---

### Task 3: Order Manager Demo Fallback
- **File**: `/workspaces/ai-trading-bot/tests/e2e/conftest.py` (lines 65-72) and `/workspaces/ai-trading-bot/execution/order_manager.py` (lines 30-32)
- **Problem**:
  - `AlpacaExecutor._is_configured()` checks if `ALPACA_API_KEY` is set and does not start with `"your_"`.
  - In `conftest.py`, the session-wide fixture `mock_servers` does not inject `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` into the environment, causing the executor to fall back to returning `demo-...` order IDs instead of hitting the mock server.
- **Fix Strategy**:
  Inject dummy keys into the environment in `tests/e2e/conftest.py` inside the `mock_servers` fixture:
  ```python
  os.environ["ALPACA_API_KEY"] = "mock_key"
  os.environ["ALPACA_SECRET_KEY"] = "mock_secret"
  ```

---

### Task 4: Settings DB Table Initialization
- **File**: `/workspaces/ai-trading-bot/automation/trading_loop.py` (lines 61-82) and `/workspaces/ai-trading-bot/tests/e2e/conftest.py` (lines 114-118)
- **Problem**:
  - The `settings` table is not initialized in `init_db` in `automation/trading_loop.py`.
  - The E2E tests and dashboard server attempt to check settings, but the settings values are not seeded, causing tests evaluating the circuit breaker or settings updates to fail or encounter missing keys/values.
- **Fix Strategy**:
  1. Add creation of the `settings` table to `init_db` in `automation/trading_loop.py`:
     ```python
     conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
     ```
  2. Seed initial default values in `tests/e2e/conftest.py` inside `clean_database` after table creation:
     ```python
     cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_loss_limit', '5000.00')")
     cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('circuit_breaker_tripped', 'false')")
     ```

---

### Task 5: Monkeypatch Namespace Resolution
- **File**: `/workspaces/ai-trading-bot/tests/e2e/test_tier1_feature.py` (line 147)
- **Problem**:
  - `test_sentiment_cache` attempts to monkeypatch `sentiment.finbert_client.get_sentiment`, but the test file imports `get_sentiment` directly using `from sentiment.finbert_client import get_sentiment` at line 10. The patch has no effect on the local reference.
- **Fix Strategy**:
  Change the patched namespace target in `test_sentiment_cache` to patch the reference inside `test_tier1_feature`:
  ```python
  monkeypatch.setattr("tests.e2e.test_tier1_feature.get_sentiment", mock_get)
  ```

---

### Task 6: Context Window Overflow Syntax Fix
- **File**: `/workspaces/ai-trading-bot/tests/e2e/test_tier2_boundary.py` (line 258)
- **Problem**:
  - `test_llm_context_window_overflow` attempts dictionary multiplication: `large_context = {"indicators": {"vwap": 1.0} * 1000}`. This is a syntax/runtime error in Python, throwing `TypeError: unsupported operand type(s) for *: 'dict' and 'int'`.
- **Fix Strategy**:
  Replace it with a valid dictionary comprehension:
  ```python
  large_context = {"indicators": {f"vwap_{i}": 1.0 for i in range(1000)}}
  ```

---

### Task 7: Port 8000 Conflict Resolution
- **File**: `/workspaces/ai-trading-bot/tests/e2e/conftest.py` (lines 156-163)
- **Problem**:
  - If port 8000 is occupied by an orphaned python process, the dashboard server started in E2E tests fails to bind, leading to test failures.
- **Fix Strategy**:
  Update `dashboard_server` fixture to execute `fuser -k 8000/tcp` before spawning the dashboard subprocess:
  ```python
  @pytest.fixture
  def dashboard_server():
      """Starts the main.py dashboard server in a background subprocess."""
      subprocess.run(["fuser", "-k", "8000/tcp"], capture_output=True)
      time.sleep(0.5)
      p = subprocess.Popen(["python3", "main.py", "--mode", "dashboard"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      time.sleep(1.0)
      yield "http://localhost:8000"
      p.terminate()
      p.wait()
  ```

---

### Task 8: Clean up requirements.txt
- **File**: `/workspaces/ai-trading-bot/requirements.txt`
- **Problem**:
  - Unused dependencies `beautifulsoup4`, `aiohttp`, `apscheduler`, and `websockets` are listed.
- **Fix Strategy**:
  Remove these lines from `/workspaces/ai-trading-bot/requirements.txt`.
