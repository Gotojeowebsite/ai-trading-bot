import os
import sys
import argparse
import sqlite3
import datetime
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List

# Import core contract functions
from automation.indicators import calculate_indicators
from sentiment.finbert_client import get_sentiment
from politician.copy_mode import get_politician_signals
from engine.decision_engine import screen_ticker, make_decision
from execution.order_manager import execute_bracket_order, close_all_positions

app = FastAPI(title="AI Trading Bot Dashboard")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.get("/api/portfolio")
def get_portfolio():
    db_path = os.getenv("DATABASE_URL", "sqlite:///trading.db").replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Check if table exists, return empty or dummy if not
    try:
        cursor.execute("SELECT SUM(qty * price) FROM trade_logs WHERE status = 'submitted'")
        positions_val = cursor.fetchone()[0] or 0.0
    except Exception:
        positions_val = 0.0
    conn.close()
    
    return {
        "portfolio_value": 100000.0 + positions_val,
        "cash": 100000.0 - positions_val,
        "positions_value": positions_val
    }

@app.get("/api/trades")
def get_trades():
    db_path = os.getenv("DATABASE_URL", "sqlite:///trading.db").replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM trade_logs ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        trades = [dict(row) for row in rows]
    except Exception:
        trades = []
    conn.close()
    return trades

@app.get("/api/signals")
def get_signals():
    db_path = os.getenv("DATABASE_URL", "sqlite:///trading.db").replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM scanned_tickers")
        rows = cursor.fetchall()
        signals = [dict(row) for row in rows]
    except Exception:
        signals = []
    conn.close()
    return signals

@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def run_scan():
    print("Running market scan...")
    db_path = os.getenv("DATABASE_URL", "sqlite:///trading.db").replace("sqlite:///", "")
    
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    
    for ticker in tickers:
        # Fetch OHLCV data
        # During testing, we use dummy DataFrame to bypass yfinance calls
        import pandas as pd
        dates = pd.date_range(end=datetime.datetime.now(), periods=100)
        
        # Simulate price chart
        df = pd.DataFrame({
            "open": [150.0] * 100,
            "high": [152.0] * 100,
            "low": [148.0] * 100,
            "close": [150.0] * 100,
            "volume": [100000.0] * 100
        }, index=dates)
        
        # Compute indicators
        processed_df = calculate_indicators(df)
        last_row = processed_df.iloc[-1]
        
        # Save to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO scanned_tickers (
                ticker, scan_time, open, high, low, close, volume, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            datetime.datetime.now().isoformat(),
            float(last_row["open"]),
            float(last_row["high"]),
            float(last_row["low"]),
            float(last_row["close"]),
            float(last_row["volume"]),
            float(last_row["vwap"]),
            float(last_row["rsi"]),
            float(last_row["macd"]),
            float(last_row["bb_upper"]),
            float(last_row["bb_lower"]),
            float(last_row["ema"]),
            float(last_row["rvol"])
        ))
        conn.commit()
        conn.close()
    print("Market scan completed.")

def run_trade():
    print("Running trading cycle...")
    db_path = os.getenv("DATABASE_URL", "sqlite:///trading.db").replace("sqlite:///", "")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scanned_tickers")
    scanned = cursor.fetchall()
    conn.close()

    for row in scanned:
        ticker = row["ticker"]
        
        # 1. Fetch NLP Sentiment
        sentiment_score = get_sentiment(ticker)
        
        # 2. Fetch Politician signals
        poly_signals = get_politician_signals(ticker)
        
        # Blend signals into dictionary for LLM decision engine
        combined_data = {
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
            "vwap": row["vwap"],
            "rsi": row["rsi"],
            "macd": row["macd"],
            "bb_upper": row["bb_upper"],
            "bb_lower": row["bb_lower"],
            "ema": row["ema"],
            "rvol": row["rvol"],
            "sentiment_score": sentiment_score,
            "politician_score": poly_signals["scored_weight"],
            "politician_recency": poly_signals["recency_days"]
        }

        # 3. Tier 1 Screening
        screen_score = screen_ticker(ticker, combined_data)
        if screen_score > 0.5:
            # 4. Tier 2 Decision
            decision = make_decision(ticker, combined_data)
            action = decision.get("action", "HOLD").upper()
            
            if action in ["BUY", "SELL"]:
                qty = decision.get("position_size", 10)
                tp = decision.get("take_profit", row["close"] * 1.05)
                sl = decision.get("stop_loss", row["close"] * 0.95)
                
                # 5. Order execution
                order_id = execute_bracket_order(ticker, action, qty, tp, sl)
                print(f"Placed {action} order for {ticker}: {order_id}")
    
    print("Trading cycle completed.")

def main():
    parser = argparse.ArgumentParser(description="AI Trading Bot CLI")
    parser.add_argument("--mode", choices=["scan", "trade", "dashboard"], required=True, help="Execution mode")
    args = parser.parse_args()

    if args.mode == "scan":
        run_scan()
    elif args.mode == "trade":
        run_trade()
    elif args.mode == "dashboard":
        uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
