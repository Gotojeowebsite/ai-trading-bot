# Handoff Report — Technical Implementation Strategy for Milestone 1

## 1. Observation
- **Project Structure**:
  - We inspected the repository root and confirmed that it contains no source files or folders yet; only `.agents/`, `.git/`, `LICENSE`, and `README.md` are present.
  - From `/home/mint/Desktop/ai-trading-bot/.agents/orchestrator/PROJECT.md`, the code layout assigns `automation/` for ingestion, indicators, and pre-market scanning, and `tests/` for tests.
- **Python Environment**:
  - We checked the system Python package list: `pandas`, `numpy`, `yfinance`, and `alpaca-py` (or `alpaca`) are **NOT** installed.
  - Only `websockets` (10.4) is available globally.
  - Python version is 3.12.3, running in system-wide environment (no local `.venv` found).
- **Interface Contracts**:
  - From `PROJECT.md` and `SCOPE.md`, `automation/indicators.py` must implement `def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame` computing `vwap`, `macd`/`macd_signal`/`macd_hist`, `rsi`, `bb_upper`/`bb_middle`/`bb_lower`, `ema_fast`/`ema_slow`/`ema_crossover`, and `rvol`.
  - `automation/data_client.py` must stream market data via Alpaca WebSocket (supporting live/paper) or fallback to yfinance polling.
  - `automation/scanner.py` must run before 9:30 AM EST to build a watchlist based on gap percentage, pre-market volume, and news catalysts.
  - From `/home/mint/Desktop/ai-trading-bot/.agents/teamwork_preview_orchestrator_e2e/SCOPE.md`, the entry point for scanning must support `main.py --mode scan` and output results to a SQLite database.
- **Testing Constraints**:
  - The project operates in `CODE_ONLY` network mode (no external internet). All E2E tests (run via `pytest tests/e2e/`) must execute fully offline using mock servers and isolated SQLite databases.

---

## 2. Logic Chain
1. **Source File Creation**: Since no code currently exists in `automation/` (Observation 1), the directory structure and code modules must be created from scratch by the implementer.
2. **Dependency Management**: Since standard libraries like `pandas` and `alpaca-py` are missing (Observation 2) and the environment is offline (Observation 4), a `requirements.txt` listing necessary libraries is required, and the implementer must ensure these dependencies are installed (e.g., using local wheels or package caches).
3. **Mocking & Config-driven Client**: Since network access is restricted to offline testing (Observation 4), the `MarketDataClient` in `data_client.py` and scanner in `scanner.py` must accept base URL configuration overrides (e.g. `ALPACA_API_BASE_URL` and `ALPACA_DATA_STREAM_URL`). During E2E tests, these will point to local mock servers instead of the production Alpaca endpoints.
4. **Self-Contained Indicators**: Since external technical analysis libraries like `pandas_ta` or `ta` are missing (Observation 2), the best strategy is to compute the indicators directly in `indicators.py` using native `pandas` and `numpy` methods. This reduces dependencies and avoids compatibility issues.
5. **Multi-ticker Support**: The contract requires `calculate_indicators` to take a DataFrame (Observation 3). Since a dataframe can represent a single ticker or multiple tickers (e.g., grouped by column or index), the function must detect the structure (checking for a `ticker` or `symbol` column/index level) and apply calculations on a per-ticker group basis.
6. **Pre-market Data Filtering**: To compute pre-market gap percentages and volume before 9:30 AM EST (Observation 3), the scanner must separate regular market data from pre-market bars (defined as 4:00 AM to 9:30 AM EST).
7. **Database Storage**: The scanner CLI must save selected tickers to a SQLite database (Observation 3). To support multiple days of trading history, the table should use a composite primary key of `(ticker, scan_date)`.

---

## 3. Caveats
- **Alpaca Feed Limitations**: The default IEX feed (free) only contains trades executed on IEX, which are thin in pre-market. For production, the client should support the SIP feed if a pro/paid API key is available.
- **Pre-market yfinance Reliability**: yfinance pre-market data can be erratic or delayed. We recommend using Alpaca's historical REST API as the primary pre-market source and yfinance only as a fallback.
- **Phased News Integration**: FinBERT sentiment analysis is scheduled for Milestone 2. For Milestone 1, the scanner's news catalyst check will use a simple keyword search ("earnings", "upgrade", etc.) on headlines retrieved via yfinance's `.news` attribute.
- **Offline Library Installation**: Because we are in `CODE_ONLY` mode, we assume the environment or testing runner has pre-provisioned python packages or will run under a pre-installed test image containing `pandas`, `yfinance`, and `alpaca-py`.

---

## 4. Conclusion
We recommend the following technical designs for Milestone 1:

### A. Technical Indicator Module (`automation/indicators.py`)
- Implement indicators in pure `pandas`/`numpy`:
  - **VWAP**: Cumulative `(typical_price * volume) / volume` resetting daily (grouped by the date part of the timestamp). Typical Price is `(high + low + close) / 3`.
  - **MACD**: EMA(12) - EMA(26) of close, signal line is EMA(9) of MACD, histogram is the difference.
  - **RSI**: 14-period Wilder's smoothing. Handle division by zero.
  - **Bollinger Bands**: 20-period simple moving average and 2 standard deviations.
  - **EMA Crossover**: 9-period and 21-period EMAs. The crossover signal must output `1` for bullish (fast crosses above slow), `-1` for bearish (fast crosses below slow), and `0` otherwise.
  - **RVOL**: Current bar volume divided by the 20-period moving average of volume.
- Grouping logic: Automatically check if the input DataFrame has a `ticker` or `symbol` column or level, and apply calculation per ticker group.

### B. Market Data Ingestion Client (`automation/data_client.py`)
- Implement a `MarketDataClient` class:
  - **Asynchronous Ingestion**: Connect to Alpaca's `StockDataStream` using `alpaca-py`.
  - **Historical Seeding**: On startup, fetch the last 100 1-minute bars using Alpaca REST `StockHistoricalDataClient` to prime the technical indicators, falling back to yfinance `yf.download(period="2d", interval="1m")`.
  - **Thread-safe Buffer**: Cache a sliding window of recent bars (e.g., max 200) in memory.
  - **Fallback Polling**: If WebSocket fails, start a background task polling yfinance every 60 seconds.
  - **Configurability**: Expose overrides for API Base URLs and WebSocket stream URLs.

### C. Pre-market Scanner Module (`automation/scanner.py`)
- Implement a scanner that runs before 9:30 AM EST:
  - Fetch previous day's close (filtering out today's date) and today's pre-market bars (4:00 AM - 9:30 AM EST).
  - Calculate `gap_percentage = (last_premarket_close - previous_close) / previous_close * 100` and pre-market volume (sum of pre-market bar volumes).
  - Check `yf.Ticker(symbol).news` for keyword catalysts.
  - Save results to SQLite database `watchlist` table:
    ```sql
    CREATE TABLE IF NOT EXISTS watchlist (
        ticker TEXT NOT NULL,
        scan_date TEXT NOT NULL,
        previous_close REAL NOT NULL,
        premarket_price REAL NOT NULL,
        gap_percentage REAL NOT NULL,
        premarket_volume INTEGER NOT NULL,
        sentiment_score REAL DEFAULT 0.0,
        catalyst_info TEXT,
        PRIMARY KEY (ticker, scan_date)
    );
    ```
  - Provide a CLI entry point: `main.py --mode scan` that reads a watch universe (e.g. config file/list), runs the scan, writes top candidates to the database, and exits.

---

## 5. Verification Method
- **Unit Tests**:
  - Test indicators by mocking a pandas DataFrame with known values (e.g., constant prices, simple crossover points) and asserting computed values match calculations.
  - Command: `pytest tests/unit/test_indicators.py`
- **E2E Tests**:
  - Run the test suite offline using the mock servers and check if the scanner CLI outputs selected tickers to the SQLite database.
  - Command: `pytest tests/e2e/test_tier1_feature_coverage.py -k test_scan`
- **Database Inspection**:
  - Run command to inspect results in the database:
    `sqlite3 trading.db "SELECT * FROM watchlist;"`
- **Invalidation Conditions**:
  - If indicator computations return `NaN` during active trading periods, or if the scanner fails to isolate the pre-market session (4:00 AM - 9:30 AM EST), or if the database table lacks the `scan_date` column/composite key, the implementation fails verification.
