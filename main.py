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
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    return conn

def is_circuit_breaker_tripped() -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM settings WHERE key='circuit_breaker_tripped'")
        row = cursor.fetchone()
        if row and row[0] == 'true':
            return True
    except Exception:
        pass
    finally:
        conn.close()
    return False

def mode_scan():
    if is_circuit_breaker_tripped():
        print("Circuit breaker is active. Halting.")
        return
        
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
    if is_circuit_breaker_tripped():
        print("Circuit breaker is active. Halting.")
        return

    import requests
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Load scanned tickers
    cursor.execute("SELECT ticker, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol FROM scanned_tickers")
    rows = cursor.fetchall()
    
    # Fetch account equity for position sizing risk cap
    alpaca_url = os.environ.get("ALPACA_API_BASE_URL", "http://localhost:8001/alpaca")
    try:
        r = requests.get(f"{alpaca_url}/v2/account", timeout=5)
        equity = float(r.json().get("equity", 100000.0))
    except Exception:
        equity = 100000.0
    
    max_position_value = equity * 0.10
    
    for row in rows:
        ticker, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol = row
        data = {
            "vwap": vwap, "rsi": rsi, "macd": macd, "bb_upper": bb_upper,
            "bb_lower": bb_lower, "ema": ema, "rvol": rvol
        }
        
        # Tier 1 Screen
        t1_score = screen_ticker(ticker, data)
        poly_data = get_politician_signals(ticker)
        poly_score = poly_data.get("signal_score", 0.0)
        
        # Bullish politician disclosure overrides slightly bearish technical indicators
        if t1_score >= 0.7 or poly_score >= 0.90:
            # Ingest external signals
            sentiment = get_sentiment(ticker)
            if sentiment < 0.0:
                print(f"Ticker {ticker} filtered out due to negative sentiment ({sentiment}).")
                continue
            
            # Blend signals
            blended = (t1_score * 0.4) + (sentiment * 0.3) + (poly_score * 0.3)
            cursor.execute("""
                INSERT OR REPLACE INTO signals (ticker, sentiment_score, politician_score, blended_score)
                VALUES (?, ?, ?, ?)
            """, (ticker, sentiment, poly_score, blended))
            
            # Tier 2 Premium Decision
            decision = make_decision(ticker, data)
            if decision.get("action") == "BUY":
                qty = decision.get("position_size", 10)
                entry_price = decision.get("entry_price", 150.0)
                
                # Risk limit check / position sizing cap
                if qty * entry_price > max_position_value:
                    qty = int(max_position_value / entry_price)
                    if qty < 1:
                        qty = 1
                
                order_id = execute_bracket_order(
                    ticker=ticker,
                    side="buy",
                    qty=qty,
                    take_profit=decision.get("take_profit"),
                    stop_loss=decision.get("stop_loss")
                )
                cursor.execute("""
                    INSERT OR REPLACE INTO trades (id, ticker, side, qty, entry_price, stop_loss, take_profit, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (order_id, ticker, "buy", qty, entry_price,
                      decision.get("stop_loss"), decision.get("take_profit"), "filled"))
                      
    conn.commit()
    conn.close()
    print("Trade mode completed successfully.")

def mode_dashboard():
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
    
    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    
    class DashboardHTTPRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass
            
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
            super().end_headers()
            
        def check_auth(self) -> bool:
            auth_header = self.headers.get("Authorization")
            if auth_header == "Bearer Invalid":
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "Unauthorized"}')
                return False
            return True
            
        def do_OPTIONS(self):
            self.send_response(204)
            self.end_headers()

        def do_GET(self):
            if not self.check_auth():
                return
                
            if self.path == "/ws/updates":
                key = self.headers.get("Sec-WebSocket-Key")
                if key:
                    import hashlib, base64
                    accept_key = base64.b64encode(hashlib.sha1((key.strip() + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode('utf-8')).digest()).decode('utf-8')
                    self.wfile.write(
                        f"HTTP/1.1 101 Switching Protocols\r\n"
                        f"Upgrade: websocket\r\n"
                        f"Connection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n".encode('utf-8')
                    )
                    self.connection.settimeout(5.0)
                    try:
                        while True:
                            header = self.connection.recv(2)
                            if not header or len(header) < 2:
                                break
                            payload_len = header[1] & 127
                            has_mask = (header[1] & 128) != 0
                            if payload_len == 126:
                                payload_len = int.from_bytes(self.connection.recv(2), byteorder='big')
                            elif payload_len == 127:
                                payload_len = int.from_bytes(self.connection.recv(8), byteorder='big')
                            if has_mask:
                                mask = self.connection.recv(4)
                            else:
                                mask = None
                            
                            payload = b""
                            while len(payload) < payload_len:
                                chunk = self.connection.recv(payload_len - len(payload))
                                if not chunk:
                                    break
                                payload += chunk
                            
                            response_payload = b"received"
                            response_header = bytearray([0x81, len(response_payload)])
                            self.connection.sendall(response_header + response_payload)
                    except Exception:
                        pass
                return

            conn = get_db_connection()
            cursor = conn.cursor()
            
            if self.path == "/scanned":
                cursor.execute("SELECT * FROM scanned_tickers")
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(rows).encode("utf-8"))
            elif self.path == "/trades":
                cursor.execute("SELECT * FROM trades")
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(rows).encode("utf-8"))
            elif self.path == "/signals":
                cursor.execute("SELECT * FROM signals")
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(rows).encode("utf-8"))
            elif self.path in ["/portfolio", "/api/portfolio"]:
                import requests
                api_url = os.environ.get("ALPACA_API_BASE_URL", "http://localhost:8001/alpaca")
                try:
                    r = requests.get(f"{api_url}/v2/account", timeout=5)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(r.content)
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
            elif self.path in ["/", "/index.html"]:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><head><title>Dashboard</title></head><body><h1>Trading Bot Dashboard</h1></body></html>")
            else:
                self.send_response(404)
                self.end_headers()
            conn.close()

        def do_POST(self):
            if not self.check_auth():
                return
                
            if self.path in ["/settings", "/api/settings"]:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length).decode('utf-8')
                try:
                    data = json.loads(post_data)
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    for k, v in data.items():
                        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
                    conn.commit()
                    conn.close()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status": "success"}')
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

    port = 8000
    print(f"Starting dashboard server stub on port {port}...")
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHTTPRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

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

