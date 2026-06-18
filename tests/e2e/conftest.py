import os
import time
import pytest
import subprocess
import sqlite3
from http.server import HTTPServer
import threading
from tests.e2e.mocks.mock_server import MockHTTPRequestHandler, MockWebSocketServer, MockIBSocketServer, state

# Monkey-patch override for dashboard.app.get_db to isolate dashboard database connections
try:
    import dashboard.app
    dashboard.app.get_db = lambda: sqlite3.connect(os.environ.get("DATABASE_PATH", "test_trading.db"))
except ImportError:
    pass

# Patch yfinance for offline mock testing
import yfinance as yf
import pandas as pd
import datetime
import pytz

class MockTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.news = [{"title": f"Mock news for {symbol}"}]
        
    def history(self, period="2d", interval="1m", prepost=True):
        tz = pytz.timezone('US/Eastern')
        now = datetime.datetime.now(tz)
        
        timestamps = []
        for i in range(5, -1, -1):
            day = now - datetime.timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            # Add timestamps for previous day regular session close and current day pre-market
            timestamps.append(f"{day_str} 15:59:00-04:00")
            timestamps.append(f"{day_str} 16:00:00-04:00")
            timestamps.append(f"{day_str} 08:30:00-04:00")
            timestamps.append(f"{day_str} 09:00:00-04:00")
            
        df = pd.DataFrame({
            'Open': [150.0] * len(timestamps),
            'High': [152.0] * len(timestamps),
            'Low': [148.0] * len(timestamps),
            'Close': [151.0] * len(timestamps),
            'Volume': [50000] * len(timestamps)
        }, index=pd.to_datetime(timestamps))
        
        if "ZERO" in self.symbol or self.symbol == "ZERO_VOL":
            df['Volume'] = 0.0
            
        return df

yf.Ticker = MockTicker
yf.download = lambda tickers, *args, **kwargs: MockTicker(tickers).history(*args, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def mock_servers():
    """Starts the E2E HTTP, WebSocket, and IB socket mock servers in the background."""
    # Start HTTP Server
    http_server = HTTPServer(("127.0.0.1", 8001), MockHTTPRequestHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()

    # Start WS Server
    ws_server = MockWebSocketServer("127.0.0.1", 8002)
    ws_server.start()

    # Start IB Socket Server
    ib_server = MockIBSocketServer("127.0.0.1", 7497)
    ib_server.start()

    # Inject mock endpoints into environment for the test session
    os.environ["ALPACA_API_BASE_URL"] = "http://localhost:8001/alpaca"
    os.environ["ALPACA_WS_BASE_URL"] = "ws://localhost:8002"
    os.environ["ALPACA_API_KEY"] = "mock_key"
    os.environ["ALPACA_SECRET_KEY"] = "mock_secret"
    os.environ["OPENAI_API_BASE"] = "http://localhost:8001/openai"
    os.environ["GEMINI_API_BASE"] = "http://localhost:8001/gemini"
    os.environ["FINBERT_API_URL"] = "http://localhost:8001/sentiment"
    os.environ["CONGRESS_DISCLOSURE_URL"] = "http://localhost:8001/congress"
    os.environ["YFINANCE_BASE_URL"] = "http://localhost:8001/yfinance"
    os.environ["DATABASE_PATH"] = "test_trading.db"

    yield ws_server

    # Teardown
    http_server.shutdown()
    ws_server.stop()
    ib_server.stop()

@pytest.fixture(autouse=True)
def clean_database():
    """Ensures test_trading.db is empty and clean before each test runs."""
    db_path = "test_trading.db"
    # Connect and reset
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Drop and recreate standard tables for test run
    cursor.execute("DROP TABLE IF EXISTS scanned_tickers")
    cursor.execute("DROP TABLE IF EXISTS trades")
    cursor.execute("DROP TABLE IF EXISTS decisions")
    cursor.execute("DROP TABLE IF EXISTS portfolio_snapshots")
    cursor.execute("DROP TABLE IF EXISTS signals")
    cursor.execute("DROP TABLE IF EXISTS settings")
    
    cursor.execute("""
        CREATE TABLE scanned_tickers (
            ticker TEXT PRIMARY KEY,
            vwap REAL, rsi REAL, macd REAL, bb_upper REAL, bb_lower REAL, ema REAL, rvol REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE trades (
            id TEXT PRIMARY KEY, ticker TEXT, side TEXT, action TEXT, qty INTEGER, entry_price REAL,
            stop_loss REAL, take_profit REAL, confidence REAL, reasoning TEXT, status TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, action TEXT, confidence REAL,
            reasoning TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, equity REAL, cash REAL, daily_pnl REAL,
            open_positions TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE signals (
            ticker TEXT PRIMARY KEY, sentiment_score REAL, politician_score REAL,
            blended_score REAL, rsi REAL, macd REAL, vwap REAL, rvol REAL,
            sentiment REAL, composite REAL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    # Reset mock server data
    with state.lock:
        state.orders.clear()
        state.positions.clear()
        state.status_overrides.clear()
        state.response_delays.clear()
        state.account_cash = 100000.0
        state.account_equity = 100000.0
        
    yield
    
    # Remove database file after session or tests to clean up workspace
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass

@pytest.fixture
def run_cli():
    """Helper to run main.py in a subprocess with environment overrides."""
    def _run(args):
        env = os.environ.copy()
        # Add any test-specific variables here
        result = subprocess.run(
            ["python3", "main.py"] + args,
            env=env,
            capture_output=True,
            text=True
        )
        return result
    return _run

@pytest.fixture
def dashboard_server():
    """Starts the main.py dashboard server in a background subprocess."""
    subprocess.run(["fuser", "-k", "8000/tcp"], capture_output=True)
    p = subprocess.Popen(["python3", "main.py", "--mode", "dashboard"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(1.0)
    yield "http://localhost:8000"
    p.terminate()
    p.wait()

