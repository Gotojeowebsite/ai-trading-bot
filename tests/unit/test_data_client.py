import time
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from automation.data_client import MarketDataClient

def test_data_client_initialization():
    client = MarketDataClient(
        api_key="mock_key",
        secret_key="mock_secret",
        symbols=["AAPL", "MSFT"],
        live=False,
        fallback_interval=5
    )
    assert client.api_key == "mock_key"
    assert client.secret_key == "mock_secret"
    assert client.symbols == ["AAPL", "MSFT"]
    assert "AAPL" in client.cache
    assert "MSFT" in client.cache
    assert client.cache["AAPL"].empty

def test_on_bar_callback():
    client = MarketDataClient(
        api_key="mock_key",
        secret_key="mock_secret",
        symbols=["AAPL"],
        live=False
    )
    
    callback_mock = MagicMock()
    client.register_callback(callback_mock)
    
    # Simulate receiving a bar update
    new_bar = {
        'open': 150.0,
        'high': 155.0,
        'low': 149.0,
        'close': 152.0,
        'volume': 1000,
        'timestamp': pd.Timestamp("2026-06-14 09:30:00")
    }
    
    client._update_cache("AAPL", new_bar)
    
    # Check cache has data
    cached_df = client.get_data("AAPL")
    assert not cached_df.empty
    assert len(cached_df) == 1
    assert cached_df['close'].iloc[0] == 152.0
    
    # Check callback was called
    callback_mock.assert_called_once()
    args, _ = callback_mock.call_args
    assert args[0] == "AAPL"
    assert isinstance(args[1], pd.DataFrame)
    assert args[1]['close'].iloc[0] == 152.0

@patch('automation.data_client.StockDataStream')
def test_alpaca_stream_run(mock_stream_class):
    mock_stream = MagicMock()
    mock_stream_class.return_value = mock_stream
    
    client = MarketDataClient(
        api_key="mock_key",
        secret_key="mock_secret",
        symbols=["AAPL", "MSFT"],
        live=False,
        use_yfinance_fallback=False
    )
    
    client.start()
    
    # Wait briefly to let the stream thread start
    time.sleep(0.1)
    
    client.stop()
    
    # Verify StockDataStream was instantiated and run
    mock_stream_class.assert_called_once_with("mock_key", "mock_secret", url="wss://stream.data.alpaca.markets/v2/iex")
    mock_stream.subscribe_bars.assert_called()
    mock_stream.run.assert_called()

def test_yfinance_polling():
    # Mock Ticker and its history method
    mock_ticker = MagicMock()
    
    # Create mock history DataFrame
    mock_history = pd.DataFrame({
        'Open': [150.0],
        'High': [155.0],
        'Low': [149.0],
        'Close': [152.0],
        'Volume': [1000]
    }, index=[pd.Timestamp("2026-06-14 09:30:00")])
    
    mock_ticker.history.return_value = mock_history
    
    client = MarketDataClient(
        api_key="mock_key",
        secret_key="mock_secret",
        symbols=["AAPL"],
        live=False,
        fallback_interval=1,
        use_yfinance_fallback=True
    )
    
    callback_mock = MagicMock()
    client.register_callback(callback_mock)
    
    with patch('yfinance.Ticker', return_value=mock_ticker):
        client.start()
        time.sleep(0.5) # Wait for polling thread to execute at least once
        client.stop()
        
    # Verify yfinance ticker was called with symbol
    # and history is downloaded
    cached_df = client.get_data("AAPL")
    assert not cached_df.empty
    assert cached_df['close'].iloc[0] == 152.0
    assert callback_mock.called

def test_data_client_callback_optimization():
    client = MarketDataClient(
        api_key="mock_key",
        secret_key="mock_secret",
        symbols=["AAPL"],
        live=False
    )
    
    callback_mock = MagicMock()
    client.register_callback(callback_mock)
    
    bar_1 = {
        'open': 150.0,
        'high': 155.0,
        'low': 149.0,
        'close': 152.0,
        'volume': 1000,
        'timestamp': pd.Timestamp("2026-06-14 09:30:00")
    }
    
    # First update: new bar -> should trigger callback
    client._update_cache("AAPL", bar_1)
    assert callback_mock.call_count == 1
    
    # Second update: duplicate unchanged bar -> should NOT trigger callback
    client._update_cache("AAPL", bar_1.copy())
    assert callback_mock.call_count == 1
    
    # Third update: duplicate timestamp but modified value -> should trigger callback
    bar_modified = bar_1.copy()
    bar_modified['close'] = 153.0
    client._update_cache("AAPL", bar_modified)
    assert callback_mock.call_count == 2
    
    # Fourth update: new timestamp -> should trigger callback
    bar_new_ts = bar_1.copy()
    bar_new_ts['timestamp'] = pd.Timestamp("2026-06-14 09:31:00")
    client._update_cache("AAPL", bar_new_ts)
    assert callback_mock.call_count == 3

def test_data_client_thread_safety():
    import threading
    client = MarketDataClient(
        api_key="mock_key",
        secret_key="mock_secret",
        symbols=["AAPL"],
        live=False
    )
    
    # Define a callback that simulates slow execution to increase contention
    def callback(symbol, df):
        # Read the dataframe copy
        _ = len(df)
        
    client.register_callback(callback)
    
    # Concurrently update cache from multiple threads
    num_threads = 10
    updates_per_thread = 50
    threads = []
    
    def worker(thread_idx):
        for i in range(updates_per_thread):
            ts = pd.Timestamp("2026-06-14 09:00:00") + pd.Timedelta(minutes=(i + thread_idx * 100))
            bar = {
                'open': 100.0 + i,
                'high': 105.0 + i,
                'low': 95.0 + i,
                'close': 101.0 + i,
                'volume': 1000 + i,
                'timestamp': ts
            }
            client._update_cache("AAPL", bar)
            _ = client.get_data("AAPL")
            
    for t_idx in range(num_threads):
        t = threading.Thread(target=worker, args=(t_idx,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    cached_df = client.get_data("AAPL")
    assert len(cached_df) <= client.max_cache_bars
