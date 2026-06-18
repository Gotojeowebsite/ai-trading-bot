import json
import threading
import socket
import struct
import hashlib
import base64
import time
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

class MockIBSocketServer:
    """Simulates native TWS socket server (e.g., on port 7497) for ib_insync."""
    def __init__(self, host="127.0.0.1", port=7497):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = False

    def start(self):
        self.running = True
        try:
            self.sock.bind((self.host, self.port))
            self.sock.listen(5)
            threading.Thread(target=self._accept_loop, daemon=True).start()
        except Exception:
            pass

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, conn):
        try:
            # Read handshake request
            data = conn.recv(1024)
            if data:
                # Send server version and time
                conn.sendall(b"150\n20260618 06:30:56 EST\n")
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break
        except Exception:
            pass
        finally:
            conn.close()

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass


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

    def check_credentials(self):
        # 1. Alpaca header/param check
        apca_key = self.headers.get("APCA-API-KEY-ID") or self.headers.get("apca-api-key-id")
        path_lower = self.path.lower()
        if apca_key in ("invalid_key", "invalid_alpaca_key") or "invalid_key" in path_lower or "invalid_alpaca_key" in path_lower:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))
            return False

        # 2. IB credentials check
        ib_auth = self.headers.get("Authorization") or self.headers.get("authorization") or ""
        if "invalid_ib_account" in ib_auth or "invalid_ib_account" in path_lower or self.headers.get("invalid_ib_account"):
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Forbidden"}).encode("utf-8"))
            return False
        return True

    def do_POST(self):
        # Verify credentials first
        if not self.check_credentials():
            return

        # Check overrides
        with state.lock:
            if self.path in state.status_overrides:
                self.send_response(state.status_overrides[self.path])
                self.end_headers()
                return

        # Check delays
        delay = 0.0
        with state.lock:
            if self.path in state.response_delays:
                delay = state.response_delays[self.path]
        if delay > 0:
            time.sleep(delay)

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')

        # Mock Control Endpoint
        if self.path == "/mock_control":
            try:
                data = json.loads(post_data)
                with state.lock:
                    if "status_overrides" in data:
                        state.status_overrides.update(data["status_overrides"])
                    if "response_delays" in data:
                        state.response_delays.update(data["response_delays"])
                    if "reset" in data and data["reset"]:
                        state.status_overrides.clear()
                        state.response_delays.clear()
                        state.orders.clear()
                        state.positions.clear()
                        state.account_cash = 100000.0
                        state.account_equity = 100000.0
                self._send_json({"status": "success"})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        # Interactive Brokers Order Placement Mock
        if ("/iserver/account/" in self.path or "/ib/v1/api/iserver/account/" in self.path) and "/orders" in self.path:
            try:
                payload = json.loads(post_data)
                orders_list = payload.get("orders", [payload])
                responses = []
                for ord_item in orders_list:
                    symbol = ord_item.get("symbol") or ord_item.get("ticker") or "AAPL"
                    qty = int(ord_item.get("quantity") or ord_item.get("qty") or 0)
                    side = (ord_item.get("side") or "BUY").lower()
                    order_type = (ord_item.get("orderType") or ord_item.get("type") or "LMT").lower()
                    price = float(ord_item.get("price") or ord_item.get("limit_price") or 150.0)
                    
                    order_id = f"ib-ord-{len(state.orders) + 1}"
                    
                    order = {
                        "id": order_id,
                        "symbol": symbol,
                        "qty": str(qty),
                        "side": side,
                        "status": "filled",
                        "type": order_type,
                        "legs": []
                    }
                    
                    if side == "buy":
                        tp_price = price * 1.10
                        sl_price = price * 0.90
                        order["legs"] = [
                            {"id": f"{order_id}-tp", "side": "sell", "type": "limit", "limit_price": str(tp_price)},
                            {"id": f"{order_id}-sl", "side": "sell", "type": "stop", "stop_price": str(sl_price)}
                        ]
                    
                    with state.lock:
                        state.orders[order_id] = order
                        current_qty = int(state.positions.get(symbol, {}).get("qty", 0))
                        change = qty if side == "buy" else -qty
                        new_qty = current_qty + change
                        if new_qty == 0:
                            state.positions.pop(symbol, None)
                        else:
                            state.positions[symbol] = {
                                "symbol": symbol,
                                "qty": str(new_qty),
                                "avg_entry_price": str(price)
                            }
                    responses.append({"order_id": order_id, "order_status": "Submitted"})
                self._send_json(responses)
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        # Interactive Brokers Order Modification/Cancellation Mock
        if ("/iserver/account/" in self.path or "/ib/v1/api/iserver/account/" in self.path) and "/order/" in self.path:
            parts = self.path.split("/order/")
            if len(parts) > 1:
                order_id = parts[1]
                with state.lock:
                    if order_id in state.orders:
                        state.orders[order_id]["status"] = "Submitted"
                self._send_json({"order_id": order_id, "order_status": "Submitted"})
            else:
                self._send_json({"error": "orderId not provided"}, 400)
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
            try:
                payload = json.loads(post_data)
                model = payload.get("model", "")
            except Exception:
                model = ""

            research_data = {
                "macro_outlook": "Bullish macro backdrop. Tech sector leading.",
                "vix": 14.5,
                "sector_trends": {
                    "Technology": "bullish",
                    "Healthcare": "neutral",
                    "Energy": "bearish"
                },
                "catalysts": {
                    "AAPL": {"event": "Product release today at 10 AM", "sentiment": "positive"},
                    "TSLA": {"event": "Earnings release pre-market", "sentiment": "negative"}
                },
                "insider_sentiment": {
                    "AAPL": 0.85,
                    "TSLA": -0.40
                }
            }

            if any(term in model.lower() for term in ("o3-mini", "o1", "thinking", "deep")):
                response = {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(research_data)
                        }
                    }]
                }
            else:
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
            research_data = {
                "macro_outlook": "Bullish macro backdrop. Tech sector leading.",
                "vix": 14.5,
                "sector_trends": {
                    "Technology": "bullish",
                    "Healthcare": "neutral",
                    "Energy": "bearish"
                },
                "catalysts": {
                    "AAPL": {"event": "Product release today at 10 AM", "sentiment": "positive"},
                    "TSLA": {"event": "Earnings release pre-market", "sentiment": "negative"}
                },
                "insider_sentiment": {
                    "AAPL": 0.85,
                    "TSLA": -0.40
                }
            }

            if any(term in self.path.lower() for term in ("thinking", "deep", "thought")):
                response = {
                    "candidates": [{
                        "content": {
                            "parts": [{"text": json.dumps(research_data)}]
                        }
                    }]
                }
            else:
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
        # Verify credentials first
        if not self.check_credentials():
            return

        with state.lock:
            if self.path in state.status_overrides:
                self.send_response(state.status_overrides[self.path])
                self.end_headers()
                return

        # Check delays
        delay = 0.0
        with state.lock:
            if self.path in state.response_delays:
                delay = state.response_delays[self.path]
        if delay > 0:
            time.sleep(delay)

        # Interactive Brokers Accounts Mock
        if "/iserver/accounts" in self.path or "/ib/v1/api/iserver/accounts" in self.path:
            self._send_json({
                "accounts": [{"id": "U12345", "name": "Mock IB Account"}]
            })
            return

        # Interactive Brokers Portfolio Meta Mock
        if ("/portfolio/" in self.path or "/ib/v1/api/portfolio/" in self.path) and "/meta" in self.path:
            self._send_json({
                "cash": state.account_cash,
                "equity": state.account_equity,
                "buying_power": state.account_cash * 4
            })
            return

        # Interactive Brokers Portfolio Positions Mock
        if ("/portfolio/" in self.path or "/ib/v1/api/portfolio/" in self.path) and "/positions" in self.path:
            with state.lock:
                ib_positions = [
                    {
                        "symbol": pos["symbol"],
                        "position": float(pos["qty"]),
                        "mktPrice": float(pos.get("avg_entry_price", 150.0)),
                        "avgCost": float(pos.get("avg_entry_price", 150.0))
                    }
                    for pos in state.positions.values()
                ]
            self._send_json(ib_positions)
            return

        # Interactive Brokers Order List Mock
        if "/iserver/account/" in self.path and "/orders" in self.path:
            with state.lock:
                self._send_json(list(state.orders.values()))
            return

        # Interactive Brokers Get Order Status/Details Mock
        if "/iserver/account/" in self.path and "/order/" in self.path:
            parts = self.path.split("/order/")
            if len(parts) > 1:
                order_id = parts[1]
                with state.lock:
                    order = state.orders.get(order_id)
                if order:
                    self._send_json(order)
                else:
                    self._send_json({"error": "order not found"}, 404)
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
        # Verify credentials first
        if not self.check_credentials():
            return

        with state.lock:
            if self.path in state.status_overrides:
                self.send_response(state.status_overrides[self.path])
                self.end_headers()
                return

        # Check delays
        delay = 0.0
        with state.lock:
            if self.path in state.response_delays:
                delay = state.response_delays[self.path]
        if delay > 0:
            time.sleep(delay)

        # Interactive Brokers Order Cancel Mock
        if ("/iserver/account/" in self.path or "/ib/v1/api/iserver/account/" in self.path) and "/order/" in self.path:
            parts = self.path.split("/order/")
            if len(parts) > 1:
                order_id = parts[1]
                with state.lock:
                    if order_id in state.orders:
                        state.orders[order_id]["status"] = "Cancelled"
                        for leg in state.orders[order_id].get("legs", []):
                            leg_id = leg.get("id")
                            if leg_id in state.orders:
                                state.orders[leg_id]["status"] = "Cancelled"
                self._send_json({"status": "success"})
                return

        # Interactive Brokers Position Liquidation Mock
        if ("/portfolio/" in self.path or "/ib/v1/api/portfolio/" in self.path) and "/positions" in self.path:
            with state.lock:
                state.positions.clear()
            self._send_json({"status": "success"})
            return

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
        self.clients_lock = threading.Lock()

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
                lines = data.split("\r\n")
                key_line = [line for line in lines if line.lower().startswith("sec-websocket-key:")][0]
                key = key_line.split(":", 1)[1].strip()
                accept_key = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode('utf-8')).digest()).decode('utf-8')
                handshake = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    "Sec-WebSocket-Accept: " + accept_key + "\r\n\r\n"
                )
                conn.send(handshake.encode('utf-8'))
                
                # Keep client connection open to stream updates
                with self.clients_lock:
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
            with self.clients_lock:
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
        with self.clients_lock:
            clients_copy = list(self.clients)
        for client in clients_copy:
            try:
                client.sendall(frame)
            except Exception:
                pass

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
        with self.clients_lock:
            clients_copy = list(self.clients)
            self.clients.clear()
        for client in clients_copy:
            try:
                client.close()
            except Exception:
                pass
