import os
import sys
import time
import socket
import pytest
import sqlite3
import threading
from .mocks.server import start_mock_server

@pytest.fixture(scope="session", autouse=True)
def configure_pythonpath():
    # Insert E2E mocks folder at the beginning of sys.path so that mock yfinance/transformers are loaded
    mocks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "mocks"))
    sys.path.insert(0, mocks_dir)
    yield
    if mocks_dir in sys.path:
        sys.path.remove(mocks_dir)

@pytest.fixture(scope="session", autouse=True)
def run_mock_services():
    # Find a free port for mock server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    
    # Start mock server in thread
    server_thread = threading.Thread(target=start_mock_server, args=(port,), daemon=True)
    server_thread.start()
    
    # Wait for server to boot
    time.sleep(0.5)
    
    # Expose environment variables to tests and subprocesses
    os.environ["TESTING"] = "true"
    os.environ["DB_PATH"] = "test_trading.db"
    os.environ["ALPACA_API_BASE_URL"] = f"http://localhost:{port}/alpaca"
    os.environ["OPENAI_API_BASE_URL"] = f"http://localhost:{port}/openai"
    os.environ["GEMINI_API_BASE_URL"] = f"http://localhost:{port}/gemini"
    os.environ["NEWS_API_URL"] = f"http://localhost:{port}/news"
    os.environ["POLITICIAN_API_URL"] = f"http://localhost:{port}/politician"
    
    yield port
    
    # Teardown logic
    if os.path.exists("test_trading.db"):
        try:
            os.remove("test_trading.db")
        except Exception:
            pass

@pytest.fixture(autouse=True)
def clean_db():
    # Clear DB tables before every test case to ensure test isolation
    if os.path.exists("test_trading.db"):
        conn = sqlite3.connect("test_trading.db")
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM scanned_tickers")
            cursor.execute("DELETE FROM signals")
            cursor.execute("DELETE FROM trades")
            # Reset settings
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('daily_loss_limit', '5000.00')")
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('circuit_breaker_tripped', 'false')")
            conn.commit()
        except sqlite3.OperationalError:
            # DB might not be initialized yet
            pass
        finally:
            conn.close()
    yield
