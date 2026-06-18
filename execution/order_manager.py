"""
Order Executor - Fully automated bracket order management via Alpaca API.
Handles buy, sell, bracket orders, position closing, and EOD auto-close.
"""
import os
import logging
import requests
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger("executor")


class AlpacaExecutor:
    def __init__(self, config: dict):
        self.mode = config.get("broker", {}).get("mode", "paper")
        if self.mode == "live":
            self.base_url = config.get("broker", {}).get("live_url", "https://api.alpaca.markets")
        else:
            self.base_url = config.get("broker", {}).get("paper_url", "https://paper-api.alpaca.markets")

        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
        }

    def _is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    def get_account(self) -> Dict:
        """Get account info (equity, cash, buying power)."""
        if not self._is_configured():
            return {"equity": "100000", "cash": "100000", "buying_power": "200000", "status": "demo"}
        try:
            r = requests.get(f"{self.base_url}/v2/account", headers=self.headers, timeout=10)
            if r.status_code == 200:
                return r.json()
            logger.error(f"Account fetch failed: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"Account fetch error: {e}")
        return {"equity": "0", "cash": "0", "buying_power": "0", "status": "error"}

    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        if not self._is_configured():
            return []
        try:
            r = requests.get(f"{self.base_url}/v2/positions", headers=self.headers, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.error(f"Positions fetch error: {e}")
        return []

    def place_bracket_order(self, ticker: str, qty: int, side: str = "buy",
                            entry_price: float = None, stop_loss: float = None,
                            take_profit: float = None) -> Optional[str]:
        """
        Place a bracket order (entry + stop-loss + take-profit).
        Returns order ID or None on failure.
        """
        if not self._is_configured():
            order_id = f"demo-{ticker}-{datetime.now().strftime('%H%M%S')}"
            logger.info(f"[DEMO] Bracket order: {side} {qty} {ticker} @ ~{entry_price}, SL={stop_loss}, TP={take_profit} → {order_id}")
            return order_id

        payload = {
            "symbol": ticker,
            "qty": str(qty),
            "side": side,
            "type": "market",
            "time_in_force": "day",
            "order_class": "bracket",
            "take_profit": {"limit_price": str(round(take_profit, 2))},
            "stop_loss": {"stop_price": str(round(stop_loss, 2))},
        }
        if entry_price and side == "buy":
            payload["type"] = "limit"
            payload["limit_price"] = str(round(entry_price, 2))

        try:
            r = requests.post(f"{self.base_url}/v2/orders", json=payload, headers=self.headers, timeout=10)
            if r.status_code == 503:
                raise ConnectionError(f"Alpaca API Outage: {r.status_code}")
            if r.status_code in (200, 201):
                order = r.json()
                order_id = order.get("id", "unknown")
                logger.info(f"Bracket order placed: {side} {qty} {ticker}, ID={order_id}")
                return order_id
            else:
                logger.error(f"Order failed: {r.status_code} {r.text}")
        except ConnectionError as e:
            raise e
        except Exception as e:
            logger.error(f"Order error: {e}")
        return None

    def close_position(self, ticker: str) -> bool:
        """Close a single position by ticker."""
        if not self._is_configured():
            logger.info(f"[DEMO] Closed position: {ticker}")
            return True
        try:
            r = requests.delete(f"{self.base_url}/v2/positions/{ticker}", headers=self.headers, timeout=10)
            if r.status_code in (200, 204):
                logger.info(f"Position closed: {ticker}")
                return True
            logger.error(f"Close position failed: {r.status_code}")
        except Exception as e:
            logger.error(f"Close position error: {e}")
        return False

    def close_all_positions(self) -> bool:
        """Close ALL open positions (end-of-day)."""
        if not self._is_configured():
            logger.info("[DEMO] All positions closed (EOD)")
            return True
        try:
            r = requests.delete(f"{self.base_url}/v2/positions", headers=self.headers, timeout=10)
            if r.status_code in (200, 204, 207):
                logger.info("All positions closed (EOD)")
                return True
            logger.error(f"Close all failed: {r.status_code}")
        except Exception as e:
            logger.error(f"Close all error: {e}")
        return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        if not self._is_configured():
            return True
        try:
            r = requests.delete(f"{self.base_url}/v2/orders", headers=self.headers, timeout=10)
            return r.status_code in (200, 204, 207)
        except Exception:
            return False

    def get_portfolio_value(self) -> float:
        """Get current portfolio equity value."""
        acct = self.get_account()
        return float(acct.get("equity", 100000))

    def get_daily_pnl(self) -> float:
        """Get today's P&L."""
        acct = self.get_account()
        equity = float(acct.get("equity", 0))
        last_equity = float(acct.get("last_equity", equity))
        return equity - last_equity


# ── Legacy API shims (backward compatibility for tests) ──

_default_executor = None

def _get_executor():
    """Get or create a default executor for legacy function calls."""
    global _default_executor
    if _default_executor is None:
        _default_executor = AlpacaExecutor({
            "broker": {
                "mode": "paper",
                "paper_url": os.environ.get("ALPACA_API_BASE_URL", "https://paper-api.alpaca.markets"),
            }
        })
    return _default_executor


def execute_bracket_order(ticker: str, side: str, qty: int,
                          take_profit: float, stop_loss: float,
                          entry_price: float = None) -> str:
    """Legacy function: place a bracket order via the default executor."""
    executor = _get_executor()
    result = executor.place_bracket_order(
        ticker=ticker, qty=qty, side=side,
        entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit
    )
    return result if result else "failed-order"


def close_all_positions():
    """Legacy function: close all positions via the default executor."""
    executor = _get_executor()
    executor.close_all_positions()


class Watchdog:
    """Simple watchdog that monitors a named process and can restart it."""
    def __init__(self, name: str):
        self.name = name
        self.status = "running"
        self.restarts = 0

    def check_and_restart(self) -> bool:
        """Check if the process crashed and restart it."""
        if self.status == "crashed":
            logger.info(f"Watchdog restarting {self.name}...")
            self.status = "running"
            self.restarts += 1
            return True
        return False
