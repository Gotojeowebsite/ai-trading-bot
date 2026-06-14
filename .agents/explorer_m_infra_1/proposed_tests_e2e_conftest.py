import os
import sqlite3
import pytest
import shutil
from .mocks.alpaca_mock import AlpacaMockServer
from .mocks.llm_mock import LLMMockServer
from .mocks.feeds_mock import FeedsMockServer

# Configurable mock ports
ALPACA_HTTP_PORT = 8001
ALPACA_WS_PORT = 8002
LLM_PORT = 8003
FEEDS_PORT = 8004
TEST_DB_NAME = "test_trading.db"

@pytest.fixture(scope="session", autouse=True)
def env_setup():
    """Sets up the testing environment variables, ensuring all subprocesses point to local mocks."""
    old_env = dict(os.environ)
    
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_NAME}"
    os.environ["APCA_API_BASE_URL"] = f"http://127.0.0.1:{ALPACA_HTTP_PORT}"
    os.environ["APCA_API_KEY_ID"] = "mock_key"
    os.environ["APCA_API_SECRET_KEY"] = "mock_secret"
    os.environ["ALPACA_WS_URL"] = f"ws://127.0.0.1:{ALPACA_WS_PORT}"
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{LLM_PORT}/v1"
    os.environ["OPENAI_API_KEY"] = "mock_openai_key"
    os.environ["GEMINI_API_URL"] = f"http://127.0.0.1:{LLM_PORT}"
    os.environ["GEMINI_API_KEY"] = "mock_gemini_key"
    os.environ["CONGRESS_DISCLOSURES_URL"] = f"http://127.0.0.1:{FEEDS_PORT}/house_disclosures.json"
    os.environ["FINBERT_API_URL"] = f"http://127.0.0.1:{FEEDS_PORT}/models/ProsusAI/finbert"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(old_env)

@pytest.fixture(scope="session", autouse=True)
def mock_servers():
    """Starts all backend mock servers in background threads."""
    alpaca = AlpacaMockServer(http_port=ALPACA_HTTP_PORT, ws_port=ALPACA_WS_PORT)
    llm = LLMMockServer(port=LLM_PORT)
    feeds = FeedsMockServer(port=FEEDS_PORT)

    alpaca.start()
    llm.start()
    feeds.start()

    yield {
        "alpaca": alpaca,
        "llm": llm,
        "feeds": feeds
    }

    alpaca.stop()
    llm.stop()
    feeds.stop()

@pytest.fixture(scope="function")
def db_setup():
    """Initializes and cleans up the SQLite database between test runs."""
    # Remove existing test db
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
        
    conn = sqlite3.connect(TEST_DB_NAME)
    cursor = conn.cursor()
    
    # Create tables based on schema
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scanned_tickers (
        ticker TEXT PRIMARY KEY,
        scan_time TIMESTAMP,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        vwap REAL,
        rsi REAL,
        macd REAL,
        bb_upper REAL,
        bb_lower REAL,
        ema REAL,
        rvol REAL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sentiment_cache (
        ticker TEXT PRIMARY KEY,
        sentiment_score REAL,
        timestamp TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP,
        ticker TEXT,
        action TEXT,
        qty INTEGER,
        price REAL,
        take_profit REAL,
        stop_loss REAL,
        reasoning TEXT,
        status TEXT
    )
    """)
    
    conn.commit()
    conn.close()

    yield TEST_DB_NAME

    # Clean up DB after test
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
