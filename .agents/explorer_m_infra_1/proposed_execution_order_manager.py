import os
import requests
import sqlite3
import datetime

def get_alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.getenv("APCA_API_KEY_ID", ""),
        "APCA-API-SECRET-KEY": os.getenv("APCA_API_SECRET_KEY", ""),
        "Content-Type": "application/json"
    }

def execute_bracket_order(ticker: str, side: str, qty: int, take_profit: float, stop_loss: float) -> str:
    """
    Places entry, profit-taking, and stop-loss orders on Alpaca.
    Returns the entry order ID or empty string on failure.
    """
    base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
    url = f"{base_url}/v2/orders"
    
    headers = get_alpaca_headers()
    
    payload = {
        "symbol": ticker,
        "qty": str(qty),
        "side": side.lower(),
        "type": "market",
        "time_in_force": "day",
        "order_class": "bracket",
        "take_profit": {
            "limit_price": f"{take_profit:.2f}"
        },
        "stop_loss": {
            "stop_price": f"{stop_loss:.2f}"
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            order_data = response.json()
            order_id = order_data.get("id", "")
            
            # Log trade to SQLite
            db_path = os.getenv("DATABASE_URL", "sqlite:///trading.db").replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trade_logs (timestamp, ticker, action, qty, price, take_profit, stop_loss, reasoning, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.datetime.now().isoformat(),
                ticker,
                side.upper(),
                qty,
                0.0, # Filled price updated by websocket
                take_profit,
                stop_loss,
                "Executed bracket order",
                "submitted"
            ))
            conn.commit()
            conn.close()
            
            return order_id
        else:
            return ""
    except Exception:
        return ""

def close_all_positions() -> None:
    """
    Sends immediate market orders to close out all open holdings.
    """
    base_url = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
    url = f"{base_url}/v2/positions"
    
    headers = get_alpaca_headers()
    
    try:
        requests.delete(url, headers=headers, timeout=5)
        
        # Mark all logs as liquidated
        db_path = os.getenv("DATABASE_URL", "sqlite:///trading.db").replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE trade_logs SET status = 'liquidated' WHERE status = 'submitted'")
        conn.commit()
        conn.close()
    except Exception:
        pass
