# Milestone 1 Investigation & Implementation Strategy Report

This report presents findings and technical recommendations for implementing Milestone 1 (Market Data & Technical Indicators) of the Autonomous AI Day-Trading Bot.

---

## 1. Observation

During our codebase inspection, we made the following direct observations:

1. **Workspace Layout**:
   - The workspace root directory `/home/mint/Desktop/ai-trading-bot` contains only metadata and default project files:
     ```json
     {"name":".agents","isDir":true}
     {"name":".git","isDir":true}
     {"name":"LICENSE","sizeBytes":"1063"}
     {"name":"README.md","sizeBytes":"33"}
     ```
     No source code directory or files (e.g. `automation/`) currently exist in the repository root.

2. **Environment & Package Availability**:
   - Running `pip list` in the workspace indicates that critical libraries required for real-time market data ingestion and technical indicators (namely `pandas`, `yfinance`, and `alpaca-py`) are not present in the global Python environment.
   - Specifically, running:
     ```bash
     python3 -c "import pandas; import yfinance; import alpaca"
     ```
     resulted in:
     ```
     ModuleNotFoundError: No module named 'pandas'
     ```

3. **Interface Contracts (from PROJECT.md and SCOPE.md)**:
   - **`automation/indicators.py`**:
     - Contract: `def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame`
     - Inputs: `data` DataFrame containing columns: `open`, `high`, `low`, `close`, `volume`, and optionally `timestamp` or DatetimeIndex.
     - Required Outputs: The same DataFrame with the following columns added:
       - `vwap`: Volume Weighted Average Price.
       - `macd`, `macd_signal`, `macd_hist`: MACD components.
       - `rsi`: Relative Strength Index (typically 14-period).
       - `bb_upper`, `bb_middle`, `bb_lower`: Bollinger Bands (20-period, 2 std dev).
       - `ema_fast`, `ema_slow`, `ema_crossover`: EMA components (9-period, 21-period, and crossover state: `1` for bullish, `-1` for bearish, `0` otherwise).
       - `rvol`: Relative Volume (volume relative to a 20-period baseline).
   - **`automation/data_client.py`**:
     - Connect to Alpaca WebSocket stream or fall back to yfinance polling.
     - Maintain and expose buffers of OHLCV bars.
   - **`automation/scanner.py`**:
     - Scans before 9:30 AM EST.
     - Identifies watchlist stocks based on gap percentage, pre-market volume, and news catalysts.

---

## 2. Logic Chain

To transition from these observations to an implementation plan:

1. **Package Setup**:
   - Since `pandas`, `yfinance`, `alpaca-py`, and `pytz` are not installed (Observation 2), the implementer must first install these dependencies (e.g., via a `requirements.txt` or setting up a Python virtual environment).
2. **Directory Structure**:
   - Since the repository root is empty of code (Observation 1), the implementer needs to create the `automation/` directory.
3. **Indicator Calculation Logic**:
   - We must design standard vectorized pandas calculations for each of the indicators to satisfy the interface contract.
   - **VWAP**: If intraday timestamp data is present, it must reset daily to prevent accumulation drift. Otherwise, it should calculate a cumulative/rolling representation across the entire dataset.
   - **MACD**: EMA(12) - EMA(26) for the line, EMA(9) of the line for the signal, and their difference for the histogram.
   - **RSI**: 14-period using Wilder's smoothing method.
   - **Bollinger Bands**: 20-period SMA and standard deviation with $\pm 2$ std dev lines.
   - **EMA Crossovers**: 9-period and 21-period EMAs. The crossover signal must be transient (`1` or `-1` only on the crossover bar, `0` elsewhere) to prevent multiple execution signals.
   - **RVOL**: Current volume divided by a 20-period rolling average volume.
4. **Data Client Architecture**:
   - The data client needs to operate asynchronously or in a background thread to prevent blocking main execution.
   - It needs thread-safe locks (`threading.Lock`) since the background thread adds data to the buffers while the decision engine reads it.
   - Real-time WebSockets can be unstable, so the client must handle reconnects and fall back gracefully to yfinance polling.
5. **Scanner Scheduling**:
   - Pre-market scanner must run in the US/Eastern timezone to align with the 9:30 AM EST market open.
   - It should calculate gap percentage against the previous day's regular market close and fetch news catalyst metrics (e.g., from Alpaca News API or yfinance feeds).

---

## 3. Caveats

1. **Network Limits in Sandbox**:
   - Since the sandbox operates in `CODE_ONLY` network mode, live network fetches will fail during development/unit testing. Mocking tools or offline data feeds (e.g., cached JSON/CSV files) must be provided in the test suites.
2. **Missing News Catalysts In M1**:
   - The news sentiment module is slated for Milestone 2. For Milestone 1, the scanner should fall back to basic headline counts via public RSS feeds or Alpaca news, or use mock news scores.
3. **Tickers Selection**:
   - The scanner needs a configured list of high-liquidity candidate tickers to scan, as querying the entire market in real-time is not feasible.

---

## 4. Conclusion & Implementation Designs

We recommend creating the `automation/` package containing the three modules designed below.

### Design A: `automation/indicators.py`
This module computes the six technical indicators using pandas in a vectorized manner, handling edge cases such as empty data and dividing by zero.

```python
import pandas as pd
import numpy as np

def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """
    Computes technical indicators on a per-ticker price history.
    
    Required Columns in data:
      - open, high, low, close, volume
      - Optionally: timestamp (or DatetimeIndex)
    """
    if data.empty:
        res = data.copy()
        new_cols = [
            'vwap', 'macd', 'macd_signal', 'macd_hist', 'rsi',
            'bb_upper', 'bb_middle', 'bb_lower',
            'ema_fast', 'ema_slow', 'ema_crossover', 'rvol'
        ]
        for col in new_cols:
            res[col] = pd.Series(dtype=np.float64)
        return res
        
    required = ['open', 'high', 'low', 'close', 'volume']
    for col in required:
        if col not in data.columns:
            raise ValueError(f"Missing required column: '{col}'")
            
    df = data.copy()
    
    # Ensure numeric types
    for col in required:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    # --- 1. VWAP (Volume Weighted Average Price) ---
    timestamps = None
    if isinstance(df.index, pd.DatetimeIndex):
        timestamps = df.index
    elif 'timestamp' in df.columns:
        timestamps = pd.to_datetime(df['timestamp'])
        
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    vol_typical = typical_price * df['volume']
    
    if timestamps is not None:
        dates = timestamps.date
        cum_vol_price = vol_typical.groupby(dates).cumsum()
        cum_vol = df['volume'].groupby(dates).cumsum()
        df['vwap'] = cum_vol_price / cum_vol.replace(0, np.nan)
        df['vwap'] = df['vwap'].fillna(typical_price)
    else:
        cum_vol_price = vol_typical.cumsum()
        cum_vol = df['volume'].cumsum()
        df['vwap'] = cum_vol_price / cum_vol.replace(0, np.nan)
        df['vwap'] = df['vwap'].fillna(typical_price)
        
    # --- 2. MACD ---
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # --- 3. RSI ---
    delta = df['close'].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    
    avg_gain = gain.ewm(alpha=1.0/14.0, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0/14.0, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    df['rsi'] = 100.0 - (100.0 / (1.0 + rs))
    df['rsi'] = df['rsi'].fillna(50.0)
    
    # --- 4. Bollinger Bands (20-period, 2 std dev) ---
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + 2.0 * bb_std
    df['bb_lower'] = df['bb_middle'] - 2.0 * bb_std
    
    # --- 5. EMA Crossovers (9-period vs 21-period) ---
    df['ema_fast'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=21, adjust=False).mean()
    
    fast_above = df['ema_fast'] > df['ema_slow']
    prev_fast_above = df['ema_fast'].shift(1) > df['ema_slow'].shift(1)
    
    df['ema_crossover'] = 0
    df.loc[fast_above & ~prev_fast_above & df['ema_fast'].notna() & df['ema_fast'].shift(1).notna(), 'ema_crossover'] = 1
    df.loc[~fast_above & prev_fast_above & df['ema_fast'].notna() & df['ema_fast'].shift(1).notna(), 'ema_crossover'] = -1
    
    # --- 6. Relative Volume (RVOL) ---
    vol_mean = df['volume'].rolling(window=20).mean()
    df['rvol'] = df['volume'] / vol_mean.replace(0.0, np.nan)
    df['rvol'] = df['rvol'].fillna(1.0)
    
    return df
```

### Design B: `automation/data_client.py`
A dual-feed architecture that manages connections, handles historical pre-population, and maintains a thread-safe data buffer.

```python
import threading
import time
import pandas as pd
import logging
from typing import Dict, List, Optional
import yfinance as yf

try:
    from alpaca.data.live import StockDataStream
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
except ImportError:
    StockDataStream = None
    StockHistoricalDataClient = None

logger = logging.getLogger(__name__)

class MarketDataClient:
    def __init__(self, api_key: str = "", secret_key: str = "", paper: bool = True, feed: str = "iex", use_yfinance: bool = False):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.feed = feed
        self.use_yfinance = use_yfinance or not (api_key and secret_key)
        
        self.buffers: Dict[str, pd.DataFrame] = {}
        self.lock = threading.Lock()
        self.tickers: List[str] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stream: Optional[StockDataStream] = None

    def start(self, tickers: List[str]):
        self.tickers = list(set(tickers))
        self._running = True
        self._prepopulate_history()
        
        if self.use_yfinance:
            self._thread = threading.Thread(target=self._yfinance_polling_loop, daemon=True)
        else:
            self._thread = threading.Thread(target=self._alpaca_streaming_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        # Thread cleanup logic here

    def get_latest_data(self, ticker: str, limit: int = 100) -> pd.DataFrame:
        with self.lock:
            df = self.buffers.get(ticker)
            if df is None or df.empty:
                return pd.DataFrame()
            return df.tail(limit)

    def _prepopulate_history(self):
        with self.lock:
            for ticker in self.tickers:
                try:
                    df = yf.download(ticker, period="5d", interval="1m")
                    if not df.empty:
                        df = df.rename(columns={
                            'Open': 'open', 'High': 'high', 'Low': 'low',
                            'Close': 'close', 'Volume': 'volume'
                        })
                        df.index.name = 'timestamp'
                        self.buffers[ticker] = df[['open', 'high', 'low', 'close', 'volume']]
                except Exception as e:
                    logger.error(f"Failed to prepopulate {ticker}: {e}")

    def _yfinance_polling_loop(self):
        while self._running:
            try:
                for ticker in self.tickers:
                    df_new = yf.download(ticker, period="1d", interval="1m").tail(5)
                    df_new = df_new.rename(columns={
                        'Open': 'open', 'High': 'high', 'Low': 'low',
                        'Close': 'close', 'Volume': 'volume'
                    })
                    df_new.index.name = 'timestamp'
                    
                    with self.lock:
                        if ticker in self.buffers:
                            combined = pd.concat([self.buffers[ticker], df_new])
                            self.buffers[ticker] = combined[~combined.index.duplicated(keep='last')].sort_index()
                        else:
                            self.buffers[ticker] = df_new[['open', 'high', 'low', 'close', 'volume']]
                time.sleep(60)
            except Exception as e:
                logger.error(f"Yfinance polling error: {e}")
                time.sleep(10)

    def _alpaca_streaming_loop(self):
        if StockDataStream is None:
            self.use_yfinance = True
            self._yfinance_polling_loop()
            return
            
        try:
            self._stream = StockDataStream(
                api_key=self.api_key,
                secret_key=self.secret_key,
                raw_data=True,
                url_override="wss://stream.data.alpaca.markets/v2/" + self.feed
            )
            
            async def handle_bar(data):
                symbol = data.get('S')
                if not symbol:
                    return
                bar_time = pd.to_datetime(data.get('t'))
                new_row = pd.DataFrame({
                    'open': [data.get('o')],
                    'high': [data.get('h')],
                    'low': [data.get('l')],
                    'close': [data.get('c')],
                    'volume': [data.get('v')]
                }, index=[bar_time])
                new_row.index.name = 'timestamp'
                
                with self.lock:
                    if symbol in self.buffers:
                        combined = pd.concat([self.buffers[symbol], new_row])
                        self.buffers[symbol] = combined[~combined.index.duplicated(keep='last')].sort_index()
                    else:
                        self.buffers[symbol] = new_row
            
            self._stream.subscribe_bars(handle_bar, *self.tickers)
            self._stream.run()
        except Exception as e:
            logger.error(f"Alpaca streaming error: {e}")
            time.sleep(10)
```

### Design C: `automation/scanner.py`
The pre-market scanner filters candidates using pre-market hours criteria, ranking by a combination of gaps, volume, and news headlines.

```python
import datetime
import pytz
import pandas as pd
import json
import logging
from typing import List, Dict, Any
import yfinance as yf

logger = logging.getLogger(__name__)

class PreMarketScanner:
    def __init__(self, api_key: str = "", secret_key: str = "", candidates: List[str] = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.candidates = candidates or ["AAPL", "MSFT", "TSLA", "NVDA", "AMD"]

    def scan(self) -> List[Dict[str, Any]]:
        results = []
        est = pytz.timezone('US/Eastern')
        
        for ticker in self.candidates:
            try:
                stock = yf.Ticker(ticker)
                history = stock.history(period="2d")
                if len(history) < 2:
                    continue
                prev_close = history['Close'].iloc[-2]
                
                pm_data = stock.history(period="1d", interval="1m", prepost=True)
                if pm_data.empty:
                    continue
                
                # Filter to only include pre-market hours
                pm_bars = pm_data[pm_data.index.tz_convert(est).time < datetime.time(9, 30)]
                premarket_price = pm_bars['Close'].iloc[-1] if not pm_bars.empty else pm_data['Close'].iloc[-1]
                premarket_volume = pm_bars['Volume'].sum() if not pm_bars.empty else pm_data['Volume'].sum()
                
                gap_pct = ((premarket_price - prev_close) / prev_close) * 100.0
                news_count = len(stock.news) if stock.news else 0
                
                # Score formula
                score = abs(gap_pct) * 2.0 + (premarket_volume / 100000.0) * 1.5 + (news_count * 3.0)
                
                results.append({
                    'ticker': ticker,
                    'prev_close': prev_close,
                    'premarket_price': premarket_price,
                    'gap_pct': gap_pct,
                    'premarket_volume': premarket_volume,
                    'news_catalysts': news_count,
                    'score': score
                })
            except Exception as e:
                logger.error(f"Scan failed for {ticker}: {e}")
                
        results.sort(key=lambda x: x['score'], reverse=True)
        return results

    def save_watchlist(self, filepath: str = "watchlist.json"):
        top_list = self.scan()[:10]
        with open(filepath, "w") as f:
            json.dump(top_list, f, indent=4)
        logger.info(f"Watchlist saved to {filepath}")
```

---

## 5. Verification Method

To independently verify the technical correctness of the proposed implementation:

1. **Unit Testing Strategy**:
   - Write offline tests using fixed datasets (CSV format) to verify that `calculate_indicators` computes the correct values for VWAP, MACD, RSI, Bollinger Bands, EMA Crossovers, and RVOL.
   - For `data_client.py` and `scanner.py`, use unittest mocking (`unittest.mock.patch` or `pytest-mock`) to mock Alpaca connections and `yfinance` methods (`yf.download` / `yf.Ticker`). This is required because of the sandbox's network limits.

2. **Verification Commands**:
   - Install dependencies and run the unit tests:
     ```bash
     pip install pandas numpy yfinance pytz pytest pytest-mock
     pytest tests/test_indicators.py tests/test_data_client.py tests/test_scanner.py
     ```

3. **Invalidation Conditions**:
   - If any test output does not match expected indicators calculated by standard financial libraries (e.g., `ta` or `pandas-ta`), or if WebSocket disconnection causes client crashes, the implementation is invalid.
