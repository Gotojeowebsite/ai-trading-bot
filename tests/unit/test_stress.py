import os
import time
import threading
import queue
import sqlite3
import pytest
import numpy as np
import pandas as pd
import pytz
from datetime import datetime
from unittest.mock import MagicMock, patch

from automation.indicators import calculate_indicators
from automation.data_client import MarketDataClient
from automation.scanner import PreMarketScanner

DB_PATH = "test_stress_scanner.db"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Cleanup database before and after test
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass
    yield
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass

def test_indicators_extreme_large_input():
    n = 100000
    closes = np.sin(np.arange(n)) * 10.0 + 100.0
    df = pd.DataFrame({
        'open': closes,
        'high': closes + 1.0,
        'low': closes - 1.0,
        'close': closes,
        'volume': np.random.randint(1, 1000, size=n).astype(float)
    }, index=pd.date_range("2026-06-15 09:30:00", periods=n, freq='min'))
    
    start_time = time.time()
    res = calculate_indicators(df)
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Verify indicators columns exist
    assert 'rsi' in res.columns
    assert 'vwap' in res.columns
    assert 'bb_upper' in res.columns
    # Ensure it processes in reasonable time (e.g. < 5.0 seconds)
    assert elapsed < 5.0

def test_indicators_extreme_mathematics():
    # Test zeros
    df_zeros = pd.DataFrame({
        'open': [0.0]*50,
        'high': [0.0]*50,
        'low': [0.0]*50,
        'close': [0.0]*50,
        'volume': [0.0]*50
    })
    res_zeros = calculate_indicators(df_zeros)
    # VWAP of zero volume should fill with close (which is 0.0)
    assert (res_zeros['vwap'] == 0.0).all()
    # RSI of all zeros should return 50.0 (since avg_gain and avg_loss are both 0.0)
    assert res_zeros['rsi'].iloc[14] == 50.0

    # Test all NaNs
    df_nans = pd.DataFrame({
        'open': [np.nan]*50,
        'high': [np.nan]*50,
        'low': [np.nan]*50,
        'close': [np.nan]*50,
        'volume': [np.nan]*50
    })
    res_nans = calculate_indicators(df_nans)
    assert res_nans['rsi'].isna().all()
    assert res_nans['vwap'].isna().all()

    # Test mixed positive/negative values
    df_mixed = pd.DataFrame({
        'open': [10.0, -10.0, 10.0, -10.0]*15,
        'high': [15.0, -5.0, 15.0, -5.0]*15,
        'low': [5.0, -15.0, 5.0, -15.0]*15,
        'close': [10.0, -10.0, 10.0, -10.0]*15,
        'volume': [100.0]*60
    })
    res_mixed = calculate_indicators(df_mixed)
    # Check that calculation completes without error
    assert 'rsi' in res_mixed.columns

def test_data_client_concurrent_high_frequency():
    client = MarketDataClient(
        api_key="mock_key",
        secret_key="mock_secret",
        symbols=["AAPL", "MSFT", "GOOG"],
        live=False
    )
    
    callback_calls = queue.Queue()
    def callback(symbol, df):
        callback_calls.put((symbol, df.copy()))
        
    client.register_callback(callback)
    
    num_threads = 5
    updates_per_thread = 100
    symbols = ["AAPL", "MSFT", "GOOG"]
    threads = []
    
    def worker(thread_idx):
        for i in range(updates_per_thread):
            symbol = symbols[i % len(symbols)]
            ts = pd.Timestamp("2026-06-15 09:30:00") + pd.Timedelta(seconds=i)
            bar = {
                'open': 100.0 + i,
                'high': 105.0 + i,
                'low': 95.0 + i,
                'close': 101.0 + i,
                'volume': 1000 + i,
                'timestamp': ts
            }
            client._update_cache(symbol, bar)
            # Also simulate reading concurrently
            _ = client.get_data(symbol)
            time.sleep(0.001)
            
    for t_idx in range(num_threads):
        t = threading.Thread(target=worker, args=(t_idx,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # Verify cache has correct maximum size limit
    for sym in symbols:
        cached = client.get_data(sym)
        assert len(cached) <= client.max_cache_bars
        
    # Callback optimization check: verify callback was called and didn't crash
    assert not callback_calls.empty()

def test_scanner_dst_transitions():
    scanner = PreMarketScanner(DB_PATH, ["AAPL"])
    
    # Spring forward DST transition: March 8, 2026
    timestamps_spring = [
        "2026-03-06 15:59:00-05:00",
        "2026-03-06 16:00:00-05:00",
        "2026-03-08 08:30:00-04:00",
        "2026-03-08 09:00:00-04:00"
    ]
    
    df_history = pd.DataFrame({
        'Open': [100.0, 100.0, 105.0, 106.0],
        'High': [101.0, 101.0, 106.0, 107.0],
        'Low': [99.0, 99.0, 104.0, 105.0],
        'Close': [100.0, 100.5, 105.5, 106.0],
        'Volume': [1000, 2000, 5000, 10000]
    }, index=pd.to_datetime(timestamps_spring))
    
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df_history
    mock_ticker.news = []
    
    current_time_est = datetime(2026, 3, 8, 8, 35, tzinfo=pytz.timezone('US/Eastern'))
    
    with patch('yfinance.Ticker', return_value=mock_ticker):
        res = scanner.scan_ticker("AAPL", current_time_est)
        
    assert res['ticker'] == "AAPL"
    assert res['previous_close'] == 100.5
    assert res['premarket_price'] == 106.0
    assert res['premarket_volume'] == 15000
    
    # Fall back DST transition: November 1, 2026
    timestamps_fall = [
        "2026-10-30 15:59:00-04:00",
        "2026-10-30 16:00:00-04:00",
        "2026-11-01 08:30:00-05:00",
        "2026-11-01 09:00:00-05:00"
    ]
    
    df_history_fall = pd.DataFrame({
        'Open': [100.0, 100.0, 105.0, 106.0],
        'High': [101.0, 101.0, 106.0, 107.0],
        'Low': [99.0, 99.0, 104.0, 105.0],
        'Close': [100.0, 100.5, 105.5, 106.0],
        'Volume': [1000, 2000, 5000, 10000]
    }, index=pd.to_datetime(timestamps_fall))
    
    mock_ticker_fall = MagicMock()
    mock_ticker_fall.history.return_value = df_history_fall
    mock_ticker_fall.news = []
    
    current_time_est_fall = datetime(2026, 11, 1, 8, 35, tzinfo=pytz.timezone('US/Eastern'))
    
    with patch('yfinance.Ticker', return_value=mock_ticker_fall):
        res_fall = scanner.scan_ticker("AAPL", current_time_est_fall)
        
    assert res_fall['ticker'] == "AAPL"
    assert res_fall['previous_close'] == 100.5
    assert res_fall['premarket_price'] == 106.0
    assert res_fall['premarket_volume'] == 15000

def test_scanner_extreme_filters():
    scanner = PreMarketScanner(DB_PATH, ["AAPL"])
    
    # Case 1: previous close is 0
    df_zero_close = pd.DataFrame({
        'Open': [0.0, 0.0, 105.0, 106.0],
        'High': [0.0, 0.0, 106.0, 107.0],
        'Low': [0.0, 0.0, 104.0, 105.0],
        'Close': [0.0, 0.0, 105.5, 106.0],
        'Volume': [1000, 2000, 5000, 10000]
    }, index=pd.to_datetime([
        "2026-06-12 15:59:00-04:00",
        "2026-06-12 16:00:00-04:00",
        "2026-06-15 08:30:00-04:00",
        "2026-06-15 09:00:00-04:00"
    ]))
    
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df_zero_close
    mock_ticker.news = []
    
    current_time_est = datetime(2026, 6, 15, 8, 35, tzinfo=pytz.timezone('US/Eastern'))
    
    with patch('yfinance.Ticker', return_value=mock_ticker):
        res = scanner.scan_ticker("AAPL", current_time_est)
    assert res['gap_percentage'] == 0.0
    
    # Case 2: premarket volume is 0 or missing
    df_no_premarket = pd.DataFrame({
        'Open': [100.0, 100.5],
        'High': [101.0, 101.0],
        'Low': [99.0, 99.0],
        'Close': [100.0, 100.5],
        'Volume': [1000, 2000]
    }, index=pd.to_datetime([
        "2026-06-12 15:59:00-04:00",
        "2026-06-12 16:00:00-04:00"
    ]))
    mock_ticker.history.return_value = df_no_premarket
    
    with patch('yfinance.Ticker', return_value=mock_ticker):
        res = scanner.scan_ticker("AAPL", current_time_est)
    assert res['premarket_volume'] == 0
    assert res['premarket_price'] == 100.5
    assert res['gap_percentage'] == 0.0
