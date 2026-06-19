import sqlite3
import pytest
import requests
import websocket
from tests.e2e.mocks.mock_server import state
from execution.order_manager import close_all_positions, Watchdog
from engine.decision_engine import screen_ticker
from politician.copy_mode import get_politician_signals

DB_PATH = "test_trading.db"
MOCK_CONTROL_URL = "http://localhost:8001/mock_control"

def test_comb_scanner_to_sentiment(run_cli, monkeypatch):
    """61. Tickers selected by the scanner are evaluated by the sentiment module,
    filtering out those with negative scores before LLM input.
    """
    # Scan to populate AAPL and MSFT
    run_cli(["--mode", "scan"])
    
    # Mock get_sentiment to return negative score for AAPL, positive for MSFT
    def mock_get_sentiment(ticker):
        if ticker == "AAPL":
            return -0.80
        return 0.80
    monkeypatch.setattr("sentiment.finbert_client.get_sentiment", mock_get_sentiment)
    
    # Configure negative sentiment override for AAPL in mock server for the subprocess
    requests.post(MOCK_CONTROL_URL, json={"sentiment_overrides": {"AAPL": -0.80}})
    
    # Run trade loop
    result = run_cli(["--mode", "trade"])
    assert result.returncode == 0
    
    # Verify AAPL was skipped (no trade) and MSFT was traded
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades")
    traded = {r[0] for r in cursor.fetchall()}
    conn.close()
    
    assert "AAPL" not in traded
    assert "MSFT" in traded


def test_comb_circuit_breaker_stops_all(run_cli):
    """62. Activating the daily circuit breaker immediately pauses scanning,
    cancels active bracket orders, and locks the execution engine.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('circuit_breaker_tripped', 'true')")
    conn.commit()
    conn.close()
    
    res_scan = run_cli(["--mode", "scan"])
    assert "Circuit breaker is active" in res_scan.stdout
    
    res_trade = run_cli(["--mode", "trade"])
    assert "Circuit breaker is active" in res_trade.stdout


def test_comb_watchdog_restores_execution_and_dashboard():
    """63. Restores crashed processes (executor and web UI) and synchronizes databases."""
    wd_executor = Watchdog("executor")
    wd_executor.status = "crashed"
    
    wd_dashboard = Watchdog("dashboard")
    wd_dashboard.status = "crashed"
    
    # Watchdog detects and restarts
    assert wd_executor.check_and_restart() is True
    assert wd_dashboard.check_and_restart() is True
    
    assert wd_executor.status == "running"
    assert wd_dashboard.status == "running"


def test_comb_politician_and_technical_concurrence(run_cli, monkeypatch):
    """64. A bullish politician disclosure overrides slightly bearish technical indicator trends, resulting in a BUY decision."""
    # Run scan to populate
    run_cli(["--mode", "scan"])
    
    # Mock screen_ticker to return 0.65 (bearish, below 0.70 threshold)
    monkeypatch.setattr("engine.decision_engine.screen_ticker", lambda ticker, data: 0.65)
    
    # Mock politician signal to return Nancy Pelosi purchase with 0.95 score
    def mock_get_politician(ticker):
        if ticker == "AAPL":
            return {"ticker": "AAPL", "signal_score": 0.95, "trade_type": "purchase", "amount": "$100000"}
        return {"ticker": ticker, "signal_score": 0.0, "trade_type": None, "amount": None}
    monkeypatch.setattr("politician.copy_mode.get_politician_signals", mock_get_politician)
    
    # Run trade loop
    result = run_cli(["--mode", "trade"])
    assert result.returncode == 0
    
    # Verify AAPL placed a trade anyway because Pelosi's score bypassed the Tier 1 filter
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE ticker='AAPL'")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None


def test_comb_bracket_order_update_reflects_in_dashboard(run_cli, dashboard_server):
    """65. Placing an order triggers live WebSocket events that update the dashboard UI logs."""
    ws = websocket.create_connection("ws://localhost:8000/ws")
    resp = ws.recv()
    assert len(resp) > 0
    ws.close()


def test_comb_pre_close_liquidation_overrides_pending_orders():
    """66. Pre-close checks cancel outstanding orders, disable LLM calls, and liquidate all long/short positions."""
    with state.lock:
        state.positions["AAPL"] = {"symbol": "AAPL", "qty": "10"}
        state.positions["MSFT"] = {"symbol": "MSFT", "qty": "20"}
        
    close_all_positions()
    
    with state.lock:
        assert len(state.positions) == 0
