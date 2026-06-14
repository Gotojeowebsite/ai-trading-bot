import os
import sqlite3
import pytest
import numpy as np
import pandas as pd
import pytz
from datetime import datetime
from unittest.mock import MagicMock, patch
from automation.scanner import PreMarketScanner, run_scanner, view_watchlist

DB_PATH = "test_scanner.db"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Cleanup database before and after test
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_db_initialization():
    scanner = PreMarketScanner(DB_PATH, ["AAPL"])
    assert os.path.exists(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist'")
    table = cursor.fetchone()
    assert table is not None
    conn.close()

def test_scan_ticker_calculation():
    scanner = PreMarketScanner(DB_PATH, ["AAPL"])
    
    # Setup mock data for yfinance history
    # 2 days of 1-minute data
    # Date 1: previous day. We want regular session (9:30 AM to 4:00 PM EST) close.
    # Date 2: current day. We want pre-market (4:00 AM to 9:29 AM EST).
    timestamps = [
        # Previous day regular session
        "2026-06-12 15:59:00-04:00",
        "2026-06-12 16:00:00-04:00",
        # Current day pre-market session
        "2026-06-15 08:30:00-04:00",
        "2026-06-15 09:00:00-04:00"
    ]
    
    df_history = pd.DataFrame({
        'Open': [100.0, 100.0, 105.0, 106.0],
        'High': [101.0, 101.0, 106.0, 107.0],
        'Low': [99.0, 99.0, 104.0, 105.0],
        'Close': [100.0, 100.5, 105.5, 106.0], # Prev close should be 100.5
        'Volume': [1000, 2000, 5000, 10000] # Premarket volume: 5000 + 10000 = 15000
    }, index=pd.to_datetime(timestamps))
    
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df_history
    mock_ticker.news = [{"title": "Big Earnings Beat for AAPL"}]
    
    current_time_est = datetime(2026, 6, 15, 8, 35, tzinfo=pytz.timezone('US/Eastern'))
    
    with patch('yfinance.Ticker', return_value=mock_ticker):
        res = scanner.scan_ticker("AAPL", current_time_est)
        
    assert res['ticker'] == "AAPL"
    assert res['previous_close'] == 100.5
    assert res['premarket_price'] == 106.0
    # Gap % = (106.0 - 100.5) / 100.5 * 100 = 5.5 / 100.5 * 100 = 5.4726%
    assert np.isclose(res['gap_percentage'], (5.5 / 100.5) * 100.0)
    assert res['premarket_volume'] == 15000
    assert res['news_catalyst'] == "Big Earnings Beat for AAPL"

def test_scanner_save_to_db():
    scanner = PreMarketScanner(DB_PATH, ["AAPL"])
    results = [{
        'ticker': "AAPL",
        'gap_percentage': 5.47,
        'premarket_volume': 15000,
        'news_catalyst': "Big Earnings Beat for AAPL"
    }]
    
    scanner.save_to_db(results, "2026-06-15")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, scan_date, gap_percentage, premarket_volume, news_catalyst FROM watchlist")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == "AAPL"
    assert row[1] == "2026-06-15"
    assert np.isclose(row[2], 5.47)
    assert row[3] == 15000
    assert row[4] == "Big Earnings Beat for AAPL"

def test_scanner_time_restrictions():
    # If run after 9:30 AM EST, run_scanner should abort and return empty results unless forced
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    
    # 10:00 AM EST (after cutoff)
    with patch('yfinance.Ticker', return_value=mock_ticker):
        results = run_scanner(DB_PATH, ["AAPL"], force=False, date_override="2026-06-15 10:00:00")
        assert len(results) == 0
        
        # When force=True, it runs anyway
        results_forced = run_scanner(DB_PATH, ["AAPL"], force=True, date_override="2026-06-15 10:00:00")
        assert len(results_forced) == 1
        assert results_forced[0]['ticker'] == "AAPL"

def test_scanner_symbol_validation():
    from automation.scanner import is_valid_symbol
    assert is_valid_symbol("AAPL") is True
    assert is_valid_symbol("BRK-B") is True
    assert is_valid_symbol("0005.HK") is True
    assert is_valid_symbol("^GSPC") is True
    assert is_valid_symbol("AAPL; DROP TABLE") is False
    assert is_valid_symbol("MSFT/USD") is False
    assert is_valid_symbol("TS LA") is False
    assert is_valid_symbol("") is False
    assert is_valid_symbol("A" * 16) is False

def test_scanner_nan_handling():
    scanner = PreMarketScanner(DB_PATH, ["AAPL"])
    
    # Setup mock data with NaNs in Close and Volume columns
    timestamps = [
        "2026-06-12 15:59:00-04:00",
        "2026-06-12 16:00:00-04:00", # Will be dropped due to Close NaN
        "2026-06-15 08:30:00-04:00", # Will be dropped due to Volume NaN
        "2026-06-15 09:00:00-04:00"  # Premarket price, premarket vol
    ]
    
    df_history = pd.DataFrame({
        'Open': [100.0, 100.0, 105.0, 106.0],
        'High': [101.0, 101.0, 106.0, 107.0],
        'Low': [99.0, 99.0, 104.0, 105.0],
        'Close': [100.0, np.nan, 105.5, 106.0],
        'Volume': [1000, 2000, np.nan, 10000]
    }, index=pd.to_datetime(timestamps))
    
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = df_history
    mock_ticker.news = []
    
    current_time_est = datetime(2026, 6, 15, 8, 35, tzinfo=pytz.timezone('US/Eastern'))
    
    with patch('yfinance.Ticker', return_value=mock_ticker):
        res = scanner.scan_ticker("AAPL", current_time_est)
        
    assert res['ticker'] == "AAPL"
    # Row at 16:00:00 is dropped, so the last valid regular session close is at 15:59:00, which is 100.0.
    assert res['previous_close'] == 100.0
    # Row at 08:30:00 is dropped due to NaN Volume, so only 09:00:00 remains in premarket.
    assert res['premarket_volume'] == 10000
    assert res['premarket_price'] == 106.0
    # Gap % = (106.0 - 100.0) / 100.0 * 100 = 6.0%
    assert np.isclose(res['gap_percentage'], 6.0)
