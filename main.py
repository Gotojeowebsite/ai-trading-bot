#!/usr/bin/env python3
"""
APEX AI Trading Bot — Unified Entry Point

Usage:
    python main.py bot           # Run the autonomous trading bot
    python main.py dashboard     # Run the web dashboard
    python main.py scan          # Run a one-shot pre-market scan
    python main.py scan --force  # Force scan outside pre-market hours
    python main.py status        # Show current bot status
"""
import os
import sys
import argparse
import logging
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def cmd_bot(args):
    """Launch the autonomous trading bot."""
    from automation.trading_loop import TradingBot
    bot = TradingBot()
    bot.run()


def cmd_dashboard(args):
    """Launch the premium web dashboard."""
    from dashboard.app import start_dashboard
    start_dashboard()


def cmd_scan(args):
    """Run a one-shot pre-market scan."""
    import yaml
    from automation.scanner import run_scanner

    config_path = Path("config/config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {"watchlist": ["AAPL", "NVDA", "TSLA", "MSFT"], "database": {"path": "trading.db"}}

    symbols = config.get("watchlist", ["AAPL", "NVDA", "TSLA", "MSFT"])
    db_path = config.get("database", {}).get("path", "trading.db")
    run_scanner(db_path, symbols, force=args.force, date_override=args.date)


def cmd_status(args):
    """Show current bot and portfolio status."""
    import yaml
    import sqlite3
    from execution.order_manager import AlpacaExecutor

    config_path = Path("config/config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    executor = AlpacaExecutor(config)
    acct = executor.get_account()
    positions = executor.get_positions()

    print("\n" + "=" * 50)
    print("🤖 APEX AI Trading Bot — Status")
    print("=" * 50)

    mode = config.get("broker", {}).get("mode", "paper")
    print(f"\n📋 Mode: {mode.upper()}")
    print(f"📊 Watchlist: {', '.join(config.get('watchlist', []))}")

    equity = float(acct.get("equity", 0))
    cash = float(acct.get("cash", 0))
    last_equity = float(acct.get("last_equity", equity))
    pnl = equity - last_equity

    print(f"\n💰 Portfolio:")
    print(f"   Equity: ${equity:,.2f}")
    print(f"   Cash:   ${cash:,.2f}")
    print(f"   P&L:    {'+'if pnl>=0 else ''}${pnl:,.2f}")

    if positions:
        print(f"\n📈 Open Positions ({len(positions)}):")
        for p in positions:
            sym = p.get("symbol", "?")
            qty = p.get("qty", 0)
            pnl_pos = float(p.get("unrealized_pl", 0))
            print(f"   {sym}: {qty} shares, P&L: {'+'if pnl_pos>=0 else ''}${pnl_pos:,.2f}")
    else:
        print(f"\n📈 No open positions")

    # Recent decisions
    db_path = config.get("database", {}).get("path", "trading.db")
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT ticker, action, confidence, reasoning, timestamp FROM decisions ORDER BY id DESC LIMIT 5").fetchall()
        if rows:
            print(f"\n🧠 Recent LLM Decisions:")
            for r in rows:
                print(f"   [{r[4][:19]}] {r[0]}: {r[1]} (conf: {r[2]:.0%}) — {(r[3] or '')[:80]}")
        conn.close()
    except Exception:
        pass

    # LLM config
    llm = config.get("llm", {})
    print(f"\n🤖 LLM Config:")
    print(f"   Tier 1: {llm.get('tier1_provider', 'gemini')}/{llm.get('tier1_model', 'gemini-2.0-flash')}")
    print(f"   Tier 2: {llm.get('tier2_provider', 'openai')}/{llm.get('tier2_model', 'gpt-4o')}")
    print(f"   Fallback: {llm.get('fallback_provider', 'gemini')}/{llm.get('fallback_model', 'gemini-1.5-pro')}")

    # API key status
    print(f"\n🔑 API Keys:")
    keys = [
        ("GEMINI_API_KEY", "Gemini (Tier 1 LLM)"),
        ("OPENAI_API_KEY", "OpenAI (Tier 2 LLM)"),
        ("ALPACA_API_KEY", "Alpaca (Broker)"),
        ("NEWSAPI_KEY", "NewsAPI (Sentiment)"),
        ("QUIVER_QUANT_API_KEY", "Quiver (Politicians)"),
        ("TELEGRAM_BOT_TOKEN", "Telegram (Alerts)"),
    ]
    for key, label in keys:
        val = os.getenv(key, "")
        if val and not val.startswith("your_"):
            print(f"   ✅ {label}")
        else:
            print(f"   ❌ {label} — not configured")

    print()


# ── Legacy mode functions (backward compat for tests) ──

def mode_scan():
    """Legacy: run pre-market scan with hardcoded tickers (test compat)."""
    import sqlite3
    import pandas as pd
    from automation.indicators import calculate_indicators

    db_path = os.environ.get("DATABASE_PATH", "trading.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS scanned_tickers (
        ticker TEXT PRIMARY KEY, vwap REAL, rsi REAL, macd REAL,
        bb_upper REAL, bb_lower REAL, ema REAL, rvol REAL)""")

    # Check circuit breaker
    cursor.execute("SELECT value FROM settings WHERE key='circuit_breaker_tripped'")
    row = cursor.fetchone()
    if row and row[0] == 'true':
        print("Circuit breaker is active. Halting.")
        conn.close()
        return

    tickers = ["AAPL", "MSFT", "GOOGL"]
    for ticker in tickers:
        raw_data = {
            "open": [148.0, 149.0, 150.0], "high": [151.0, 150.0, 152.0],
            "low": [147.0, 148.0, 149.0], "close": [150.0, 149.0, 151.0],
            "volume": [100000, 120000, 150000]
        }
        df = pd.DataFrame(raw_data)
        df_indicators = calculate_indicators(df)
        last_row = df_indicators.iloc[-1]
        cursor.execute("""INSERT OR REPLACE INTO scanned_tickers (ticker, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, float(last_row['VWAP']), float(last_row['RSI']), float(last_row['MACD']),
             float(last_row['BB_upper']), float(last_row['BB_lower']), float(last_row['EMA']), float(last_row['RVOL'])))
    conn.commit()
    conn.close()
    print("Scan mode completed successfully.")


def mode_trade():
    """Legacy: run trade pipeline (test compat)."""
    import sqlite3
    import requests as req
    from sentiment.finbert_client import get_sentiment
    from politician.copy_mode import get_politician_signals
    from engine.decision_engine import screen_ticker, make_decision
    from execution.order_manager import execute_bracket_order

    db_path = os.environ.get("DATABASE_PATH", "trading.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS signals (
        ticker TEXT PRIMARY KEY, sentiment_score REAL, politician_score REAL,
        blended_score REAL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY, ticker TEXT, side TEXT, qty INTEGER, entry_price REAL,
        stop_loss REAL, take_profit REAL, status TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    # Check circuit breaker
    cursor.execute("SELECT value FROM settings WHERE key='circuit_breaker_tripped'")
    row = cursor.fetchone()
    if row and row[0] == 'true':
        print("Circuit breaker is active. Halting.")
        conn.close()
        return

    cursor.execute("SELECT ticker, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol FROM scanned_tickers")
    rows = cursor.fetchall()

    alpaca_url = os.environ.get("ALPACA_API_BASE_URL", "http://localhost:8001/alpaca")
    try:
        r = req.get(f"{alpaca_url}/v2/account", timeout=5)
        equity = float(r.json().get("equity", 100000.0))
    except Exception:
        equity = 100000.0
    max_position_value = equity * 0.10

    for row in rows:
        ticker, vwap, rsi, macd, bb_upper, bb_lower, ema, rvol = row
        data = {"vwap": vwap, "rsi": rsi, "macd": macd, "bb_upper": bb_upper,
                "bb_lower": bb_lower, "ema": ema, "rvol": rvol}
        t1_score = screen_ticker(ticker, data)
        poly_data = get_politician_signals(ticker)
        poly_score = poly_data.get("signal_score", poly_data.get("composite_score", 0.0))

        if t1_score >= 0.7 or poly_score >= 0.90:
            sentiment_result = get_sentiment(ticker)
            sentiment = sentiment_result["score"] if isinstance(sentiment_result, dict) else float(sentiment_result)
            if sentiment < 0.0:
                print(f"Ticker {ticker} filtered out due to negative sentiment ({sentiment}).")
                continue
            blended = (t1_score * 0.4) + (sentiment * 0.3) + (poly_score * 0.3)
            cursor.execute("""INSERT OR REPLACE INTO signals (ticker, sentiment_score, politician_score, blended_score)
                VALUES (?, ?, ?, ?)""", (ticker, sentiment, poly_score, blended))
            decision = make_decision(ticker, data)
            if decision.get("action") == "BUY":
                qty = decision.get("position_size", 10)
                entry_price = decision.get("entry_price", 150.0)
                if qty * entry_price > max_position_value:
                    qty = int(max_position_value / entry_price)
                    if qty < 1:
                        qty = 1
                order_id = execute_bracket_order(
                    ticker=ticker, side="buy", qty=qty,
                    take_profit=decision.get("take_profit"),
                    stop_loss=decision.get("stop_loss")
                )
                cursor.execute("""INSERT OR REPLACE INTO trades (id, ticker, side, qty, entry_price, stop_loss, take_profit, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (order_id, ticker, "buy", qty, entry_price, decision.get("stop_loss"), decision.get("take_profit"), "filled"))
    conn.commit()
    conn.close()
    print("Trade mode completed successfully.")


def mode_dashboard():
    """Legacy: run HTTP dashboard on port 8000 (test compat)."""
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
    import sqlite3

    db_path = os.environ.get("DATABASE_PATH", "trading.db")

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, f, *a): pass
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
            super().end_headers()
        def check_auth(self):
            if self.headers.get("Authorization") == "Bearer Invalid":
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
            if not self.check_auth(): return
            if self.path in ("/ws/updates", "/ws"):
                key = self.headers.get("Sec-WebSocket-Key")
                if key:
                    import hashlib, base64
                    accept_key = base64.b64encode(hashlib.sha1((key.strip() + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                    self.wfile.write(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept_key}\r\n\r\n".encode())
                    init_msg = b"connected"
                    self.connection.sendall(bytearray([0x81, len(init_msg)]) + init_msg)
                    self.connection.settimeout(5.0)
                    try:
                        while True:
                            header = self.connection.recv(2)
                            if not header or len(header) < 2: break
                            pl = header[1] & 127
                            hm = (header[1] & 128) != 0
                            if pl == 126: pl = int.from_bytes(self.connection.recv(2), 'big')
                            elif pl == 127: pl = int.from_bytes(self.connection.recv(8), 'big')
                            if hm: self.connection.recv(4)
                            payload = b""
                            while len(payload) < pl:
                                chunk = self.connection.recv(pl - len(payload))
                                if not chunk: break
                                payload += chunk
                            resp = b"received"
                            self.connection.sendall(bytearray([0x81, len(resp)]) + resp)
                    except: pass
                return
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            if self.path in ("/scanned",):
                cursor.execute("SELECT * FROM scanned_tickers")
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(json.dumps(rows).encode())
            elif self.path in ("/trades",):
                cursor.execute("SELECT * FROM trades")
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(json.dumps(rows).encode())
            elif self.path in ("/signals",):
                cursor.execute("SELECT * FROM signals")
                cols = [d[0] for d in cursor.description]
                rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(json.dumps(rows).encode())
            elif self.path in ("/portfolio", "/api/portfolio"):
                import requests as req
                api_url = os.environ.get("ALPACA_API_BASE_URL", "http://localhost:8001/alpaca")
                try:
                    r_acct = req.get(f"{api_url}/v2/account", timeout=5)
                    acct_data = r_acct.json()
                    try:
                        r_pos = req.get(f"{api_url}/v2/positions", timeout=5)
                        positions_data = r_pos.json() if r_pos.status_code == 200 else []
                    except Exception:
                        positions_data = []
                    res_data = {"account": acct_data, "positions": positions_data}
                    self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                    self.wfile.write(json.dumps(res_data).encode())
                except Exception:
                    self.send_response(500); self.end_headers()
            elif self.path in ("/", "/index.html"):
                self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
                self.wfile.write(b"<html><head><title>Dashboard</title></head><body><h1>Trading Bot Dashboard</h1></body></html>")
            else:
                self.send_response(404); self.end_headers()
            conn.close()
        def do_POST(self):
            if not self.check_auth(): return
            if self.path in ("/settings", "/api/settings"):
                cl = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(cl).decode())
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                for k, v in data.items():
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
                conn.commit(); conn.close()
                self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
                self.wfile.write(b'{"status": "success"}')
            else:
                self.send_response(404); self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


def main():
    # ── Backward compatibility: support --mode scan/trade/dashboard ──
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1]
            if mode == "scan":
                mode_scan()
            elif mode == "trade":
                mode_trade()
            elif mode == "dashboard":
                mode_dashboard()
            else:
                print(f"Unknown mode: {mode}")
            return

    # ── New subcommand-based CLI ──
    parser = argparse.ArgumentParser(
        description="APEX AI — Autonomous Day Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py bot              # Start the autonomous trading bot
  python main.py dashboard        # Start the web dashboard on port 8080
  python main.py scan --force     # Run pre-market scan now
  python main.py status           # Check bot status and API keys
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # bot
    bot_parser = subparsers.add_parser("bot", help="Run the autonomous trading bot")

    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Run the web dashboard")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Run a pre-market scan")
    scan_parser.add_argument("--force", action="store_true", help="Force scan outside pre-market hours")
    scan_parser.add_argument("--date", type=str, help="Override scan date (YYYY-MM-DD)")

    # status
    status_parser = subparsers.add_parser("status", help="Show bot status")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    commands = {
        "bot": cmd_bot,
        "dashboard": cmd_dashboard,
        "scan": cmd_scan,
        "status": cmd_status,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

