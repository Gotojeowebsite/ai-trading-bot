import os
import sys
import subprocess
import sqlite3
import requests
import pytest

def test_scan_happy_path():
    env = os.environ.copy()
    
    # We add the mocks path to PYTHONPATH so it overrides yfinance
    mocks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "mocks"))
    env["PYTHONPATH"] = f"{mocks_dir}:{env.get('PYTHONPATH', '')}"
    
    # Run scan on main.py which is at the parent level of this test file
    main_py_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
    
    res = subprocess.run(
        ["python", main_py_path, "--mode", "scan"],
        env=env,
        capture_output=True,
        text=True
    )
    
    assert res.returncode == 0
    assert "Market scan completed." in res.stdout
    
    # Verify DB has entries
    db_path = env.get("DB_PATH", "test_trading.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM scanned_tickers")
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count > 0

def test_trade_happy_path():
    # Set up scan data first
    env = os.environ.copy()
    mocks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "mocks"))
    env["PYTHONPATH"] = f"{mocks_dir}:{env.get('PYTHONPATH', '')}"
    
    main_py_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
    
    subprocess.run(["python", main_py_path, "--mode", "scan"], env=env, capture_output=True)
    
    # Run trade loop
    res = subprocess.run(
        ["python", main_py_path, "--mode", "trade"],
        env=env,
        capture_output=True,
        text=True
    )
    
    assert res.returncode == 0
    assert "Trading loop cycle completed." in res.stdout
    
    # Verify trade is logged in DB
    db_path = env.get("DB_PATH", "test_trading.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trades")
    trade_count = cursor.fetchone()[0]
    conn.close()
    
    assert trade_count > 0

def test_sentiment_score_range():
    # Try importing using our mocked sys.path
    try:
        from sentiment.finbert_client import get_sentiment
    except ImportError:
        # Fallback if python path doesn't resolve in pytest process
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
        from sentiment.finbert_client import get_sentiment
        
    score = get_sentiment("AAPL")
    assert -1.0 <= score <= 1.0
    
def test_dashboard_api(run_mock_services):
    port = run_mock_services
    # Query mock account details
    res = requests.get(f"http://localhost:{port}/alpaca/v2/account")
    assert res.status_code == 200
    data = res.json()
    assert data["account_number"] == "MOCK12345"
