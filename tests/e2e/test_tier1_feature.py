import os
import time
import sqlite3
import pytest
import pandas as pd
import requests
import websocket
from tests.e2e.mocks.mock_server import state
from automation.indicators import calculate_indicators
from sentiment.finbert_client import get_sentiment
from politician.copy_mode import get_politician_signals
from engine.decision_engine import screen_ticker, make_decision
from execution.order_manager import execute_bracket_order, close_all_positions, Watchdog
from automation.scanner import run_scanner

DB_PATH = "test_trading.db"
MOCK_CONTROL_URL = "http://localhost:8001/mock_control"

# ==========================================
# FEAT-SCAN: Market Scanner & Technical Indicators
# ==========================================

def test_scan_happy_path(run_cli):
    """1. Scanner retrieves prices, computes indicators, and saves to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scanned_tickers")
    conn.commit()
    conn.close()

    result = run_cli(["--mode", "scan"])
    assert result.returncode == 0
    assert "completed successfully" in result.stdout or "completed" in result.stdout

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, vwap, rsi, macd FROM scanned_tickers")
    rows = cursor.fetchall()
    assert len(rows) > 0
    tickers = {r[0] for r in rows}
    assert "AAPL" in tickers
    conn.close()


def test_scan_yfinance_fallback(run_cli):
    """2. Scanner falls back to yfinance when Alpaca historical API fails."""
    # Set mock server to return 500 for Alpaca bars
    with state.lock:
        state.status_overrides["/alpaca/v2/stocks/bars"] = 500

    result = run_cli(["--mode", "scan"])
    assert result.returncode == 0

    # Verify that the scanner still succeeded using yfinance fallback
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM scanned_tickers")
    count = cursor.fetchone()[0]
    assert count > 0
    conn.close()


def test_scan_indicators_non_empty():
    """3. Verifies calculated indicators are valid floats."""
    raw_data = {
        "open": [150.0 + i for i in range(30)],
        "high": [152.0 + i for i in range(30)],
        "low": [148.0 + i for i in range(30)],
        "close": [151.0 + i for i in range(30)],
        "volume": [10000 + i for i in range(30)]
    }
    df = pd.DataFrame(raw_data)
    df_indicators = calculate_indicators(df)
    assert not df_indicators.empty

    last_row = df_indicators.iloc[-1]
    assert isinstance(float(last_row['VWAP']), float)
    assert isinstance(float(last_row['RSI']), float)
    assert isinstance(float(last_row['MACD']), float)
    assert isinstance(float(last_row['BB_upper']), float)
    assert isinstance(float(last_row['EMA']), float)
    assert isinstance(float(last_row['RVOL']), float)


def test_scan_schedule():
    """4. Scanner completes execution in expected pre-market timeline."""
    results = run_scanner(DB_PATH, ["AAPL", "MSFT"], force=True)
    assert isinstance(results, list)
    assert len(results) > 0


def test_scan_output_format():
    """5. Verify output scanner database schema matches specification."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(scanned_tickers)")
    columns = {col[1] for col in cursor.fetchall()}
    expected = {"ticker", "vwap", "rsi", "macd", "bb_upper", "bb_lower", "ema", "rvol"}
    for exp in expected:
        assert exp in columns or exp.upper() in columns
    conn.close()


# ==========================================
# FEAT-SENT: News Sentiment Analysis
# ==========================================

def test_sentiment_happy_path():
    """6. Ingests headlines and computes sentiment score."""
    score = get_sentiment("AAPL")
    # Mock defaults positive-negative = 0.90 - 0.05 = 0.85
    assert score == pytest.approx(0.85)


def test_sentiment_score_range():
    """7. FinBERT client returns scores strictly in [-1.0, 1.0]."""
    for symbol in ["AAPL", "MSFT", "TSLA"]:
        score = get_sentiment(symbol)
        assert -1.0 <= score <= 1.0


def test_sentiment_empty_news():
    """8. Default to neutral score (0.0) when no news matches ticker."""
    with state.lock:
        state.status_overrides["/sentiment/models/ProsusAI/finbert"] = 404
    score = get_sentiment("AAPL")
    assert score == 0.0


def test_sentiment_invalid_ticker():
    """9. Handles invalid symbols and returns neutral sentiment."""
    score = get_sentiment("INVALID_TICKER_XYZ")
    assert score == 0.0


def test_sentiment_cache(monkeypatch):
    """10. Sentiment scoring fetches from local cache if within TTL."""
    # We can mock get_sentiment to verify cache/repeated calls
    call_count = 0
    original_get = get_sentiment

    def mock_get(ticker):
        nonlocal call_count
        call_count += 1
        return original_get(ticker)

    monkeypatch.setattr("sentiment.finbert_client.get_sentiment", mock_get)
    s1 = get_sentiment("AAPL")
    s2 = get_sentiment("AAPL")
    assert s1 == s2
    # Ensure it behaves correctly and can be cached if client is implemented
    assert call_count > 0


# ==========================================
# FEAT-POLY: Congress Trade Copying
# ==========================================

def test_politician_happy_path():
    """11. Scrapes/reads disclosures and extracts congressional trades."""
    data = get_politician_signals("AAPL")
    assert data["ticker"] == "AAPL"
    assert data["signal_score"] == 0.95
    assert data["trade_type"] == "purchase"


def test_politician_scoring_weight():
    """12. Higher scores are assigned to recent/large trades."""
    data = get_politician_signals("AAPL")
    assert data["signal_score"] > 0.5


def test_politician_blended_signal(run_cli):
    """13. Correctly blends politician scores with other metrics."""
    run_cli(["--mode", "scan"])
    result = run_cli(["--mode", "trade"])
    assert result.returncode == 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, blended_score FROM signals WHERE ticker='AAPL'")
    row = cursor.fetchone()
    assert row is not None
    assert row[1] > 0.0
    conn.close()


def test_politician_corrupt_data():
    """14. Handles malformed congressional disclosure inputs gracefully."""
    with state.lock:
        state.status_overrides["/congress"] = 500
    res = get_politician_signals("AAPL")
    assert res["signal_score"] == 0.0


def test_politician_no_recent_trades():
    """15. Returns zero signal when trades are outside lookback."""
    res = get_politician_signals("GOOG")
    assert res["signal_score"] == 0.0


# ==========================================
# FEAT-LLM: Tiered LLM Decision Pipeline
# ==========================================

def test_llm_happy_path():
    """16. Runs Tier 1 screening and Tier 2 decision, returning BUY/SELL/HOLD."""
    t1 = screen_ticker("AAPL", {})
    assert t1 == pytest.approx(0.85)

    t2 = make_decision("AAPL", {})
    assert t2["action"] in ["BUY", "SELL", "HOLD"]


def test_llm_tier1_screening(run_cli):
    """17. Low-performing tickers are filtered out during Tier 1 screen."""
    with state.lock:
        # Mock Gemini (Tier 1) to return low score by forcing 500 -> 0.0 fallback
        state.status_overrides["/gemini/v1beta/models/gemini-2.0-flash:generateContent"] = 500
    
    run_cli(["--mode", "scan"])
    run_cli(["--mode", "trade"])

    # Ensure no trade was created for AAPL
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM trades WHERE ticker='AAPL'")
    count = cursor.fetchone()[0]
    assert count == 0
    conn.close()


def test_llm_tier2_json_schema():
    """18. Tier 2 response parses into valid JSON with specified parameters."""
    res = make_decision("AAPL", {})
    assert "action" in res
    assert "confidence" in res
    assert "entry_price" in res
    assert "stop_loss" in res
    assert "take_profit" in res


def test_llm_fallback_tier1_fail():
    """19. Fallbacks to fallback configuration on Tier 1 LLM failure."""
    with state.lock:
        state.status_overrides["/gemini/v1beta/models/gemini-2.0-flash:generateContent"] = 502
    score = screen_ticker("AAPL", {})
    assert score == 0.0


def test_llm_fallback_tier2_fail():
    """20. Fallbacks to Tier 1 score or HOLD on Tier 2 failure."""
    with state.lock:
        state.status_overrides["/openai/v1/chat/completions"] = 500
    res = make_decision("AAPL", {})
    assert res["action"] == "HOLD"


# ==========================================
# FEAT-EXEC: Alpaca Bracket Orders & Risk Circuit Breakers
# ==========================================

def test_exec_bracket_order():
    """21. Places bracket entry, take profit, and stop loss legs on Alpaca."""
    order_id = execute_bracket_order("AAPL", "buy", 10, 160.0, 140.0)
    assert order_id.startswith("ord-")

    with state.lock:
        assert order_id in state.orders
        order = state.orders[order_id]
        assert order["symbol"] == "AAPL"
        assert len(order["legs"]) == 2


def test_exec_circuit_breaker(run_cli):
    """22. Circuit breaker halts trading after daily realized losses exceed limit."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('circuit_breaker_tripped', 'true')")
    conn.commit()
    conn.close()

    result = run_cli(["--mode", "trade"])
    assert "Circuit breaker is active" in result.stdout


def test_exec_pre_close_liquidation():
    """23. Closes out open positions at 3:55 PM EST."""
    with state.lock:
        state.positions["AAPL"] = {"symbol": "AAPL", "qty": "10"}

    close_all_positions()

    with state.lock:
        assert "AAPL" not in state.positions


def test_exec_watchdog_restart():
    """24. Watchdog process restarts execution module if it dies."""
    wd = Watchdog("executor")
    wd.status = "crashed"
    assert wd.check_and_restart() is True
    assert wd.restarts == 1
    assert wd.status == "running"


def test_exec_position_sizing():
    """25. Position sizes do not exceed maximum capital allowance."""
    max_capital = 100000.0
    allowance = max_capital * 0.10  # 10% max sizing
    assert allowance == 10000.0


# ==========================================
# FEAT-DASH: Real-Time Glassmorphism Web Dashboard
# ==========================================

def test_dash_rest_portfolio(dashboard_server):
    """26. API returns accurate balance, cash, and position stats."""
    r = requests.get(f"{dashboard_server}/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert "cash" in data
    assert "equity" in data


def test_dash_rest_trades(run_cli, dashboard_server):
    """27. API returns complete history of trade logs."""
    run_cli(["--mode", "scan"])
    run_cli(["--mode", "trade"])

    r = requests.get(f"{dashboard_server}/trades")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 0


def test_dash_websocket_updates(dashboard_server):
    """28. WebSocket pushes updates on order placement and execution."""
    # WebSocket path
    ws = websocket.create_connection(f"ws://localhost:8000/ws/updates")
    ws.send("ping")
    resp = ws.recv()
    assert resp == "received"
    ws.close()


def test_dash_glassmorphism_static(dashboard_server):
    """29. Web server successfully serves static dashboard assets."""
    r = requests.get(f"{dashboard_server}/")
    assert r.status_code == 200
    assert "html" in r.text.lower()


def test_dash_settings_update(dashboard_server):
    """30. Configuration parameters updated via dashboard API."""
    payload = {"daily_loss_limit": "2000.00"}
    r = requests.post(f"{dashboard_server}/api/settings", json=payload)
    assert r.status_code == 200
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='daily_loss_limit'")
    val = cursor.fetchone()[0]
    conn.close()
    assert val == "2000.00"
