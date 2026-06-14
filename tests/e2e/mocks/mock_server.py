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

        # Check delays
        delay = 0.0
        with state.lock:
            if self.path in state.response_delays:
                delay = state.response_delays[self.path]
        if delay > 0:
            time.sleep(delay)

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
        try:
            self.sock.close()
        except Exception:
            pass
        with state.lock:
            for client in self.clients:
                try:
                    client.close()
                except Exception:
                    pass
            self.clients.clear()
