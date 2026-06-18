# E2E Test Suite Redesign & Implementation Strategy

**Working Directory:** `/workspaces/ai-trading-bot/.agents/explorer_s2_1`  
**Author:** explorer_s2_1 (teamwork_preview_explorer)

---

## 1. Observation

A detailed review was conducted of the current E2E test file (`tests/e2e/test_r1_r5_e2e.py`), mock backend servers (`tests/e2e/mocks/mock_server.py`), test configurations (`tests/e2e/conftest.py`), and the core codebase modules (`dashboard/app.py`, `execution/order_manager.py`, `engine/llm_brain.py`, `main.py`).

Direct observations are compiled below:

### Observation A: Facade Implementation and Local Stubs
The test file `tests/e2e/test_r1_r5_e2e.py` implements its own mock representations of core trading logic and configurations inside the test file itself:
*   **Line 21**: `class IBExecutor` is defined locally to stub Interactive Brokers integration.
*   **Line 79**: `def run_morning_research(...)` is defined locally to stub AI research logic and database persistence.
*   **Line 151**: `class MockCLISetupWizard` is defined locally to stub CLI configuration setup.
*   **Line 167**: `class MockGUISetupWizard` is defined locally to stub GUI configuration setup.
*   **Lines 189 & 198**: `is_market_holiday(...)` and `calculate_macro_context(...)` are written locally rather than imported.

These stubs hide the lack of production implementations for Interactive Brokers and setup wizards, bypass the actual `AlpacaExecutor` in `execution/order_manager.py`, and bypass the actual tiered decision logic in `engine/llm_brain.py`.

### Observation B: Dynamic FastAPI Route Injection
In `tests/e2e/test_r1_r5_e2e.py` (Lines 208-243), the test suite imports the premium dashboard application and decorates it dynamically with test-only routes:
*   `@dashboard_fastapi_app.get("/api/research")`
*   `@dashboard_fastapi_app.get("/api/analytics")`
*   `@dashboard_fastapi_app.post("/api/settings")`

These API endpoints do not exist in the production dashboard app (`dashboard/app.py`). The test server is self-testing routes it injected dynamically, masking the absence of these endpoints in the actual application.

### Observation C: Misaligned Requirements Mapping
The R1-R5 features defined and executed in `test_r1_r5_e2e.py` are mapped to non-existent features (e.g. Interactive Brokers, GUI/CLI Wizards, and custom morning research) instead of the actual project specifications defined in `.agents/ORIGINAL_REQUEST.md`.

*   **Original Specifications (R1-R5)**:
    *   **R1**: Real-Time Market Data & Technical Analysis (VWAP, MACD, RSI, Bollinger Bands, EMA, RVOL + Pre-market scanner)
    *   **R2**: News Sentiment Analysis (headline ingestion + FinBERT model scoring)
    *   **R3**: Politician Trade Copy Mode (U.S. Congressional stock disclosures + blending into decision pipeline)
    *   **R4**: Tiered LLM Decision Engine (Tier 1 Gemini screening + Tier 2 OpenAI decision with failover)
    *   **R5**: Fully Automated Order Execution (Alpaca bracket orders, auto-close by 3:55 PM, paper/live mode, watchdog)
*   **Test File Mappings (R1-R5)**:
    *   **R1**: Morning Deep Research (local stub)
    *   **R2**: Interactive Brokers Integration (local stub, not in requirements)
    *   **R3**: Premium Dashboard Enhancements (patches endpoints onto app)
    *   **R4**: Setup Wizards (local stub, not in requirements)
    *   **R5**: Enhanced Trading Engine Logic (local helper functions)

### Observation D: Database Isolation Leak
In `dashboard/app.py` lines 46-49, the database connection is established via:
```python
def get_db():
    config = get_config()
    db_path = config.get("database", {}).get("path", "trading.db")
    return sqlite3.connect(db_path)
```
This fails to check the `DATABASE_PATH` environment variable. In `tests/e2e/conftest.py` line 78, the environment variable `os.environ["DATABASE_PATH"] = "test_trading.db"` is set to isolate test operations. Consequently, the premium dashboard endpoints run queries directly against the production database file `trading.db`, contaminating live data.

### Observation E: Lock Contention in Mock Server
In `tests/e2e/mocks/mock_server.py` line 571, the `broadcast` method iterates through client connections and issues `client.sendall(frame)` commands inside a global state lock block:
```python
with state.lock:
    for client in self.clients:
        try:
            client.sendall(frame)
        ...
```
Performing network I/O operations while holding `state.lock` blocks all other concurrent requests to HTTP endpoints on the mock server, creating a potential concurrency deadlock or timeout bottleneck.

### Observation F: WebSocket Infinite Hang Risk
In `dashboard/app.py` lines 133-161, the `/ws` websocket handler queries the database and silently swallows any database exceptions (such as missing `signals` or `decisions` tables in an empty test database) with a silent `except: pass` block:
```python
try:
    signals = db.execute("SELECT ...").fetchall()
    ...
    await ws.send_json(data)
except:
    pass
```
If an exception occurs, the server skips sending a JSON payload, sleeps for 5 seconds, and loops. In `tests/e2e/test_r1_r5_e2e.py` line 380, the test client executes `ws.recv()`. Because the server enters a loop where it never sends a message, `ws.recv()` blocks indefinitely, causing the test runner to hang.

---

## 2. Logic Chain

1.  **Observations A, B, and C** demonstrate that `test_r1_r5_e2e.py` bypasses testing the actual codebase by defining stubs directly inside the test code and injecting fake endpoints into the FastAPI app. Thus, the tests pass even if the production modules are completely broken, missing, or misconfigured.
2.  **Observation D** demonstrates that database isolation is broken. The dashboard always targets the production `trading.db` database regardless of the test environment setup. This exposes the production environment to side-effects and prevents reliable test execution.
3.  **Observation E** indicates that mock server concurrency is bottlenecked because of network I/O inside the global state lock, creating reliability issues during high-load WebSocket testing.
4.  **Observation F** details a flaw in the dashboard app exception handling: swallowing errors on database failures causes the WebSocket to hang instead of closing or sending an error frame, which results in test suites hanging indefinitely.
5.  Therefore, to establish a robust, compliant E2E test suite, the stubbed/patched tests must be deleted, database isolation and websocket robustness must be implemented, and tests must be rewritten to target the real production files using conditional skips for unimplemented logic.

---

## 3. Caveats

*   No source code files were edited during this investigation (conforming to the read-only Explorer role).
*   Live test execution outcomes of the proposed rewritten tests could not be verified in the terminal due to non-interactive environment constraints. However, static code paths and import checks verify that the proposed strategy is architecturally sound.

---

## 4. Conclusion

The current E2E test suite in `tests/e2e/test_r1_r5_e2e.py` is a facade and does not verify the real codebase features (R1-R5). 

We recommend a complete rewrite of `test_r1_r5_e2e.py` that:
1.  **Removes all local stubs/facades** (`IBExecutor`, `MockCLISetupWizard`, `MockGUISetupWizard`, `run_morning_research`, etc.).
2.  **Removes dynamic FastAPI route injection** on `dashboard_fastapi_app`.
3.  **Imports and tests genuine production modules**: `AlpacaExecutor`, `llm_brain` (`tier1_screen`, `tier2_decide`), `get_sentiment`, and `get_politician_signals`.
4.  **Implements conditional skips** (`pytest.mark.skipif` / `pytest.mark.xfail`) to gracefully bypass tests for unimplemented modules and endpoints without breaking the test suite run.
5.  **Fixes database isolation, websocket exception handling, and mock server lock bottlenecks** in the target production files.

---

## 5. Verification Method

Once implemented, the rewritten test suite can be verified by running the project test command:
```bash
pytest tests/e2e/test_r1_r5_e2e.py
```

Invalidation conditions for the new test strategy include:
*   Any test passing when the imported module does not exist (unless marked with `skipif` / `xfail`).
*   Any test hanging indefinitely during execution.
*   The test suite modifying the production `trading.db` file instead of `test_trading.db`.

---

# E2E Test Suite Redesign Specification

## 1. Removing Local Stubs & Route Patching

All local class and function definitions must be deleted from `test_r1_r5_e2e.py`. All `@dashboard_fastapi_app.get` decorators defined inside the test file must be removed. 

The background FastAPI server fixture must start the dashboard app in its original state:
```python
@pytest.fixture(scope="module")
def real_dashboard_server():
    """Starts the genuine, unmodified dashboard FastAPI app in a background thread."""
    import uvicorn
    from dashboard.app import app as dashboard_fastapi_app
    server_thread = threading.Thread(
        target=lambda: uvicorn.run(dashboard_fastapi_app, host="127.0.0.1", port=8003, log_level="error"),
        daemon=True
    )
    server_thread.start()
    time.sleep(1.0)
    yield "http://localhost:8003"
```

## 2. Implementing Conditional Skips & Expected Failures

To ensure tests can be written for planned but unimplemented modules (e.g. a future Interactive Brokers executor) and unimplemented routes, we use try-except blocks and FastAPI app inspection.

### Check for Unimplemented Modules
```python
import pytest

# Interactive Brokers Executor (unimplemented)
try:
    from execution.ib_executor import IBExecutor
    HAS_IB_EXECUTOR = True
except ImportError:
    HAS_IB_EXECUTOR = False
    IBExecutor = None

# Custom Configuration Wizard (unimplemented)
try:
    from automation.wizards import CLISetupWizard, GUISetupWizard
    HAS_WIZARDS = True
except ImportError:
    HAS_WIZARDS = False
    CLISetupWizard, GUISetupWizard = None, None
```

### Check for Unimplemented API Routes
```python
from dashboard.app import app as dashboard_fastapi_app

def has_dashboard_route(path: str) -> bool:
    """Helper to check if a route path exists in the dashboard FastAPI app."""
    return any(route.path == path for route in dashboard_fastapi_app.routes)

HAS_RESEARCH_API = has_dashboard_route("/api/research")
HAS_ANALYTICS_API = has_dashboard_route("/api/analytics")
HAS_SETTINGS_API = has_dashboard_route("/api/settings")
```

### Decorating the Test Cases
```python
@pytest.mark.skipif(not HAS_IB_EXECUTOR, reason="Interactive Brokers executor is unimplemented in the codebase")
def test_ib_bracket_order_placement():
    # Test details...
    pass

@pytest.mark.skipif(not HAS_WIZARDS, reason="CLI/GUI setup wizards are unimplemented in the codebase")
def test_cli_wizard_flow():
    # Test details...
    pass

@pytest.mark.skipif(not HAS_RESEARCH_API, reason="Dashboard API /api/research endpoint is unimplemented")
def test_dashboard_research_panel(real_dashboard_server):
    # Test details...
    pass
```

## 3. Genuine E2E Test Case Design

### R1. Real-Time Market Data & Technical Analysis
Tests must use the actual `automation.scanner` and indicator tools against the mock server running on port 8001.
*   **TC-1.1: Pre-Market Scanner Run**: Trigger `run_scanner(DB_PATH, ["AAPL"], force=True)`. It queries mock Alpaca endpoints and stores results. Verify `scanned_tickers` table is populated in the database.
*   **TC-1.2: Technical Indicator Verification**: Verify values computed for `vwap`, `rsi`, `macd`, `bb_upper`, `bb_lower`, `ema`, and `rvol` in the database are numeric floats and fall within reasonable bounds.
*   **TC-1.3: yfinance Fallback**: Configure the mock server to return `500 Internal Server Error` for Alpaca historical data request. Run `run_scanner` and verify it falls back to mocked `yfinance` methods (setup in `conftest.py`) and successfully populates the database.
*   **TC-1.4: Pre-Market Schedule Enforcement**: Verify that scanning logic raises errors or outputs logs indicating pre-market execution limits if triggered after 9:30 AM EST (unless `force=True` is provided).
*   **TC-1.5: Watchlist Parsing**: Verify that the scanner retrieves the configured list from `config/config.yaml` and processes every ticker.

### R2. News Sentiment Analysis
Tests must verify news ingestion and sentiment score integration.
*   **TC-2.1: News Headlines Ingestion**: Call `get_sentiment("AAPL")`. Verify it routes to the mock News/FinBERT server on port 8001 and successfully retrieves headlines.
*   **TC-2.2: FinBERT Score Constraints**: Assert that computed sentiment scores are between -1.0 and 1.0.
*   **TC-2.3: Pipeline Blending**: Verify that sentiment scores are stored in the database (`signals` table) and passed correctly in the decision signal payload.
*   **TC-2.4: Negative Sentiment Halt**: Verify that a sentiment score below 0.0 (or -0.3) halts buy operations for that ticker in the trading loop.
*   **TC-2.5: API Outage Tolerance**: Mock the FinBERT endpoint to return 503 and ensure the sentiment analysis fallback returns a neutral score (`0.0`) without raising a crash.

### R3. Politician Trade Copy Mode
Tests must verify U.S. congressional trade tracking.
*   **TC-3.1: Politician Trade Disclosures Fetching**: Call `get_all_recent_trades()`. Verify it retrieves disclosures from the mock Capitol Hill endpoint.
*   **TC-3.2: Copy Signal Generation**: Verify `get_politician_signals("AAPL")` returns a dictionary containing a calculated signal score.
*   **TC-3.3: Blended Copy Score Integration**: Ensure politician scores are blended into the overall decision engine signals database table.
*   **TC-3.4: Copier Decision Rule Trigger**: Verify that a high politician copy score (e.g. >= 0.90) influences decisions and is logged in the `signals` table.
*   **TC-3.5: Dashboard Feed Delivery**: Send GET request to the real `/api/politicians` dashboard endpoint and verify it returns recent politician trades matching mock database state.

### R4. Tiered LLM Decision Engine
Tests must verify Gemini and OpenAI integrations.
*   **TC-4.1: Tier 1 Fast Screening**: Call `tier1_screen("AAPL", signals, config)`. Assert that it makes an API call to the mock Gemini service and returns a numeric opportunity score (0 to 10).
*   **TC-4.2: Structured Briefing Build**: Verify that if Tier 1 score exceeds the threshold, a structured briefing containing technical indicators, news sentiment, politician trades, and portfolio status is built and sent to Tier 2.
*   **TC-4.3: Tier 2 Decision Validation**: Call `tier2_decide("AAPL", signals, portfolio, config)`. Ensure the returned payload matches the required JSON schema (`action`, `confidence`, `entry`, `stop_loss`, `take_profit`, `position_pct`, `reasoning`).
*   **TC-4.4: Risk Rule Overrule**: Pass a Tier 2 decision with invalid risk rules (e.g., stop loss higher than entry price on a buy). Verify the wrapper overrules the action to `HOLD` with a reasoning update.
*   **TC-4.5: Provider Failover**: Set OpenAI mock API to return a 503 status code. Call the decision engine and verify it automatically falls back to Gemini 1.5 Pro to complete the decision loop.

### R5. Fully Automated Order Execution
Tests must use the actual `AlpacaExecutor` class.
*   **TC-5.1: Bracket Order Execution**: Call `AlpacaExecutor.place_bracket_order(ticker="AAPL", qty=10, side="buy", entry_price=150.0, stop_loss=140.0, take_profit=160.0)`. Verify it sends the bracket payload to the mock Alpaca server and returns a valid order ID.
*   **TC-5.2: EOD Auto-Close Trigger**: Mock system time to 3:56 PM EST and execute the trading loop iteration. Verify that the executor triggers `close_all_positions()` to liquidate holdings before market close.
*   **TC-5.3: Circuit Breaker Enforcement**: Set the `circuit_breaker_tripped` key to `true` in the database `settings` table. Verify that the execution pipeline immediately exits and blocks any new order execution.
*   **TC-5.4: Default Paper Safeguard**: Confirm that when credentials are not configured or set to default mocks, the executor defaults to paper trading, returning fake order IDs without attempting to reach real live endpoints.
*   **TC-5.5: Watchdog Crash Recovery**: Simulate a crashed state for the main trading process. Trigger `Watchdog.check_and_restart()` and assert that it correctly restarts the thread and logs the recovery event.

---

## 4. Required Production Code Improvements

To ensure these tests pass reliably, the following changes are required in the codebase:

### 1. Fix Database Isolation in `dashboard/app.py`
Modify `get_db()` in `dashboard/app.py` to respect the `DATABASE_PATH` environment variable:
```python
def get_db():
    db_path = os.environ.get("DATABASE_PATH")
    if not db_path:
        config = get_config()
        db_path = config.get("database", {}).get("path", "trading.db")
    return sqlite3.connect(db_path)
```

### 2. Fix WebSocket Hangs in `dashboard/app.py`
In the websocket endpoint `/ws`, handle database access failures without creating an infinite, silent wait loop. Close the connection or send an error payload:
```python
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            db = get_db()
            try:
                # Attempt to query tables
                signals = db.execute("SELECT ticker, rsi, macd, vwap, rvol, sentiment, politician_score, composite FROM signals").fetchall()
                decisions = db.execute("SELECT ticker, action, confidence, reasoning, timestamp FROM decisions ORDER BY id DESC LIMIT 5").fetchall()

                data = {
                    "type": "update",
                    "signals": [{"ticker": s[0], "rsi": s[1], "macd": s[2], "vwap": s[3], "rvol": s[4],
                                 "sentiment": s[5], "politician": s[6], "composite": s[7]} for s in signals],
                    "decisions": [{"ticker": d[0], "action": d[1], "confidence": d[2], "reasoning": d[3],
                                   "timestamp": d[4]} for d in decisions],
                    "timestamp": datetime.now().isoformat(),
                }
                await ws.send_json(data)
            except sqlite3.OperationalError as e:
                # Send error payload if database is not fully initialized
                await ws.send_json({"type": "error", "message": f"Database error: {str(e)}"})
            finally:
                db.close()
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        ws_clients.discard(ws)
```
Also, configure the client websocket tests to use a socket timeout:
```python
ws = websocket.create_connection(f"ws://localhost:8003/ws", timeout=2.0)
```

### 3. Remove Mock Server Lock Contention in `tests/e2e/mocks/mock_server.py`
Release the lock when writing network buffers to prevent slower clients from blocking mock API requests:
```python
def broadcast(self, message):
    payload = json.dumps(message).encode('utf-8')
    header = bytearray()
    header.append(0x81)  # Text frame
    length = len(payload)
    if length <= 125:
        header.append(length)
    elif length <= 65535:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
        
    frame = header + payload
    
    # Copy client list within lock to avoid race conditions
    with state.lock:
        clients_copy = list(self.clients)
        
    # Write to network outside lock
    for client in clients_copy:
        try:
            client.sendall(frame)
        except Exception:
            # Safely remove disconnected client inside lock
            with state.lock:
                if client in self.clients:
                    self.clients.remove(client)
```
