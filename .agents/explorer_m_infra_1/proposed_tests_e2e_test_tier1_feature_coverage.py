import os
import subprocess
import sqlite3
import pytest
import requests
import json
import time

def test_scan_happy_path(db_setup):
    """
    FEAT-SCAN: Scanner retrieves prices, computes indicators, and saves to database.
    We run the CLI main.py --mode scan as a subprocess.
    """
    # Run scanner process
    result = subprocess.run(
        ["python", "main.py", "--mode", "scan"],
        capture_output=True,
        text=True,
        env=os.environ
    )
    
    # Assert successful execution
    assert result.returncode == 0
    assert "Market scan completed." in result.stdout or "Market scan completed." in result.stderr
    
    # Verify the database has the scanned tickers with valid technical indicators
    conn = sqlite3.connect(db_setup)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, rsi, ema, vwap, rvol FROM scanned_tickers")
    rows = cursor.fetchall()
    conn.close()
    
    assert len(rows) > 0
    for row in rows:
        ticker, rsi, ema, vwap, rvol = row
        assert ticker in ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        assert 0.0 <= rsi <= 100.0
        assert ema > 0.0
        assert vwap > 0.0
        assert rvol > 0.0

def test_sentiment_happy_path(db_setup):
    """
    FEAT-SENT: Ingests news headlines and computes sentiment score.
    Verifies that get_sentiment fetches and caches sentiment correctly.
    """
    from sentiment.finbert_client import get_sentiment
    
    # Clear cache/db if any
    conn = sqlite3.connect(db_setup)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sentiment_cache")
    conn.commit()
    conn.close()
    
    # Call get_sentiment for AAPL
    score = get_sentiment("AAPL")
    
    # Our mock server returns positive score: pos = 0.9, neg = 0.05 => 0.85
    assert 0.8 <= score <= 0.9
    
    # Verify it is cached in the DB
    conn = sqlite3.connect(db_setup)
    cursor = conn.cursor()
    cursor.execute("SELECT sentiment_score FROM sentiment_cache WHERE ticker = 'AAPL'")
    cached_score = cursor.fetchone()[0]
    conn.close()
    
    assert cached_score == score

def test_politician_happy_path():
    """
    FEAT-POLY: Scrapes/reads disclosures and extracts congressional trades.
    """
    from politician.copy_mode import get_politician_signals
    
    signals = get_politician_signals("AAPL")
    
    assert signals["ticker"] == "AAPL"
    assert len(signals["disclosures"]) > 0
    assert signals["scored_weight"] != 0.0
    assert signals["recency_days"] < 180

def test_llm_happy_path():
    """
    FEAT-LLM: Runs Tier 1 screening and Tier 2 decision, returning BUY/SELL/HOLD.
    """
    from engine.decision_engine import screen_ticker, make_decision
    
    dummy_data = {
        "close": 150.0,
        "rsi": 65.0,
        "sentiment_score": 0.85,
        "politician_score": 5.0,
        "politician_recency": 5
    }
    
    # Screen ticker should return > 0.5 (mock returns 0.85)
    screen_score = screen_ticker("AAPL", dummy_data)
    assert screen_score == 0.85
    
    # Make decision should return BUY dict (mock returns BUY)
    decision = make_decision("AAPL", dummy_data)
    assert decision["action"] == "BUY"
    assert decision["confidence"] == 0.85
    assert decision["entry_price"] == 150.0
    assert decision["stop_loss"] == 145.0
    assert decision["take_profit"] == 160.0

def test_exec_bracket_order(db_setup):
    """
    FEAT-EXEC: Places bracket entry, take profit, and stop loss legs on Alpaca.
    """
    from execution.order_manager import execute_bracket_order
    
    order_id = execute_bracket_order("AAPL", "BUY", 10, 160.0, 145.0)
    assert order_id.startswith("order-")
    
    # Check that it's in the trade_logs DB
    conn = sqlite3.connect(db_setup)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, action, qty, status FROM trade_logs WHERE ticker = 'AAPL'")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == "AAPL"
    assert row[1] == "BUY"
    assert row[2] == 10
    assert row[3] == "submitted"
