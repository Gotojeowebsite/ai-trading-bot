# Synthesis of Milestone 1 Technical Designs

## 1. Consensus & Conclusion
We will build the core automation components for Milestone 1 inside the `automation/` package:
- `automation/indicators.py`: Vectorized technical indicators calculated using pandas/numpy (VWAP, MACD, RSI, Bollinger Bands, EMA crossover, RVOL).
- `automation/data_client.py`: Thread-safe market data client using Alpaca StockDataStream or yfinance polling.
- `automation/scanner.py`: Pre-market scanner filtering stocks before 9:30 AM EST and saving candidates to a SQLite database.

## 2. Resolved Implementation Architecture
### A. Technical Indicators (`automation/indicators.py`)
- Standardized columns: `open`, `high`, `low`, `close`, `volume`.
- **VWAP**: Daily-resetting cumulative typical price-volume product divided by volume:
  $$VWAP = \frac{\sum (TypicalPrice \times Volume)}{\sum Volume}$$
  where $TypicalPrice = \frac{High + Low + Close}{3}$.
- **MACD**: EMA(12) - EMA(26), signal line is EMA(9) of MACD, histogram is the difference.
- **RSI**: 14-period using Wilder's smoothed method.
- **Bollinger Bands**: 20-period SMA and standard deviation, upper/lower bands at 2 standard deviations.
- **EMA Crossover**: 9-period and 21-period EMAs. Returns `1` for bullish (fast crosses above slow), `-1` for bearish (fast crosses below slow), `0` otherwise.
- **RVOL**: Current bar volume divided by the rolling 20-period average of volume.

### B. Live Market Data Ingestion Client (`automation/data_client.py`)
- Background thread or async loop streaming Alpaca websocket bars using `StockDataStream` (handling paper/live environments).
- Fallback loop polling `yfinance.download()` every 60 seconds.
- Internal thread-safe cache (`threading.Lock`) of sliding windows of historical 1-minute bars.
- API base url/websocket url config options to support offline mock E2E testing.

### C. Pre-market Scanner (`automation/scanner.py`)
- Runs daily before 9:30 AM EST.
- Fetches previous day's close and today's pre-market data.
- Filters and ranks by gap % and pre-market volume.
- Saves watchlists to a SQLite database under `watchlist` table with composite key `(ticker, scan_date)`.
- CLI interface supporting execution.

## 3. Dependency Requirements
Create a `requirements.txt` in project root with:
```
pandas
numpy
yfinance
alpaca-py
pytz
pytest
pytest-mock
```
and ensure the Worker installs them.

## 4. Verification Methods
- Offline unit tests in `tests/unit/test_indicators.py` verifying mathematical correctness of indicators.
- Mock-driven functional tests for the market data client and pre-market scanner in `tests/unit/` or `tests/e2e/`.
