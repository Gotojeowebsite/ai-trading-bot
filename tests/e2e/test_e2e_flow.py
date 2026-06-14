import sqlite3
import os
from tests.e2e.mocks.mock_server import state

def test_e2e_scanner_and_trading_flow(run_cli):
    # 1. Verify that database starts clean
    db_path = "test_trading.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM scanned_tickers")
    assert cursor.fetchone()[0] == 0
    conn.close()

    # 2. Run scan mode
    result = run_cli(["--mode", "scan"])
    assert result.returncode == 0
    assert "Scan mode completed successfully." in result.stdout

    # Verify scanned tickers are saved
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, rsi, ema FROM scanned_tickers")
    scanned = cursor.fetchall()
    assert len(scanned) == 3
    tickers = {row[0] for row in scanned}
    assert tickers == {"AAPL", "MSFT", "GOOGL"}
    conn.close()

    # 3. Run trade mode
    result = run_cli(["--mode", "trade"])
    assert result.returncode == 0
    assert "Trade mode completed successfully." in result.stdout

    # Verify that trades and signals are recorded
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT ticker, blended_score FROM signals")
    signals = cursor.fetchall()
    # At least AAPL should have score >= 0.7 from screen_ticker (mock returns 0.85)
    # So blended score should be computed: (0.85 * 0.4) + (sentiment * 0.3) + (poly_score * 0.3)
    # sentiment: positive (0.90) - negative (0.05) = 0.85
    # poly_score: recency score of AAPL is 0.95
    # blended score: 0.85*0.4 + 0.85*0.3 + 0.95*0.3 = 0.34 + 0.255 + 0.285 = 0.88
    assert len(signals) > 0
    assert any(row[0] == "AAPL" for row in signals)
    
    cursor.execute("SELECT ticker, side, qty, entry_price, status FROM trades")
    trades = cursor.fetchall()
    assert len(trades) > 0
    assert trades[0][0] == "AAPL"
    assert trades[0][1] == "buy"
    assert trades[0][2] == 10
    assert trades[0][3] == 150.0
    assert trades[0][4] == "filled"
    conn.close()

    # Verify that order state in Mock server is updated
    with state.lock:
        assert len(state.orders) > 0
        assert any(order["symbol"] == "AAPL" for order in state.orders.values())
        assert state.positions["AAPL"]["qty"] == "10"
