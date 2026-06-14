"""
Dashboard API Backend — FastAPI + WebSocket for real-time updates.
Serves the HTML dashboard and provides REST/WebSocket APIs.
"""
import os
import sys
import json
import sqlite3
import asyncio
import yaml
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from politician.copy_mode import get_all_recent_trades, get_politician_signals
from sentiment.finbert_client import get_sentiment

logger = logging.getLogger("dashboard")

app = FastAPI(title="AI Trading Bot Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# WebSocket clients
ws_clients = set()

def get_config():
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}

def get_db():
    config = get_config()
    db_path = config.get("database", {}).get("path", "trading.db")
    return sqlite3.connect(db_path)

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>Dashboard not found</h1>")

@app.get("/api/portfolio")
async def get_portfolio():
    try:
        from execution.order_manager import AlpacaExecutor
        config = get_config()
        executor = AlpacaExecutor(config)
        acct = executor.get_account()
        positions = executor.get_positions()
        return {"account": acct, "positions": positions}
    except Exception as e:
        return {"account": {"equity": "100000", "cash": "100000"}, "positions": [], "error": str(e)}

@app.get("/api/portfolio/history")
async def get_portfolio_history():
    db = get_db()
    try:
        rows = db.execute("SELECT equity, cash, daily_pnl, open_positions, timestamp FROM portfolio_snapshots ORDER BY id DESC LIMIT 500").fetchall()
        return [{"equity": r[0], "cash": r[1], "daily_pnl": r[2], "open_positions": r[3], "timestamp": r[4]} for r in rows]
    except:
        return []
    finally:
        db.close()

@app.get("/api/trades")
async def get_trades():
    db = get_db()
    try:
        rows = db.execute("SELECT id, ticker, action, qty, entry_price, stop_loss, take_profit, confidence, reasoning, timestamp, status FROM trades ORDER BY timestamp DESC LIMIT 50").fetchall()
        return [{"id": r[0], "ticker": r[1], "action": r[2], "qty": r[3], "entry_price": r[4], "stop_loss": r[5],
                 "take_profit": r[6], "confidence": r[7], "reasoning": r[8], "timestamp": r[9], "status": r[10]} for r in rows]
    except:
        return []
    finally:
        db.close()

@app.get("/api/decisions")
async def get_decisions():
    db = get_db()
    try:
        rows = db.execute("SELECT ticker, action, confidence, reasoning, timestamp FROM decisions ORDER BY id DESC LIMIT 30").fetchall()
        return [{"ticker": r[0], "action": r[1], "confidence": r[2], "reasoning": r[3], "timestamp": r[4]} for r in rows]
    except:
        return []
    finally:
        db.close()

@app.get("/api/signals")
async def get_signals():
    db = get_db()
    try:
        rows = db.execute("SELECT ticker, rsi, macd, vwap, rvol, sentiment, politician_score, composite, timestamp FROM signals").fetchall()
        return [{"ticker": r[0], "rsi": r[1], "macd": r[2], "vwap": r[3], "rvol": r[4], "sentiment": r[5],
                 "politician_score": r[6], "composite": r[7], "timestamp": r[8]} for r in rows]
    except:
        return []
    finally:
        db.close()

@app.get("/api/politicians")
async def get_politicians():
    try:
        trades = get_all_recent_trades()
        return trades
    except Exception as e:
        return []

@app.get("/api/config")
async def get_config_api():
    config = get_config()
    # Remove sensitive data
    safe = {k: v for k, v in config.items() if k not in ("llm",)}
    safe["llm"] = {"tier1_provider": config.get("llm", {}).get("tier1_provider"),
                   "tier2_provider": config.get("llm", {}).get("tier2_provider")}
    return safe

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            # Send periodic updates
            db = get_db()
            try:
                signals = db.execute("SELECT ticker, rsi, macd, vwap, rvol, sentiment, politician_score, composite FROM signals").fetchall()
                decisions = db.execute("SELECT ticker, action, confidence, reasoning, timestamp FROM decisions ORDER BY id DESC LIMIT 5").fetchall()

                data = {
                    "type": "update",
                    "signals": [{"ticker": s[0], "rsi": s[1], "macd": s[2], "vwap": s[3], "rvol": s[4],
                                 "sentiment": s[5], "politician": s[6], "composite": s[7]} for s in signals],
                    "decisions": [{"ticker": d[0], "action": d[1], "confidence": d[2], "reasoning": d[3],
                                   "timestamp": d[4]} for d in decisions],
                    "timestamp": datetime.now().isoformat(),
                }
                await ws.send_json(data)
            except:
                pass
            finally:
                db.close()
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        ws_clients.discard(ws)


def start_dashboard():
    config = get_config()
    host = config.get("dashboard", {}).get("host", "0.0.0.0")
    port = config.get("dashboard", {}).get("port", 8080)
    logger.info(f"Starting dashboard on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_dashboard()
