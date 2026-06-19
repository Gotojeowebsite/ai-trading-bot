"""
Interactive Brokers Order Executor.
Handles portfolio retrieval, position query, order execution, and position closing.
"""
import os
import logging
import requests
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger("ib_executor")


class IBExecutor:
    def __init__(self, config: dict):
        self.config = config
        self.account_id = config.get("broker", {}).get("account_id", "U12345")
        
        # Determine ib_base_url
        if os.environ.get("OPENAI_API_BASE"):
            self.ib_base_url = "http://localhost:8001"
        else:
            self.ib_base_url = config.get("broker", {}).get("ib_base_url") or "https://localhost:5000/v1/api"
        
        # Check if ib_insync is available and try to connect
        try:
            import ib_insync
            self.has_ib_insync = True
        except ImportError:
            self.has_ib_insync = False
            
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.account_id}"
        }
        
        # Call placeholder connect method
        self.connect_ib_insync()

    def connect_ib_insync(self):
        """Placeholder method to connect to TWS using ib_insync if available."""
        if self.has_ib_insync:
            try:
                import ib_insync
                ib = ib_insync.IB()
                # Tries to connect to TWS on 127.0.0.1:7497
                ib.connect('127.0.0.1', 7497, clientId=1)
                logger.info("Connected to TWS via ib_insync successfully.")
                return ib
            except Exception as e:
                logger.debug(f"Failed to connect via ib_insync: {e}")
        else:
            logger.debug("ib_insync is not available.")
        return None

    def _is_configured(self) -> bool:
        return bool(self.account_id and not self.account_id.startswith("your_"))

    def get_account(self) -> Dict:
        """Get IB account info (equity, cash, buying power)."""
        try:
            url = f"{self.ib_base_url}/portfolio/{self.account_id}/meta"
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if "equity" in data:
                    data["equity"] = float(data["equity"])
                if "cash" in data:
                    data["cash"] = float(data["cash"])
                return data
            logger.error(f"IB Account fetch failed: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"IB Account fetch error: {e}")
        return {"equity": 0.0, "cash": 0.0, "buying_power": 0.0, "status": "error"}

    def get_positions(self) -> List[Dict]:
        """Get all open positions and map to standard formats."""
        try:
            url = f"{self.ib_base_url}/portfolio/{self.account_id}/positions"
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                positions = r.json()
                mapped = []
                for p in positions:
                    mapped.append({
                        "symbol": p.get("symbol", ""),
                        "qty": str(p.get("position", "0")),
                        "current_price": str(p.get("mktPrice", "0.0")),
                        "avg_entry_price": str(p.get("avgCost", "0.0"))
                    })
                return mapped
            logger.error(f"IB Positions fetch failed: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"IB Positions fetch error: {e}")
        return []

    def place_bracket_order(self, ticker: str, qty: int, side: str = "buy",
                             entry_price: float = None, stop_loss: float = None,
                             take_profit: float = None) -> Optional[str]:
        """
        Place a bracket order via IB Web API.
        Returns order ID or None on failure.
        """
        price = entry_price if entry_price else 150.0
        payload = {
            "symbol": ticker,
            "quantity": qty,
            "qty": qty,
            "side": side,
            "price": price,
            "limit_price": price,
            "type": "limit" if entry_price else "market",
            "orderType": "LMT" if entry_price else "MKT"
        }
        
        if take_profit:
            payload["take_profit"] = {"limit_price": str(round(take_profit, 2))}
        if stop_loss:
            payload["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}

        try:
            url = f"{self.ib_base_url}/iserver/account/{self.account_id}/orders"
            r = requests.post(url, json=payload, headers=self.headers, timeout=10)
            if r.status_code in (200, 201):
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    order_id = data[0].get("order_id")
                    logger.info(f"IB Bracket order placed: {side} {qty} {ticker}, ID={order_id}")
                    return order_id
                elif isinstance(data, dict):
                    order_id = data.get("order_id") or data.get("id")
                    logger.info(f"IB Bracket order placed: {side} {qty} {ticker}, ID={order_id}")
                    return order_id
            logger.error(f"IB Order failed: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"IB Order error: {e}")
        return None

    def close_position(self, ticker: str) -> bool:
        """Close a single position by ticker."""
        try:
            url1 = f"{self.ib_base_url}/portfolio/{self.account_id}/positions/{ticker}"
            url2 = f"{self.ib_base_url}/portfolio/{self.account_id}/position/{ticker}"
            r = requests.delete(url1, headers=self.headers, timeout=10)
            if r.status_code in (200, 204):
                logger.info(f"IB Position closed: {ticker}")
                return True
            r2 = requests.delete(url2, headers=self.headers, timeout=10)
            if r2.status_code in (200, 204):
                logger.info(f"IB Position closed: {ticker}")
                return True
            logger.error(f"IB Close position failed: {r.status_code} {r.text}")
        except Exception as e:
            logger.error(f"IB Close position error: {e}")
        return False

    def close_all_positions(self) -> bool:
        """Close ALL open positions."""
        try:
            url = f"{self.ib_base_url}/portfolio/{self.account_id}/positions"
            r = requests.delete(url, headers=self.headers, timeout=10)
            if r.status_code in (200, 204):
                logger.info("IB All positions closed")
                return True
            logger.error(f"IB Close all positions failed: {r.status_code}")
        except Exception as e:
            logger.error(f"IB Close all positions error: {e}")
        return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        try:
            url = f"{self.ib_base_url}/iserver/account/{self.account_id}/orders"
            r = requests.delete(url, headers=self.headers, timeout=10)
            if r.status_code in (200, 204):
                return True
            
            get_url = f"{self.ib_base_url}/iserver/account/{self.account_id}/orders"
            get_r = requests.get(get_url, headers=self.headers, timeout=10)
            if get_r.status_code == 200:
                orders = get_r.json()
                success = True
                for o in orders:
                    o_id = o.get("id") or o.get("order_id")
                    if o_id:
                        del_url = f"{self.ib_base_url}/iserver/account/{self.account_id}/order/{o_id}"
                        del_r = requests.delete(del_url, headers=self.headers, timeout=10)
                        if del_r.status_code not in (200, 204):
                            success = False
                return success
        except Exception as e:
            logger.error(f"IB Cancel all orders error: {e}")
        return False

    def get_portfolio_value(self) -> float:
        """Get current portfolio equity value."""
        acct = self.get_account()
        return float(acct.get("equity", 100000.0))

    def get_daily_pnl(self) -> float:
        """Get today's P&L."""
        acct = self.get_account()
        equity = float(acct.get("equity", 0))
        last_equity = float(acct.get("last_equity", equity))
        return equity - last_equity
