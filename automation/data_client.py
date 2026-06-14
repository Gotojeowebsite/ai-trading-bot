import threading
import time
import logging
from typing import List, Dict, Optional, Callable
import pandas as pd
import yfinance as yf

# Import Alpaca components safely
try:
    from alpaca.data.live.stock import StockDataStream
except ImportError:
    StockDataStream = None

logger = logging.getLogger(__name__)

class MarketDataClient:
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        symbols: List[str],
        live: bool = False,
        alpaca_ws_url: Optional[str] = None,
        fallback_interval: int = 60,
        max_cache_bars: int = 1000,
        use_yfinance_fallback: bool = False
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbols = symbols
        self.live = live
        self.alpaca_ws_url = alpaca_ws_url
        self.fallback_interval = fallback_interval
        self.max_cache_bars = max_cache_bars
        self.use_yfinance_fallback = use_yfinance_fallback
        
        self.cache: Dict[str, pd.DataFrame] = {
            symbol: pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'timestamp'])
            for symbol in symbols
        }
        self._lock = threading.Lock()
        self.running = False
        
        self.stream_thread = None
        self.fallback_thread = None
        self.stream = None
        self.on_bar_callback: Optional[Callable[[str, pd.DataFrame], None]] = None
        
    def start(self):
        self.running = True
        if self.use_yfinance_fallback or StockDataStream is None:
            logger.info("Starting yfinance polling fallback thread.")
            self.fallback_thread = threading.Thread(target=self._run_yfinance_polling, daemon=True)
            self.fallback_thread.start()
        else:
            logger.info("Starting Alpaca StockDataStream thread.")
            self.stream_thread = threading.Thread(target=self._run_alpaca_stream, daemon=True)
            self.stream_thread.start()
            
    def stop(self):
        self.running = False
        if self.stream:
            try:
                # Attempt to stop the stream if running
                # (Alpaca-py stream stop methods may vary or be async, so we wrap in a try-except)
                if hasattr(self.stream, 'stop'):
                    self.stream.stop()
            except Exception as e:
                logger.error(f"Error stopping Alpaca stream: {e}")
                
    def register_callback(self, callback: Callable[[str, pd.DataFrame], None]):
        """Callback format: callback(symbol, symbol_df)"""
        self.on_bar_callback = callback
        
    def get_data(self, symbol: str) -> pd.DataFrame:
        with self._lock:
            return self.cache.get(symbol, pd.DataFrame()).copy()
            
    def _update_cache(self, symbol: str, new_row: dict):
        df_copy = None
        changed = False
        with self._lock:
            df = self.cache.get(symbol, pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'timestamp']))
            timestamp = new_row['timestamp']
            
            # Check for duplicate timestamp
            if not df.empty and timestamp in df['timestamp'].values:
                # Check if values actually changed
                idx = df[df['timestamp'] == timestamp].index[0]
                row_changed = False
                for k, v in new_row.items():
                    existing_val = df.at[idx, k]
                    if existing_val != v and not (pd.isna(existing_val) and pd.isna(v)):
                        row_changed = True
                        df.at[idx, k] = v
                if row_changed:
                    changed = True
            else:
                # Append row
                new_df = pd.DataFrame([new_row])
                df = pd.concat([df, new_df], ignore_index=True)
                changed = True
                
            if changed:
                # Limit cache size
                if len(df) > self.max_cache_bars:
                    df = df.iloc[-self.max_cache_bars:].reset_index(drop=True)
                self.cache[symbol] = df
                if self.on_bar_callback:
                    df_copy = df.copy()
            
        if changed and self.on_bar_callback and df_copy is not None:
            try:
                self.on_bar_callback(symbol, df_copy)
            except Exception as e:
                logger.error(f"Error in user callback for {symbol}: {e}")
                
    def _run_alpaca_stream(self):
        try:
            if StockDataStream is None:
                raise ImportError("alpaca-py is not installed or StockDataStream is not available.")
                
            url = self.alpaca_ws_url
            if not url:
                url = "wss://stream.data.alpaca.markets/v2/sip" if self.live else "wss://stream.data.alpaca.markets/v2/iex"
                
            self.stream = StockDataStream(self.api_key, self.secret_key, url=url)
            
            async def handle_bar(bar):
                new_row = {
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': float(bar.volume),
                    'timestamp': pd.to_datetime(bar.timestamp)
                }
                self._update_cache(bar.symbol, new_row)
                
            for symbol in self.symbols:
                self.stream.subscribe_bars(handle_bar, symbol)
                
            self.stream.run()
        except Exception as e:
            logger.error(f"Alpaca websocket error: {e}. Falling back to yfinance polling.")
            if self.running:
                self._run_yfinance_polling()
                
    def _run_yfinance_polling(self):
        while self.running:
            for symbol in self.symbols:
                if not self.running:
                    break
                try:
                    ticker = yf.Ticker(symbol)
                    df = ticker.history(period="1d", interval="1m")
                    if not df.empty:
                        for idx, row in df.iterrows():
                            new_row = {
                                'open': float(row['Open']),
                                'high': float(row['High']),
                                'low': float(row['Low']),
                                'close': float(row['Close']),
                                'volume': float(row['Volume']),
                                'timestamp': pd.to_datetime(idx)
                            }
                            self._update_cache(symbol, new_row)
                except Exception as e:
                    logger.error(f"Error fetching data from yfinance for {symbol}: {e}")
            # Bounded sleep checking running status
            sleep_step = 1.0
            elapsed = 0.0
            while elapsed < self.fallback_interval and self.running:
                time.sleep(sleep_step)
                elapsed += sleep_step
