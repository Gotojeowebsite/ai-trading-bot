# E2E Test Infrastructure Design & Implementation Strategy

## 1. Executive Summary
This document defines the End-to-End (E2E) Test Infrastructure and Runner design for the AI Trading Bot. The system is designed to run 100% offline, isolation-compliant, and in a deterministic manner. External dependencies (Alpaca, yfinance, LLMs, News, and Congressional disclosures) are simulated via a lightweight, built-in mock server running in a background thread of the `pytest` runner. Core interface contracts are stubbed to facilitate verification of the test runner and tests.

---

## 2. Directory Structure Design for `tests/e2e/`
The proposed folder structure under `tests/` maintains absolute segregation between E2E testing resources and source code, in compliance with project standards.

```
tests/
├── __init__.py
└── e2e/
    ├── __init__.py
    ├── conftest.py                # Main test configuration, fixtures, and mock server orchestration
    ├── test_tier1_feature.py      # Tier 1: 30 Happy Path feature coverage tests
    ├── test_tier2_boundary.py     # Tier 2: 30 Boundary & Corner case tests
    ├── test_tier3_combinatorial.py# Tier 3: 6 Cross-Feature combination tests
    ├── test_tier4_scenarios.py     # Tier 4: 5 Real-World full day scenarios
    ├── mocks/
    │   ├── __init__.py
    │   ├── mock_server.py         # Mock HTTP & TCP/WS Server class
    │   └── data/                  # Static mock payloads
    │       ├── news_samples.json
    │       ├── politician_trades.csv
    │       └── historical_bars.json
    └── utils.py                   # E2E specific CLI runners and test helpers
```

---

## 3. Mock Server Design in `tests/e2e/conftest.py`
To support offline testing of subprocesses (the bot CLI and dashboard server), we implement a multi-purpose HTTP and WebSocket mock server running on `localhost`. Since subprocesses do not share memory with the test runner, configuration is passed via environment variables, and dynamic behavior (e.g., simulating API timeouts or rate limits) is controlled via a `/mock_control` HTTP endpoint.

### `tests/e2e/mocks/mock_server.py`
```python
import json
import threading
import socket
import struct
import hashlib
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer

class MockServerState:
    def __init__(self):
        self.lock = threading.Lock()
        self.orders = {}
        self.positions = {}
        self.account_cash = 100000.0
        self.account_equity = 100000.0
        self.status_overrides = {}  # Map path -> HTTP status code (e.g., {"/alpaca/v2/orders": 429})
        self.response_delays = {}    # Map path -> delay in seconds
        self.alpaca_ws_clients = []

# Global shared state
state = MockServerState()

class MockHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress server logging to keep test output clean
        pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _send_csv(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/csv")
        self.end_headers()
        self.wfile.write(data.encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        # Check overrides
        with state.lock:
            if self.path in state.status_overrides:
                self.send_response(state.status_overrides[self.path])
                self.end_headers()
                return

        # Mock Control Endpoint
        if self.path == "/mock_control":
            try:
                data = json.loads(post_data)
                with state.lock:
                    if "status_overrides" in data:
                        state.status_overrides.update(data["status_overrides"])
                    if "reset" in data and data["reset"]:
                        state.status_overrides.clear()
                        state.orders.clear()
                        state.positions.clear()
                        state.account_cash = 100000.0
                self._send_json({"status": "success"})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        # Alpaca Order Placement
        if self.path.startswith("/alpaca/v2/orders"):
            try:
                payload = json.loads(post_data)
                symbol = payload.get("symbol")
                qty = int(payload.get("qty", 0))
                side = payload.get("side")
                order_id = f"ord-{len(state.orders) + 1}"
                
                order = {
                    "id": order_id,
                    "symbol": symbol,
                    "qty": str(qty),
                    "side": side,
                    "status": "filled",
                    "type": payload.get("type", "market"),
                    "legs": []
                }
                
                # Handle bracket legs
                if payload.get("order_class") == "bracket":
                    tp = payload.get("take_profit", {}).get("limit_price")
                    sl = payload.get("stop_loss", {}).get("stop_price")
                    order["legs"] = [
                        {"id": f"{order_id}-tp", "side": "sell" if side == "buy" else "buy", "type": "limit", "limit_price": str(tp)},
                        {"id": f"{order_id}-sl", "side": "sell" if side == "buy" else "buy", "type": "stop", "stop_price": str(sl)}
                    ]
                
                with state.lock:
                    state.orders[order_id] = order
                    # Simple position updates
                    current_qty = int(state.positions.get(symbol, {}).get("qty", 0))
                    change = qty if side == "buy" else -qty
                    new_qty = current_qty + change
                    if new_qty == 0:
                        state.positions.pop(symbol, None)
                    else:
                        state.positions[symbol] = {
                            "symbol": symbol,
                            "qty": str(new_qty),
                            "avg_entry_price": "150.00"
                        }
                self._send_json(order)
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        # OpenAI Chat Completions Mock
        if self.path.startswith("/openai/v1/chat/completions"):
            response = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({
                            "action": "BUY",
                            "confidence": 0.88,
                            "entry_price": 150.0,
                            "stop_loss": 140.0,
                            "take_profit": 165.0,
                            "position_size": 10,
                            "reasoning": "Technical breakout supported by strong positive sentiment."
                        })
                    }
                }]
            }
            self._send_json(response)
            return

        # Gemini Mock API
        if "generateContent" in self.path:
            response = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "0.85"}]
                    }
                }]
            }
            self._send_json(response)
            return

        # FinBERT Sentiment Mock
        if "finbert" in self.path:
            response = [[
                {"label": "positive", "score": 0.90},
                {"label": "negative", "score": 0.05},
                {"label": "neutral", "score": 0.05}
            ]]
            self._send_json(response)
            return

        self._send_json({"error": "not found"}, 404)

    def do_GET(self):
        with state.lock:
            if self.path in state.status_overrides:
                self.send_response(state.status_overrides[self.path])
                self.end_headers()
                return

        # Alpaca Account Mock
        if self.path.startswith("/alpaca/v2/account"):
            self._send_json({
                "cash": str(state.account_cash),
                "equity": str(state.account_equity),
                "buying_power": str(state.account_cash * 4)
            })
            return

        # Alpaca Positions Mock
        if self.path.startswith("/alpaca/v2/positions"):
            with state.lock:
                self._send_json(list(state.positions.values()))
            return

        # Alpaca Order List Mock
        if self.path.startswith("/alpaca/v2/orders"):
            with state.lock:
                self._send_json(list(state.orders.values()))
            return

        # Alpaca Bars Historical Data Mock
        if "/bars" in self.path:
            # e.g., /alpaca/v2/stocks/AAPL/bars
            response = {
                "bars": [
                    {"t": "2026-06-12T16:00:00Z", "o": 150.0, "h": 152.0, "l": 149.0, "c": 151.0, "v": 50000, "vw": 150.5}
                ],
                "symbol": "AAPL"
            }
            self._send_json(response)
            return

        # Yahoo Finance Mock API
        if "/v8/finance/chart" in self.path:
            response = {
                "chart": {
                    "result": [{
                        "meta": {"symbol": "AAPL"},
                        "timestamp": [1718373600],
                        "indicators": {
                            "quote": [{"open": [150.0], "high": [152.0], "low": [149.0], "close": [151.0], "volume": [50000]}]
                        }
                    }]
                }
            }
            self._send_json(response)
            return

        # Congress Disclosures Mock API
        if "/congress" in self.path:
            csv_data = "DisclosureDate,FilerName,Ticker,TradeType,Amount,RecencyScore\n2026-06-10,Nancy Pelosi,AAPL,purchase,$100000,0.95"
            self._send_csv(csv_data)
            return

        self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        # Alpaca Liquidate Mock
        if self.path.startswith("/alpaca/v2/positions"):
            with state.lock:
                state.positions.clear()
            self._send_json({"status": "success"})
            return
        self._send_json({"error": "not found"}, 404)

class MockWebSocketServer:
    """Simulates Alpaca WebSocket stream using standard sockets."""
    def __init__(self, host="127.0.0.1", port=8002):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = False
        self.clients = []

    def start(self):
        self.running = True
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, conn):
        # Perform WebSocket Handshake
        try:
            data = conn.recv(1024).decode('utf-8')
            if "Upgrade: websocket" in data:
                key = [line for line in data.split("\r\n") if line.startswith("Sec-WebSocket-Key:")][0].split(": ")[1]
                accept_key = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode('utf-8')).digest()).decode('utf-8')
                handshake = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    "Sec-WebSocket-Accept: " + accept_key + "\r\n\r\n"
                )
                conn.send(handshake.encode('utf-8'))
                
                # Keep client connection open to stream updates
                with state.lock:
                    self.clients.append(conn)
                while self.running:
                    # Keepalive loop or read incoming messages
                    msg = conn.recv(1024)
                    if not msg:
                        break
            conn.close()
        except Exception:
            pass
        finally:
            with state.lock:
                if conn in self.clients:
                    self.clients.remove(conn)

    def broadcast(self, message):
        payload = json.dumps(message).encode('utf-8')
        header = bytearray()
        header.append(0x81)  # Text frame
        length = len(payload)
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", length))
            
        frame = header + payload
        with state.lock:
            for client in self.clients:
                try:
                    client.sendall(frame)
                except Exception:
                    pass

    def stop(self):
        self.running = False
        self.sock.close()
        with state.lock:
            for client in self.clients:
                try:
                    client.close()
                except Exception:
                    pass
            self.clients.clear()
```

### `tests/e2e/conftest.py`
```python
import os
import time
import pytest
import subprocess
import sqlite3
from http.server import HTTPServer
import threading
from tests.e2e.mocks.mock_server import MockHTTPRequestHandler, MockWebSocketServer, state

@pytest.fixture(scope="session", autouse=True)
def mock_servers():
    """Starts the E2E HTTP and WebSocket mock servers in the background."""
    # Start HTTP Server
    http_server = HTTPServer(("127.0.0.1", 8001), MockHTTPRequestHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()

    # Start WS Server
    ws_server = MockWebSocketServer("127.0.0.1", 8002)
    ws_server.start()

    # Inject mock endpoints into environment for the test session
    os.environ["ALPACA_API_BASE_URL"] = "http://localhost:8001/alpaca"
    os.environ["ALPACA_WS_BASE_URL"] = "ws://localhost:8002"
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
    cursor.execute("DROP TABLE IF EXISTS signals")
    
    cursor.execute("""
        CREATE TABLE scanned_tickers (
            ticker TEXT PRIMARY KEY,
            vwap REAL, rsi REAL, macd REAL, bb_upper REAL, bb_lower REAL, ema REAL, rvol REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE trades (
            id TEXT PRIMARY KEY, ticker TEXT, side TEXT, qty INTEGER, entry_price REAL,
            stop_loss REAL, take_profit REAL, status TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE signals (
            ticker TEXT PRIMARY KEY, sentiment_score REAL, politician_score REAL,
            blended_score REAL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    
    # Reset mock server data
    with state.lock:
        state.orders.clear()
        state.positions.clear()
        state.status_overrides.clear()
        state.account_cash = 100000.0
        
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
```

---

## 4. Core Contract Stubs Design
To verify the E2E framework without full module implementations, we provide the minimal stubs conforming to the contracts in `PROJECT.md`.

### `automation/indicators.py`
```python
import pandas as pd
import numpy as np

def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """
    Computes technical indicators: VWAP, RSI, MACD, Bollinger Bands, EMA, RVOL.
    Expects DataFrame with columns: open, high, low, close, volume.
    """
    df = data.copy()
    if df.empty:
        return df

    # VWAP
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    df['VWAP'] = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    
    # RSI (Simple stub calculation)
    df['RSI'] = 55.0
    
    # MACD
    df['MACD'] = 0.5
    
    # Bollinger Bands
    df['BB_mid'] = df['close'].rolling(window=2, min_periods=1).mean()
    df['BB_upper'] = df['BB_mid'] + 2.0
    df['BB_lower'] = df['BB_mid'] - 2.0
    
    # EMA
    df['EMA'] = df['close'].ewm(span=2, adjust=False, min_periods=1).mean()
    
    # RVOL (Relative Volume)
    df['RVOL'] = 1.2
    
    return df
```

### `sentiment/finbert_client.py`
```python
import os
import requests

def get_sentiment(ticker: str) -> float:
    """
    Ingests news headlines and uses mock FinBERT endpoint.
    Returns float in [-1.0, 1.0].
    """
    api_url = os.environ.get("FINBERT_API_URL", "http://localhost:8001/sentiment")
    try:
        # Simulate query to FinBERT API
        response = requests.post(f"{api_url}/models/ProsusAI/finbert", json={"text": f"News about {ticker}"}, timeout=5)
        if response.status_code == 200:
            result = response.json()
            # Calculate composite sentiment: positive_score - negative_score
            pos = next((x["score"] for x in result[0] if x["label"] == "positive"), 0.0)
            neg = next((x["score"] for x in result[0] if x["label"] == "negative"), 0.0)
            return float(pos - neg)
    except Exception:
        pass
    
    # Fallback default neutral sentiment
    return 0.0
```

### `politician/copy_mode.py`
```python
import os
import requests

def get_politician_signals(ticker: str) -> dict:
    """
    Fetches Capitol trade disclosures for the ticker and scores them.
    """
    api_url = os.environ.get("CONGRESS_DISCLOSURE_URL", "http://localhost:8001/congress")
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            # Simple parser for mock CSV
            lines = response.text.split("\n")
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split(",")
                if parts[2] == ticker:
                    return {
                        "ticker": ticker,
                        "signal_score": float(parts[5]),
                        "trade_type": parts[3],
                        "amount": parts[4]
                    }
    except Exception:
        pass
    return {"ticker": ticker, "signal_score": 0.0, "trade_type": None, "amount": None}
```

### `engine/decision_engine.py`
```python
import os
import json
import requests

def screen_ticker(ticker: str, data: dict) -> float:
    """
    Tier 1 screening score (0.0 to 1.0) using Gemini Mock API.
    """
    api_url = os.environ.get("GEMINI_API_BASE", "http://localhost:8001/gemini")
    try:
        # Standard format request
        payload = {"contents": [{"parts": [{"text": f"Screen {ticker} with data: {data}"}]}]}
        response = requests.post(f"{api_url}/v1beta/models/gemini-2.0-flash:generateContent", json=payload, timeout=5)
        if response.status_code == 200:
            val_str = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return float(val_str)
    except Exception:
        pass
    return 0.0

def make_decision(ticker: str, data: dict) -> dict:
    """
    Tier 2 premium JSON decision using OpenAI Mock API.
    """
    api_url = os.environ.get("OPENAI_API_BASE", "http://localhost:8001/openai")
    try:
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"Make decision for {ticker}"}]
        }
        response = requests.post(f"{api_url}/v1/chat/completions", json=payload, timeout=5)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception:
        pass
        
    return {
        "action": "HOLD",
        "confidence": 0.0,
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "position_size": 0,
        "reasoning": "Fallback decision: Error or Timeout."
    }
```

### `execution/order_manager.py`
```python
import os
import requests

def execute_bracket_order(ticker: str, side: str, qty: int, take_profit: float, stop_loss: float) -> str:
    """
    Places bracket order on Alpaca REST mock server.
    """
    api_url = os.environ.get("ALPACA_API_BASE_URL", "http://localhost:8001/alpaca")
    payload = {
        "symbol": ticker,
        "qty": qty,
        "side": side,
        "type": "market",
        "time_in_force": "gtc",
        "order_class": "bracket",
        "take_profit": {"limit_price": take_profit},
        "stop_loss": {"stop_price": stop_loss}
    }
    try:
        response = requests.post(f"{api_url}/v2/orders", json=payload, timeout=5)
        if response.status_code == 200:
            return response.json().get("id", "unknown-id")
    except Exception as e:
        raise ConnectionError(f"Failed to reach mock Alpaca server: {e}")
    return "failed-order"

def close_all_positions() -> None:
    """
    Triggers immediate close of all open holdings in Alpaca mock.
    """
    api_url = os.environ.get("ALPACA_API_BASE_URL", "http://localhost:8001/alpaca")
    try:
        requests.delete(f"{api_url}/v2/positions", timeout=5)
    except Exception as e:
        raise ConnectionError(f"Failed to clear mock positions: {e}")
```

### `main.py`
```python
import os
import sys
import argparse
import sqlite3
import pandas as pd
from automation.indicators import calculate_indicators
from sentiment.finbert_client import get_sentiment
from politician.copy_mode import get_politician_signals
from engine.decision_engine import screen_ticker, make_decision
from execution.order_manager import execute_bracket_order, close_all_positions

def get_db_connection():
    db_path = os.environ.get("DATABASE_PATH", "trading.db")
    return sqlite3.connect(db_path)

def mode_scan():
    # Pre-market scanner logic
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Mock stock tickers we scan
    tickers = ["AAPL", "MSFT", "GOOGL"]
    for ticker in tickers:
        # Fetch mock historical daily candles
        raw_data = {
            "open": [148.0, 149.0, 150.0],
            "high": [151.0, 150.0, 152.0],
            "low": [147.0, 148.0, 149.0],
            "close": [150.0, 149.0, 151.0],
            "volume": [100000, 120000, 150000]
        }
        df = pd.DataFrame(raw_data)
        df_indicators = calculate_indicators(df)
        last_row = df_indicators.iloc[-1]
        
        # Save to SQLite db
        cursor.execute("""
            INSERT OR REPLACE INTO scanned_tickers (ticker, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, float(last_row['VWAP']), float(last_row['RSI']), float(last_row['MACD']),
              float(last_row['BB_upper']), float(last_row['BB_lower']), float(last_row['EMA']), float(last_row['RVOL'])))
    
    conn.commit()
    conn.close()
    print("Scan mode completed successfully.")

def mode_trade():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Load scanned tickers
    cursor.execute("SELECT ticker, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol FROM scanned_tickers")
    rows = cursor.fetchall()
    
    for row in rows:
        ticker, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol = row
        data = {
            "vwap": vwap, "rsi": rsi, "macd": macd, "bb_upper": bb_upper,
            "bb_lower": bb_lower, "ema": ema, "rvol": rvol
        }
        
        # Tier 1 Screen
        t1_score = screen_ticker(ticker, data)
        if t1_score >= 0.7:
            # Ingest external signals
            sentiment = get_sentiment(ticker)
            poly_data = get_politician_signals(ticker)
            poly_score = poly_data.get("signal_score", 0.0)
            
            # Blend signals
            blended = (t1_score * 0.4) + (sentiment * 0.3) + (poly_score * 0.3)
            cursor.execute("""
                INSERT OR REPLACE INTO signals (ticker, sentiment_score, politician_score, blended_score)
                VALUES (?, ?, ?, ?)
            """, (ticker, sentiment, poly_score, blended))
            
            # Tier 2 Premium Decision
            decision = make_decision(ticker, data)
            if decision.get("action") == "BUY":
                order_id = execute_bracket_order(
                    ticker=ticker,
                    side="buy",
                    qty=decision.get("position_size", 10),
                    take_profit=decision.get("take_profit"),
                    stop_loss=decision.get("stop_loss")
                )
                cursor.execute("""
                    INSERT OR REPLACE INTO trades (id, ticker, side, qty, entry_price, stop_loss, take_profit, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (order_id, ticker, "buy", decision.get("position_size"), decision.get("entry_price"),
                      decision.get("stop_loss"), decision.get("take_profit"), "filled"))
                      
    conn.commit()
    conn.close()
    print("Trade mode completed successfully.")

def mode_dashboard():
    # Start web server stub
    print("Starting dashboard server stub on port 8000...")
    # Normally runs Flask/FastAPI, but for testing we can just run http.server or run it in background
    # Since dashboard is ran in tests, the E2E test runner will verify it starts.
    # To keep stub minimal, we parse port and start a simple server or loop.
    import time
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break

def main():
    parser = argparse.ArgumentParser(description="AI Trading Bot CLI")
    parser.add_argument("--mode", choices=["scan", "trade", "dashboard"], required=True, help="Mode to execute")
    args = parser.parse_args()
    
    if args.mode == "scan":
        mode_scan()
    elif args.mode == "trade":
        mode_trade()
    elif args.mode == "dashboard":
        mode_dashboard()

if __name__ == "__main__":
    main()
```

---

## 5. Verification & Test Execution Strategy
The test runner is configured to discover and execute E2E tests using `pytest`.

### Step-by-Step Test Execution Flow:
1. `pytest` loads `tests/e2e/conftest.py`.
2. The session-scoped `mock_servers` fixture launches the mock HTTP server (port 8001) and mock WebSocket server (port 8002).
3. The environment variables are set to force the client SDKs to redirect to `localhost:8001` and `localhost:8002`.
4. Prior to each test, the `clean_database` fixture sets up a pristine SQLite `test_trading.db` and resets order/position states on the mock server.
5. The test executes:
   - Evaluates outputs by executing `run_cli(["--mode", "scan"])` and checking the SQLite database.
   - Triggers dynamic mock conditions (e.g., mock failures) by sending a request to the `http://localhost:8001/mock_control` endpoint.
   - Assertions verify that the CLI outputs are stored, standard logs show correct flow, and exceptions are handled safely.
6. The test runner outputs execution statistics.
