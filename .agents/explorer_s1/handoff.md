# E2E Test Suite Design Report (R1-R5) — explorer_s1

This report presents the E2E analysis and design proposal for testing the new features of the APEX AI trading bot. It details existing test structures, outlines extensions for `mock_server.py`, and maps out a 4-tier test case design.

---

## 1. Observation

Based on static analysis of the workspace directories and codebase, the following files and structures were identified:

### Existing E2E Test Suite Structure
The E2E tests are located in `tests/e2e/` and organized into files corresponding to a tiered methodology:
1. **`tests/e2e/conftest.py`**: Configures session-wide mock HTTP (port 8001) and WebSocket (port 8002) servers, sets mock API environment variables (`ALPACA_API_BASE_URL`, `OPENAI_API_BASE`, etc.), and provides database cleanup and CLI execution fixtures (`run_cli`, `dashboard_server`).
2. **`tests/e2e/mocks/mock_server.py`**:
   - Imulates the Alpaca REST API (`/v2/orders`, `/v2/account`, `/v2/positions`), OpenAI completions, Gemini content generation, FinBERT news sentiment, Yahoo Finance indicators, and Congress disclosures.
   - Provides a `POST /mock_control` endpoint that sets `status_overrides` and `response_delays` to simulate error states and latency.
3. **`tests/e2e/test_tier1_feature.py`**: Tests happy paths of scanner, news sentiment, politician tracking, LLM decisions, bracket orders, and the web dashboard (e.g. `test_scan_happy_path` in lines 23-43, `test_exec_bracket_order` in lines 263-273).
4. **`tests/e2e/test_tier2_boundary.py`**: Tests corner cases like zero volume, penny stocks, API timeouts, invalid LLM action types, out-of-bounds stop loss prices, and unauthorized dashboard access (e.g. `test_scan_zero_volume` in lines 21-30, `test_llm_hallucinated_action` in lines 202-217).
5. **`tests/e2e/test_tier3_combinatorial.py`**: Verifies cross-feature interactions like negative sentiment filtering, circuit breakers halting scans/trades, and watchdog service recovery (e.g. `test_comb_scanner_to_sentiment` in lines 13-39).
6. **`tests/e2e/test_tier4_scenarios.py`**: Exercises full lifecycles, outage recovery, and high-frequency news ingestion under load (e.g. `test_scenario_standard_trading_day` in lines 13-37).
7. **`tests/e2e/test_e2e_flow.py`**: Executes an integrated scan-to-trade cycle, checking database outputs and mock server states.

### Observed API Mismatches
1. In `tests/e2e/test_tier1_feature.py` line 328, the dashboard REST test queries `f"{dashboard_server}/trades"`, whereas `dashboard/app.py` line 81 defines the endpoint as `@app.get("/api/trades")`.
2. In `tests/e2e/test_tier1_feature.py` line 341, the test opens a websocket to `f"ws://localhost:8000/ws/updates"`, but `dashboard/app.py` line 133 exposes it at `@app.websocket("/ws")`.
3. In `tests/e2e/test_tier1_feature.py` line 358, the test POSTs settings updates to `f"{dashboard_server}/api/settings"`, but `dashboard/app.py` has no corresponding POST handler implemented.
4. Legacy shims in `main.py` lines 142-371 bypass the production class `TradingBot` in `automation/trading_loop.py` to run simulated day trade pipelines for tests.
5. Production APIs in `sentiment/finbert_client.py` and `politician/copy_mode.py` have schema differences with test mocks (e.g. dict vs float sentiment scores).

---

## 2. Logic Chain

From the observations, the following logical inferences are made to design the E2E tests:

1. **Integration and Subprocesses**: Because the existing test suite runs the bot via subprocess commands (`main.py --mode scan/trade` or the new subcommand structure `main.py bot/scan`), our E2E tests must configure system state through config file templates (`config/config.yaml`), environment variables, or mock server API calls (`POST /mock_control`), and then run the CLI to check output state in the database (`test_trading.db`) and the mock server memory.
2. **Interactive Brokers (IB) Delegation**: Since `execution/order_manager.py` will delegate execution to either `AlpacaExecutor` or the new `IBExecutor` based on configuration, the E2E mock server must handle either Alpaca REST endpoints or IB REST/socket endpoints depending on the configuration. To support unified state checks, the mock server state (`state.orders`, `state.positions`) should be shared between Alpaca and IB endpoints, ensuring consistency.
3. **Reasoning Model Integration**: The Morning Deep Research Engine (R1) will call advanced reasoning models (Gemini Deep Think or OpenAI o3-mini). We must configure mock server routes for these reasoning endpoints (e.g. `/gemini/v1beta/models/gemini-2.0-flash-thinking` or `/openai/v1/chat/completions` with the `o3-mini` model parameter) that return structured pre-market research JSON.
4. **Key Validation in Wizards**: The setup wizards validate entered API credentials by making low-cost "get account" metadata requests. The mock server must return 401/403 errors when called with a recognized invalid key string (e.g., `invalid_alpaca_key` or `invalid_ib_account`), allowing the test runner to assert that the wizard blocks proceeding.
5. **Headless GUI Testing**: Because GUI applications (like the Tkinter setup wizard on Windows) require graphical displays, running them in headless CI environments requires programmatic Tkinter drivers that initialize the app root, modify field variables (`StringVar`), trigger button handlers directly, and check config file outputs without rendering the window.

---

## 3. Caveats

1. **Packaging Executables**: E2E testing of the packaged Windows `.exe` and Linux binary cannot be fully automated inside a headless Linux workspace without cross-compilation environments. Thus, the App Packaging tests (TC-4.5) will verify that PyInstaller pins dependencies and compiles the binaries, executing the Linux CLI binary inside the workspace with `--help` or `status` to spot-check basic entry point stability.
2. **Interactive Brokers Interface Style**: It is assumed that `execution/ib_executor.py` uses either IB Client Portal REST APIs or `ib_insync` TCP socket APIs. The mock server extensions are designed to support both options to give the implementer flexibility.
3. **Database Concurrency**: In high-frequency or combinatorial tests, SQLite can encounter "Database Locked" errors due to concurrent dashboard reads and bot writes. The test database cleanup and helper fixtures must handle retries or utilize a shared lock.

---

## 4. Conclusion

A complete E2E design is proposed below, specifying mock server additions, API contracts, and a 4-tier test case hierarchy.

### 4.1. Mock Server Extensions (`tests/e2e/mocks/mock_server.py`)

To support testing R1-R5, add the following endpoints and classes to the mock server:

#### A. Interactive Brokers Mocking
If using the REST Client Portal API (port 5000 / configured route):
- `GET /ib/v1/api/iserver/accounts`: Returns account details.
- `GET /ib/v1/api/portfolio/{accountId}/meta`: Returns cash, equity, buying power.
- `GET /ib/v1/api/portfolio/{accountId}/positions`: Returns positions list.
- `POST /ib/v1/api/iserver/account/{accountId}/orders`: Accepts order inputs. If order type is limit, uses the entry price; if side is buy, places bracket TP/SL child legs.
- `DELETE /ib/v1/api/iserver/account/{accountId}/order/{orderId}`: Cancels order.
- `DELETE /ib/v1/api/portfolio/{accountId}/positions`: Liquidates positions.

If using native TWS Socket (`ib_insync` on port 7497):
- Add `MockIBSocketServer` to run in a background thread alongside the HTTP mock.
- Handles connections, performs TWS version handshake, parses incoming standard requests (`reqPositions`, `placeOrder`, `cancelOrder`), and broadcasts matching TCP responses (`position`, `orderStatus`, `openOrder`).

#### B. Morning Deep Research Reasoning Model Mocking
- `POST /gemini/v1beta/models/gemini-2.0-flash-thinking:generateContent` & `POST /openai/v1/chat/completions` (when `model` is `o3-mini`):
  - Returns structured research JSON matching:
    ```json
    {
      "macro_outlook": "Bullish macro backdrop. Tech sector leading.",
      "vix": 14.5,
      "sector_trends": {
        "Technology": "bullish",
        "Healthcare": "neutral",
        "Energy": "bearish"
      },
      "catalysts": {
        "AAPL": {"event": "Product release today at 10 AM", "sentiment": "positive"},
        "TSLA": {"event": "Earnings release pre-market", "sentiment": "negative"}
      },
      "insider_sentiment": {
        "AAPL": 0.85,
        "TSLA": -0.40
      }
    }
    ```

#### C. Setup Wizard Authentication Verification Mocks
- If Alpaca header `APCA-API-KEY-ID` equals `"invalid_key"`, return `401 Unauthorized`.
- If IB request header contains `"invalid_ib_account"`, return `403 Forbidden`.

---

### 4.2. 4-Tier E2E Test Case Design Specification

#### Tier 1: Feature Coverage (5+ cases per feature)

##### Feature 1: Morning Deep Research (R1)
* **TC-1.1: Pre-Market Schedule Trigger**
  * *Verification*: Set pre-market scan time to 2 seconds in the future. Launch `main.py bot`. Verify trading loop waits, fires research engine at the designated time, and logs execution.
* **TC-1.2: Research Data Persistence**
  * *Verification*: Execute research command. Query `test_trading.db` or check JSON directory. Verify data is saved with correct columns (`macro_outlook`, `vix`, `sector_trends`, `catalysts`, `insider_sentiment`).
* **TC-1.3: Macro & Sector Context Extraction**
  * *Verification*: Mock reasoning model to return specific VIX values and sector strengths. Run research. Verify correct indicators are saved in SQLite tables.
* **TC-1.4: Catalyst Detection**
  * *Verification*: Configure mock server with positive catalyst for AAPL and negative catalyst for TSLA. Run research. Verify catalyst strings are stored in DB.
* **TC-1.5: Decision Pipeline Integration**
  * *Verification*: Populate DB with positive pre-market research on AAPL. Run `main.py --mode trade`. Verify Tier 2 decision logic incorporates research strings in the LLM prompt.

##### Feature 2: Interactive Brokers Backend Integration (R2)
* **TC-2.1: Broker Backend Selection**
  * *Verification*: Edit `config.yaml` to set `broker.provider` to `ib` (or `interactive_brokers`). Run trade. Verify requests hit IB mock endpoints instead of Alpaca.
* **TC-2.2: IB Bracket Order Placement**
  * *Verification*: Execute buy signal. Assert mock server receives order containing main limit buy + TP limit sell + SL stop sell, and generates order IDs.
* **TC-2.3: IB Position Tracking**
  * *Verification*: Place buy order. Query `/api/portfolio` on the dashboard. Verify dashboard retrieves positions from IB mock and matches quantities.
* **TC-2.4: IB Order Cancellation**
  * *Verification*: Submit limit buy. Before it fills, trigger cancel. Assert DELETE request is sent to IB mock and order status changes to Cancelled.
* **TC-2.5: IB EOD Liquidation**
  * *Verification*: Set open positions on IB mock. Run EOD close code. Assert DELETE positions request is received by IB mock and positions are cleared.

##### Feature 3: Premium Dashboard Enhancements (R3)
* **TC-3.1: Morning Research Panel Content**
  * *Verification*: Populate research table in DB. Query GET `/api/research`. Assert JSON contains correct research texts and Outlook headers.
* **TC-3.2: Trade Performance Analytics**
  * *Verification*: Populate DB with 4 winning trades and 1 losing trade. Query GET `/api/analytics`. Verify response contains `win_rate: 0.80`, computed Sharpe ratio, and total P&L.
* **TC-3.3: Interactive Chart History**
  * *Verification*: Ingest 50 portfolio snapshots. Query GET `/api/portfolio/history`. Verify coordinates map correctly for Chart.js rendering.
* **TC-3.4: Settings Configuration Page**
  * *Verification*: POST to `/api/settings` with payload `{"stop_loss_pct": "1.00"}`. Verify `config.yaml` is modified and database settings table reflects the new value.
* **TC-3.5: Dashboard Real-Time WebSocket Updates**
  * *Verification*: Establish a websocket connection. Trigger a trade. Assert JSON update event is immediately pushed down the socket containing the trade details.

##### Feature 4: Cross-Platform Setup Wizards (R4)
* **TC-4.1: CLI Setup Wizard Stdin Flow**
  * *Verification*: Spawn Linux CLI wizard in a subprocess. Pipe inputs for keys, broker, and risk. Verify script exits with status 0 and generates valid `.env` and `config.yaml`.
* **TC-4.2: GUI Setup Wizard Programmatic Flow**
  * *Verification*: Launch the Tkinter app class in headless mode. Set form string variables programmatically, trigger save callback. Assert files are written correctly.
* **TC-4.3: Wizard Credentials Verification (Success)**
  * *Verification*: Input valid mock keys in wizard. Wizard tests connection to mock server. Assert wizard displays green validation check and permits proceeding.
* **TC-4.4: Wizard Credentials Verification (Failure)**
  * *Verification*: Input `invalid_key` in wizard. Assert wizard shows error dialog, provides API signup links, and disables the "Finish" button.
* **TC-4.5: Package Executable Compilation**
  * *Verification*: Run PyInstaller packaging script. Verify compilation succeeds and that the output binary can execute `status` commands.

##### Feature 5: Enhanced Trading Engine Logic (R2)
* **TC-5.1: US Holiday Awareness**
  * *Verification*: Mock current date to Christmas Day. Run trading loop. Assert bot logs holiday detection, skips scans, and goes to sleep.
* **TC-5.2: Macro Context Calculation**
  * *Verification*: Run trade engine under heavy bearish indices. Assert `calculate_macro_context` outputs score below -0.50.
* **TC-5.3: LLM API Rate Limiting**
  * *Verification*: Run consecutive LLM requests. Assert client rate-limits calls to Gemini/OpenAI, waiting for the designated throttle window before proceeding.
* **TC-5.4: Default Paper Trading Safeguard**
  * *Verification*: Clean `.env` files. Start bot. Assert it default-runs in paper mode on mock URLs and prints clear warnings.
* **TC-5.5: Time-Aware 3:55 PM Liquidation**
  * *Verification*: Mock system time to 3:55 PM EST on a trading day. Assert loop halts cycle scans and executes `close_all_positions()`.

---

#### Tier 2: Boundary & Corner Cases (5+ cases per feature)

##### Boundary 1: Morning Deep Research (R1)
* **TC-6.1: Research Model Rate Limits (HTTP 429)**
  * *Verification*: Override mock reasoning endpoint to 429. Assert research engine retries with exponential backoff before logging error and falling back to scanning.
* **TC-6.2: Missing Historical Macro Feeds**
  * *Verification*: Set mock VIX feed to empty. Verify research engine handles null data gracefully, logging a warning but continuing sector analyses.
* **TC-6.3: Malformed AI Research JSON Output**
  * *Verification*: Configure LLM mock to return invalid JSON text. Assert research engine runs text parser cleanup regexes, or falls back to neutral defaults.
* **TC-6.4: Scheduled Run during API Outage**
  * *Verification*: Override reasoning endpoint to 503. Assert bot logs outage, bypasses deep research, and executes normal day trading using fallback indicators.
* **TC-6.5: Empty Ticker Catalyst Event**
  * *Verification*: Pass a watchlist ticker with no catalyst scheduled. Assert research outputs `"None"` or `"Neutral"` catalyst without crashing.

##### Boundary 2: Interactive Brokers (R2)
* **TC-7.1: Insufficient Buying Power**
  * *Verification*: Send a buy order exceeding account cash. Verify IB mock returns order rejection. Assert bot logs error, skips trade, and continues.
* **TC-7.2: IB Gateway Disconnection**
  * *Verification*: Force mock socket/REST server connection drop. Assert bot raises GatewayTimeout, halts loop, and activates watchdog warning.
* **TC-7.3: Partially Filled Bracket Legs**
  * *Verification*: Place buy order. Mock a partial fill of 40% on entry. Verify stop-loss and take-profit legs are immediately resized to match the filled size.
* **TC-7.4: Invalid IB Port Configuration**
  * *Verification*: Set port to invalid number. Verify executor prints clear guidance on configuring TWS/Gateway socket ports and exits cleanly.
* **TC-7.5: Wash Sale / Short Sale Restriction Rejections**
  * *Verification*: Mock IB order rejection due to short-sale restrictions. Assert bot catches error, logs trade rejection, and marks ticker as blacklisted for the day.

##### Boundary 3: Premium Dashboard (R3)
* **TC-8.1: First-Time Launch (Empty DB State)**
  * *Verification*: Wipe database. Query GET `/api/analytics` and `/api/trades`. Assert dashboard responds with empty structures (status 200) and displays clear instructions.
* **TC-8.2: 100+ Concurrent Websocket Clients**
  * *Verification*: Open 100 websocket connections to `/ws`. Verify memory footprint remains stable and broadcast event latency remains under 50ms.
* **TC-8.3: Settings Validation Boundary Checks**
  * *Verification*: POST to `/api/settings` with invalid values (e.g., `-1.5` stop-loss or `abc` port). Verify server returns 400 Bad Request and DB remains unchanged.
* **TC-8.4: Database Locked Retries**
  * *Verification*: Lock the database in a background thread. Perform a trade save. Verify order manager runs SQLite retry handler, waiting for unlock before completing write.
* **TC-8.5: Cross-Origin Security Restrictions**
  * *Verification*: Perform OPTIONS pre-flight request from `evil-dashboard.com`. Assert CORS filters block access, returning correct forbidden headers.

##### Boundary 4: Setup Wizards (R4)
* **TC-9.1: Malformed Keys Pattern Matching**
  * *Verification*: Enter API key with spaces or special symbols in the text box. Assert wizard regex validation marks field in red and blocks submission.
* **TC-9.2: Read-Only System Permission Faults**
  * *Verification*: Set parent folder permission to read-only. Submit configuration. Assert wizard shows "Permission Denied: Unable to write config.yaml" message box and keeps user inputs intact.
* **TC-9.3: Abrupt Termination Recovery**
  * *Verification*: Terminate setup wizard mid-way. Assert no corrupted/empty files are saved, and relaunching wizard defaults to fresh guided instructions.
* **TC-9.4: Special Character Passwords**
  * *Verification*: Input password containing characters like `$` or `\` in credentials. Verify setup wizard escapes inputs when writing to files.
* **TC-9.5: Command-Line Flags Overrides**
  * *Verification*: Launch CLI setup wizard with invalid options. Assert wizard displays instructions and exits with error code 1.

##### Boundary 5: Enhanced Trading Engine (R2)
* **TC-10.1: Weekend Holiday Interruption**
  * *Verification*: Run bot on a Saturday. Assert bot sleeps until Monday, bypassing scan triggers.
* **TC-10.2: Extreme Macro Context Scores (-1.0 and +1.0)**
  * *Verification*: Set macro context score to +1.0. Assert bot sizes orders to configured maximum (20%). Set to -1.0. Assert bot skips BUY orders.
* **TC-10.3: Rapid Consecutive Order Limits**
  * *Verification*: Generate 5 trade signals in 1 second. Verify bot queues and paces order submissions to stay within rate limits.
* **TC-10.4: Position Liquidation Failure at 3:55 PM**
  * *Verification*: Override positions deletion endpoint to 500. Execute EOD close. Verify bot retries deletion every 15 seconds, sending critical warnings until successful.
* **TC-10.5: Watchlist with 100+ Tickers**
  * *Verification*: Configure watchlist with 100 stocks. Assert pre-market scanner processes symbols in chunks without exceeding API limits.

---

#### Tier 3: Cross-Feature Combinations (Pairwise)

* **TC-11.1: Interactive Brokers + Holiday Trade Blocking**
  * *Combination*: `broker.provider: ib` + current date is Christmas.
  * *Verification*: Verify bot stays in sleep loop, placing no connection handshakes or mock requests.
* **TC-11.2: Morning Deep Research + Interactive Brokers Execution**
  * *Combination*: Pre-market research (R1) + IB execution (R2).
  * *Verification*: Deep research identifies positive TSLA catalyst and stores it. Market opens. Trading engine triggers trade on TSLA on IB using research sizing metrics.
* **TC-11.3: Setup Wizard + Premium Dashboard Synchronization**
  * *Combination*: CLI setup wizard configuration (R4) + Dashboard app settings view (R3).
  * *Verification*: Run wizard to set stop loss to 1.25%. Launch dashboard server. Query GET `/api/config`. Assert returned JSON contains `stop_loss_pct: 1.25`.
* **TC-11.4: Rate Limiting + Pre-Market scan**
  * *Combination*: Sentiment API rate limiting (R2) + scan execution (R1).
  * *Verification*: Simulate NewsAPI HTTP 429. Assert pre-market scanner handles rate limits by sleeping and completes processing without dropping tickers.
* **TC-11.5: Circuit Breaker + Interactive Brokers Liquidation**
  * *Combination*: Daily loss limit hit (R2) + IB position management (R2).
  * *Verification*: Open positions on IB. Force portfolio drop on IB mock. Assert circuit breaker trips, sends Telegram alert, cancels open orders, and liquidates positions on IB.
* **TC-11.6: OpenAI Outage + Gemini Fallback + Interactive Brokers**
  * *Combination*: OpenAI down (R2) + LLM fallback (R2) + IB execution (R2).
  * *Verification*: Override `/openai` to 503. Run trade. Verify bot fails back to Gemini 1 Pro, receives decision, and places order on IB.

---

#### Tier 4: Real-World Scenarios

* **TC-12.1: Integrated Day-Trading Lifecycle on Interactive Brokers**
  * *Timeline*:
    1. **08:00 AM**: Pre-market research runs (Gemini Thinking), saving macro sentiment (Tech Bullish) and TSLA catalyst (Earnings Upbeat) to DB.
    2. **09:30 AM**: Market opens. Loop starts. Trades are set to execute via IB.
    3. **10:00 AM**: Scanner inputs + research scores trigger Tier 2 LLM. Bot places bracket buy order for TSLA on IB.
    4. **02:00 PM**: TSLA hits take-profit limit. Position is closed. Profit logged.
    5. **03:55 PM**: EOD close checks positions, liquidates remaining.
    6. **04:00 PM**: P&L and win rate computed, sent via Telegram, database snapshot saved.
* **TC-12.2: Bearish Macro FOMC Downturn Panic on Alpaca**
  * *Timeline*:
    1. **08:00 AM**: Deep research notes Federal Reserve meeting, VIX spikes to 28.5 (Bearish).
    2. **09:30 AM**: Market opens. Macro context score calculated at -0.82, risk management reduces trade size by 50%.
    3. **10:15 AM**: Market drops sharply. Open positions hit stop losses.
    4. **11:00 AM**: Realized loss exceeds 2%. Daily circuit breaker trips.
    5. **11:01 AM**: Bot cancels pending orders, liquidates positions, sends alert, and enters sleep loop until next day.
* **TC-12.3: Watchdog Recovery and State Synchronization on IB**
  * *Timeline*:
    1. Bot holds 100 shares of MSFT on IB with active bracket legs.
    2. The local executor process crashes. Watchdog detects crash.
    3. Watchdog restarts process, reads state, queries IB positions API.
    4. Bot reconciles holdings, matches active order IDs, recovers TSLA bracket legs, and resumes loop.
* **TC-12.4: Newbie Onboarding to Safe Trading Flow**
  * *Timeline*:
    1. Newbie runs `setup_wizard` CLI/GUI.
    2. Guided screens explain API keys, provide registration links.
    3. User enters keys, selects IB Paper. Wizard validates keys against mock (success).
    4. Configuration saved. User starts bot. Bot initializes paper trading securely.
* **TC-12.5: Multi-Day Run with Holiday & Weekend Interruption**
  * *Timeline*:
    1. **Thursday 3:55 PM**: Bot active, EOD liquidation, sleeps overnight.
    2. **Friday 08:00 AM (Good Friday)**: Bot wakes up, detects US stock market holiday in calendar, logs sleep status, goes to sleep until Monday.
    3. **Saturday-Sunday**: Wakes up, checks weekend, sleeps.
    4. **Monday 08:00 AM**: Wakes up, runs pre-market research, and enters active trading.

---

## 5. Verification Method

To independently verify this design and prepare for the implementation track:

1. **Verify Interface Contracts**:
   - Inspect files in `tests/e2e/` (specifically `test_tier1_feature.py` and `mocks/mock_server.py`) using `view_file` to confirm compatibility of route additions.
   - Inspect target interface contracts in `.agents/orchestrator/PROJECT.md` to ensure mock formats match the specified module APIs.
2. **Review Mismatches Fixes**:
   - Inspect `dashboard/app.py` and verify that the endpoint paths match the E2E test GET calls.
3. **Execution Verification (in M6/Milestone S5)**:
   - Once implemented by the worker agent, the E2E test suite can be run using the standard project test command:
     ```bash
     pytest tests/e2e
     ```
   - Successful completion of the test suite (100% passing tests) will confirm the verification of all R1-R5 features.
