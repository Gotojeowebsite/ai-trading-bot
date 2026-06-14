# Handoff Report - Milestone 1 Technical Implementation Strategy

## 1. Observation
The following observations were made during the read-only investigation:
1. **Workspace Files**: Run of `list_dir` on `/home/mint/Desktop/ai-trading-bot` returned only:
   - `.agents/` (agent directories)
   - `.git/` (git repository metadata)
   - `LICENSE`
   - `README.md`
   No source directories (such as `automation/`) or Python files currently exist in the root of the workspace.
2. **Project Contract Specifications**: In `/home/mint/Desktop/ai-trading-bot/.agents/orchestrator/PROJECT.md` lines 37-38:
   ```python
   def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame
   ```
   "Computes VWAP, RSI, MACD, Bollinger Bands, EMA, and RVOL on raw OHLCV price histories."
3. **Indicator Output Column Details**: In `/home/mint/Desktop/ai-trading-bot/.agents/teamwork_preview_orchestrator_m1/SCOPE.md` lines 15-24, the expected output columns and definitions are specified:
   - `vwap`: Volume Weighted Average Price.
   - `macd`, `macd_signal`, `macd_hist`: MACD components.
   - `rsi`: Relative Strength Index.
   - `bb_upper`, `bb_middle`, `bb_lower`: Bollinger Bands (20-period, 2 std dev).
   - `ema_fast`, `ema_slow`, `ema_crossover`: EMA components (9 and 21-period EMAs, and crossover signals: 1 for bullish, -1 for bearish, 0 otherwise).
   - `rvol`: Relative Volume (compared to average volume over 20 periods).
4. **Environment Check**:
   - Running `python3 --version` returned `Python 3.12.3`.
   - Running `pip list` and `python3 -m pip list --user` confirmed standard system packages are present (such as `websockets 10.4` and `requests 2.31.0`), but critical domain libraries `pandas`, `yfinance`, and `alpaca-py` are **not** installed.

---

## 2. Logic Chain
1. Based on Observation 4, the environment lacks `pandas`, `yfinance`, and `alpaca-py`. Thus, the first step for the implementation phase must be to install these packages (preferably via a standard `requirements.txt` or a setup script) so the codebase can compile and execute.
2. Based on Observation 1, the folder structure `automation/` needs to be created. It must house `data_client.py`, `indicators.py`, and `scanner.py` as defined by the SCOPE.md layout.
3. Based on Observation 2, `calculate_indicators` must receive a pandas DataFrame and return a pandas DataFrame. To ensure performance and prevent runtime performance bottlenecks, the calculations should be vectorized using pandas and NumPy, and should handle input column case-insensitivity.
4. To meet the requirements of `data_client.py` (Observation 3 & SCOPE.md), the client must manage a real-time stream using Alpaca WebSocket with proper fallback. Since streaming updates can be sparse or only arrive minute-by-minute, a bootstrap mechanism is required on startup to query historical bars (using Alpaca Historical API or yfinance) and populate the local cache. This guarantees that indicators requiring historical periods (e.g. 20-period Bollinger Bands or 21-period EMA) have sufficient history to be computed immediately upon client startup.
5. For the pre-market scanner (`scanner.py`), the pre-market session (4:00 AM - 9:30 AM EST) needs timezone-aware comparison. The scanner must download pre-market data (using `yfinance` with `prepost=True` or Alpaca historical endpoints), filter by start times, aggregate pre-market volume, calculate gap percentages from the previous regular close, and fetch recent news headlines from Yahoo Finance to check for catalyst keywords before the market open.

---

## 3. Caveats
- **Alpaca Data Feed Limitations**: The free tier Alpaca data feed (IEX) has lower volume and coverage than standard SIP feeds. The scanner might show discrepancy in pre-market volume if using Alpaca IEX vs yfinance. Utilizing yfinance as the primary data fetcher for the scanner is recommended for better coverage.
- **News Catalysts**: The news scanner in Milestone 1 is implemented using keyword detection on RSS/yfinance news headlines, as the FinBERT sentiment module is scheduled for Milestone 2.
- **Memory Consumption**: If the `MarketDataClient` runs indefinitely, its local bar cache will grow. The design must cap the cache size per ticker (e.g., to the last 500 bars) to prevent memory leaks.

---

## 4. Conclusion & Proposed Designs

### Proposed Design: `automation/indicators.py`
This module computes technical indicators. It handles case-insensitive columns, uses vectorized formulas, and is fully robust against empty or short DataFrames.

```python
import pandas as pd
import numpy as np

def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """
    Computes technical indicators on raw OHLCV price histories.
    
    Inputs:
        data: pd.DataFrame with columns: open, high, low, close, volume (case-insensitive)
        
    Outputs:
        pd.DataFrame with original columns and additional columns:
        vwap, macd, macd_signal, macd_hist, rsi, bb_upper, bb_middle, bb_lower,
        ema_fast, ema_slow, ema_crossover, rvol
    """
    if data.empty:
        # Return empty DataFrame with expected structure if input is empty
        empty_df = data.copy()
        for col in ['vwap', 'macd', 'macd_signal', 'macd_hist', 'rsi', 
                    'bb_upper', 'bb_middle', 'bb_lower', 'ema_fast', 
                    'ema_slow', 'ema_crossover', 'rvol']:
            empty_df[col] = pd.Series(dtype='float64')
        return empty_df

    df = data.copy()
    
    # Standardize column mapping for case-insensitivity
    cols = {col.lower(): col for col in df.columns}
    required = ['open', 'high', 'low', 'close', 'volume']
    for req in required:
        if req not in cols:
            raise ValueError(f"Required column '{req}' (case-insensitive) missing from input data.")
            
    o = df[cols['open']]
    h = df[cols['high']]
    l = df[cols['low']]
    c = df[cols['close']]
    v = df[cols['volume']]
    
    # 1. VWAP (Volume Weighted Average Price)
    # Group by date if index is DatetimeIndex, otherwise fallback to global cumsum
    typical_price = (h + l + c) / 3
    tp_v = typical_price * v
    
    if isinstance(df.index, pd.DatetimeIndex):
        group = df.index.date
        df['vwap'] = tp_v.groupby(group).cumsum() / v.groupby(group).cumsum().replace(0, 1e-9)
    elif 'timestamp' in cols:
        timestamps = pd.to_datetime(df[cols['timestamp']])
        group = timestamps.dt.date
        df['vwap'] = tp_v.groupby(group).cumsum() / v.groupby(group).cumsum().replace(0, 1e-9)
    else:
        df['vwap'] = tp_v.cumsum() / v.cumsum().replace(0, 1e-9)
    df['vwap'] = df['vwap'].ffill().fillna(typical_price)
    
    # 2. MACD (Moving Average Convergence Divergence)
    ema_12 = c.ewm(span=12, adjust=False).mean()
    ema_26 = c.ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # 3. RSI (Relative Strength Index - 14-period Wilder's Smoothing)
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    df['rsi'] = rsi.where(avg_gain + avg_loss > 0, 50.0)
    
    # 4. Bollinger Bands (20-period, 2 std dev)
    df['bb_middle'] = c.rolling(window=20, min_periods=1).mean()
    bb_std = c.rolling(window=20, min_periods=1).std(ddof=0)
    df['bb_upper'] = df['bb_middle'] + 2 * bb_std
    df['bb_lower'] = df['bb_middle'] - 2 * bb_std
    
    # 5. EMA Crossovers (9-period fast, 21-period slow)
    df['ema_fast'] = c.ewm(span=9, adjust=False).mean()
    df['ema_slow'] = c.ewm(span=21, adjust=False).mean()
    
    diff = df['ema_fast'] - df['ema_slow']
    prev_diff = diff.shift(1)
    
    bullish = (diff > 0) & (prev_diff <= 0)
    bearish = (diff < 0) & (prev_diff >= 0)
    
    df['ema_crossover'] = 0
    df.loc[bullish, 'ema_crossover'] = 1
    df.loc[bearish, 'ema_crossover'] = -1
    
    # 6. RVOL (Relative Volume - 20-period baseline)
    avg_volume = v.rolling(window=20, min_periods=1).mean()
    df['rvol'] = v / avg_volume.replace(0, 1e-9)
    
    return df
```

### Proposed Design: `automation/data_client.py`
This client connects to Alpaca WebSockets, stores real-time updates in a thread-safe local cache, supports bootstrap querying on startup, and provides a polling fallback via yfinance.

```python
import asyncio
import logging
import threading
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf
from alpaca.data.live.stock import StockDataStream
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MarketDataClient:
    def __init__(self, api_key: str, secret_key: str, paper: bool = True, watchlist: List[str] = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.watchlist = watchlist or []
        
        self.data_store: Dict[str, pd.DataFrame] = {}
        self.lock = threading.Lock()
        self.is_running = False
        
        self._thread = None
        self._loop = None
        self.stream = None
        
        self.historical_client = StockHistoricalDataClient(api_key, secret_key)
        
    def bootstrap_history(self, limit: int = 100):
        """Fetches historical bars to populate cache before streaming starts."""
        logger.info("Bootstrapping historical data...")
        start_time = datetime.now() - timedelta(days=5)
        
        for ticker in self.watchlist:
            try:
                request = StockBarsRequest(
                    symbol_or_symbols=ticker,
                    timeframe=TimeFrame.Minute,
                    start=start_time
                )
                bars = self.historical_client.get_stock_bars(request)
                df = bars.df
                if not df.empty:
                    # Reset multi-index if returned by Alpaca
                    if isinstance(df.index, pd.MultiIndex):
                        df = df.xs(ticker, level=0)
                    
                    # Normalize column casing
                    df = df.rename(columns={col: col.lower() for col in df.columns})
                    with self.lock:
                        self.data_store[ticker] = df.tail(limit)
                logger.info(f"Successfully bootstrapped {ticker}")
            except Exception as e:
                logger.warning(f"Failed to bootstrap {ticker} via Alpaca: {e}. Trying yfinance fallback.")
                try:
                    df = yf.Ticker(ticker).history(period="5d", interval="1m")
                    if not df.empty:
                        df = df.rename(columns={col: col.lower() for col in df.columns})
                        with self.lock:
                            self.data_store[ticker] = df.tail(limit)
                except Exception as yf_err:
                    logger.error(f"Fallback bootstrap failed for {ticker}: {yf_err}")

    def start(self):
        """Starts stream in background."""
        self.is_running = True
        self.bootstrap_history()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        url = "wss://data.alpaca.markets/v2/iex"
        self.stream = StockDataStream(self.api_key, self.secret_key, url=url)
        
        async def bar_handler(bar):
            ticker = bar.symbol
            new_row = pd.DataFrame([{
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            }], index=[pd.to_datetime(bar.timestamp)])
            
            with self.lock:
                if ticker not in self.data_store or self.data_store[ticker].empty:
                    self.data_store[ticker] = new_row
                else:
                    self.data_store[ticker] = pd.concat([self.data_store[ticker], new_row])
                    # Cap size to prevent memory leaks
                    if len(self.data_store[ticker]) > 1000:
                        self.data_store[ticker] = self.data_store[ticker].iloc[-1000:]
                        
        for ticker in self.watchlist:
            self.stream.subscribe_bars(bar_handler, ticker)
            
        try:
            self._loop.run_until_complete(self.stream._run())
        except Exception as e:
            logger.error(f"WebSocket stream disconnected: {e}. Launching yfinance polling backup.")
            self._start_yfinance_polling()
            
    def _start_yfinance_polling(self):
        """Fallback polling loop using yfinance."""
        def poll():
            while self.is_running:
                for ticker in self.watchlist:
                    try:
                        df = yf.Ticker(ticker).history(period="1d", interval="1m")
                        if not df.empty:
                            df = df.rename(columns={col: col.lower() for col in df.columns})
                            with self.lock:
                                self.data_store[ticker] = df
                    except Exception as ex:
                        logger.error(f"yfinance polling error for {ticker}: {ex}")
                import time
                time.sleep(60)
        
        threading.Thread(target=poll, daemon=True).start()

    def get_latest_data(self, ticker: str) -> pd.DataFrame:
        """Returns the cached price DataFrame for a ticker."""
        with self.lock:
            return self.data_store.get(ticker, pd.DataFrame()).copy()
```

### Proposed Design: `automation/scanner.py`
This scanner runs daily prior to 9:30 AM EST, aggregates pre-market transactions using yfinance prepost parameters, filters tickers based on gap and volume thresholds, and aggregates potential news catalysts.

```python
import pytz
from datetime import datetime, time
import pandas as pd
import yfinance as yf
from typing import List, Dict, Any

class PreMarketScanner:
    def __init__(self, tickers: List[str], min_volume: int = 20000, min_gap_pct: float = 1.5):
        self.tickers = tickers
        self.min_volume = min_volume
        self.min_gap_pct = min_gap_pct
        
    def is_premarket_hours(self) -> bool:
        """Determines if current local time falls inside 4:00 AM - 9:30 AM EST."""
        tz = pytz.timezone('US/Eastern')
        now_est = datetime.now(tz)
        if now_est.weekday() > 4:  # Weekend check
            return False
        return time(4, 0) <= now_est.time() < time(9, 30)
        
    def scan(self, force: bool = False) -> pd.DataFrame:
        """
        Scanswatchlist during pre-market.
        """
        if not force and not self.is_premarket_hours():
            logger.warning("Attempted to run scanner outside pre-market hours.")
            return pd.DataFrame()
            
        results = []
        for ticker in self.tickers:
            try:
                ticker_obj = yf.Ticker(ticker)
                
                # Fetch daily data for previous session close
                daily_hist = ticker_obj.history(period="5d", interval="1d")
                if len(daily_hist) < 2:
                    continue
                prev_close = daily_hist['Close'].iloc[-2]
                
                # Fetch intraday data with extended hours (pre-market and after-hours)
                intraday_hist = ticker_obj.history(period="1d", interval="1m", prepost=True)
                if intraday_hist.empty:
                    continue
                
                if intraday_hist.index.tz is None:
                    intraday_hist.index = intraday_hist.index.tz_localize('UTC')
                intraday_est = intraday_hist.index.tz_convert('US/Eastern')
                
                # Filter for today's pre-market window
                today = datetime.now(pytz.timezone('US/Eastern')).date()
                mask = (
                    (intraday_est.date == today) &
                    (intraday_est.time >= time(4, 0)) &
                    (intraday_est.time < time(9, 30))
                )
                premarket_bars = intraday_hist[mask]
                
                if premarket_bars.empty:
                    continue
                    
                pre_market_price = premarket_bars['Close'].iloc[-1]
                pre_market_vol = premarket_bars['Volume'].sum()
                
                gap_pct = ((pre_market_price - prev_close) / prev_close) * 100
                
                if pre_market_vol >= self.min_volume and abs(gap_pct) >= self.min_gap_pct:
                    catalysts = self._fetch_catalysts(ticker_obj)
                    results.append({
                        'ticker': ticker,
                        'prev_close': prev_close,
                        'pre_market_price': pre_market_price,
                        'gap_pct': round(gap_pct, 2),
                        'pre_market_volume': int(pre_market_vol),
                        'catalysts': catalysts
                    })
            except Exception as e:
                logger.error(f"Error scanning {ticker}: {e}")
                
        df_results = pd.DataFrame(results)
        if not df_results.empty:
            df_results = df_results.sort_values(by='gap_pct', ascending=False).reset_index(drop=True)
        return df_results
        
    def _fetch_catalysts(self, ticker_obj: yf.Ticker) -> List[str]:
        catalysts = []
        keywords = ["earnings", "revenue", "fda", "merger", "acquisition", "clinical", "partnership", "guidance"]
        try:
            news_items = ticker_obj.news
            if news_items:
                for item in news_items:
                    title = item.get("title", "").lower()
                    if any(kw in title for kw in keywords):
                        catalysts.append(item.get("title"))
        except Exception:
            pass
        return catalysts
```

---

## 5. Verification Method

To verify these components during implementation, the team should execute:
1. **Requirements setup**:
   ```bash
   pip install pandas yfinance alpaca-py pytest pytz numpy
   ```
2. **Unit Tests for Indicators Module (`tests/test_indicators.py`)**:
   - Create mock DataFrame with synthetic daily / intraday price arrays (e.g. standard sine wave or constant columns).
   - Assert all output column names are present: `vwap`, `macd`, `macd_signal`, `macd_hist`, `rsi`, `bb_upper`, `bb_middle`, `bb_lower`, `ema_fast`, `ema_slow`, `ema_crossover`, and `rvol`.
   - Verify calculation correctness with known hand-calculated edge cases (e.g. constant price series should result in RSI of 50, standard deviation of Bollinger Bands as 0, EMA fast/slow identical).
   - Test empty DataFrame input handles gracefully.
   - Run tests with:
     ```bash
     pytest tests/test_indicators.py
     ```
3. **Unit Tests for Scanner (`tests/test_scanner.py`)**:
   - Mock Yahoo Finance's `history` calls to return pre-fabricated pre-market dataframes.
   - Assert filtering logic correctly drops tickers under volume or gap percentage thresholds.
   - Assert sorting functions correctly (largest gap percentage ranked first).
4. **Verification command execution**:
   Run all tests from the repository root:
   ```bash
   pytest
   ```
