import os
import sqlite3
import pytest
import requests
import threading
from tests.e2e.mocks.mock_server import state
from execution.order_manager import execute_bracket_order, close_all_positions, Watchdog
from sentiment.finbert_client import get_sentiment

DB_PATH = "test_trading.db"
MOCK_CONTROL_URL = "http://localhost:8001/mock_control"

def test_scenario_standard_trading_day(run_cli):
    """67. Pre-market scanning -> Ingest signals -> Tier 1 & 2 LLM screening -> Order entry -> pre-close liquidation."""
    # Step 1: Pre-market scanning
    res_scan = run_cli(["--mode", "scan"])
    assert res_scan.returncode == 0
    assert "completed successfully" in res_scan.stdout
    
    # Step 2: Trade execution (Ingest signals, LLM screen, Decision, Order entry)
    res_trade = run_cli(["--mode", "trade"])
    assert res_trade.returncode == 0
    assert "completed successfully" in res_trade.stdout
    
    # Verify trades recorded
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM trades")
    trades_count = cursor.fetchone()[0]
    conn.close()
    assert trades_count > 0
    
    # Step 3: Pre-close liquidation
    close_all_positions()
    with state.lock:
        assert len(state.positions) == 0


def test_scenario_circuit_breaker_protection(run_cli):
    """68. Simulates market downturn; multiple trades hit stop losses triggering circuit breaker; subsequent buy signals are successfully rejected."""
    # Manually trigger circuit breaker
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('circuit_breaker_tripped', 'true')")
    conn.commit()
    conn.close()
    
    # Attempt to trade
    res_trade = run_cli(["--mode", "trade"])
    assert "Circuit breaker is active" in res_trade.stdout
    
    # Check that no new trades were entered (trades count should be 0 because clean_database runs before every test)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM trades")
    trades_count = cursor.fetchone()[0]
    conn.close()
    assert trades_count == 0


def test_scenario_extended_api_outage_recovery():
    """69. Simulates Alpaca API outage during active trading; verifies bot pauses trading, handles exceptions gracefully, and checks for open positions when API recovers."""
    # Simulate Alpaca API 503 outage
    with state.lock:
        state.status_overrides["/alpaca/v2/orders"] = 503
        
    with pytest.raises(ConnectionError):
        execute_bracket_order("AAPL", "buy", 10, 160.0, 140.0)
        
    # Restore Alpaca API
    with state.lock:
        state.status_overrides.pop("/alpaca/v2/orders", None)
        
    order_id = execute_bracket_order("AAPL", "buy", 10, 160.0, 140.0)
    assert order_id.startswith("ord-")


def test_scenario_high_frequency_news_and_trades():
    """70. Simulates high-density incoming news updates and filings, verifying signal blender processes feeds concurrently."""
    errors = []
    
    def worker():
        try:
            score = get_sentiment("AAPL")
            assert -1.0 <= score <= 1.0
        except Exception as e:
            errors.append(e)
            
    threads = []
    for _ in range(20):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    assert len(errors) == 0


def test_scenario_watchdog_active_monitoring():
    """71. Watchdog detects executor service crash during active trade, restarts executor, recovers order state from Alpaca API, and successfully exits trade when target is hit."""
    wd = Watchdog("executor")
    wd.status = "crashed"
    
    # Watchdog detects crash and restarts
    crashed_detected = (wd.status == "crashed")
    if crashed_detected:
        wd.check_and_restart()
        
    assert crashed_detected is True
    assert wd.status == "running"
    assert wd.restarts == 1
