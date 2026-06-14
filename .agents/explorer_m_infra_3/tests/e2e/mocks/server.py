import json
import time
import socket
import struct
import hashlib
import base64
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

MOCK_POSITIONS = []

class MockHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        global MOCK_POSITIONS
        
        # Alpaca WebSocket streaming endpoint
        if self.path.startswith("/stream"):
            self.handle_websocket()
            return

        # Alpaca REST API: Get Account details
        if self.path == "/alpaca/v2/account":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            acc = {
                "id": "mock-account-id",
                "account_number": "MOCK12345",
                "status": "ACTIVE",
                "currency": "USD",
                "buying_power": "400000.00",
                "cash": "100000.00",
                "portfolio_value": "100000.00",
                "pattern_day_trader": False,
                "trading_blocked": False,
                "transactable_by_authorized_user": True
            }
            self.wfile.write(json.dumps(acc).encode('utf-8'))
            return

        # Alpaca REST API: Get Positions
        if self.path == "/alpaca/v2/positions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(MOCK_POSITIONS).encode('utf-8'))
            return

        # Politician Signal Disclosures
        if self.path.startswith("/politician"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            signals = {
                "ticker": "AAPL",
                "trades": [
                    {
                        "representative": "Nancy Pelosi",
                        "transaction_date": "2026-06-10",
                        "disclosure_date": "2026-06-12",
                        "type": "purchase",
                        "amount_range": "$100,001 - $250,000",
                        "estimated_size": 175000,
                        "recency_weight": 0.9
                    }
                ],
                "score": 0.8
            }
            self.wfile.write(json.dumps(signals).encode('utf-8'))
            return

        # News/Sentiment API
        if self.path.startswith("/news"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            news = {
                "news": [
                    {"headline": "Apple reports record earnings and strong guidance", "source": "Reuters", "pub_date": "2026-06-13T12:00:00Z"},
                    {"headline": "Congressional trades show purchases of AAPL stock", "source": "CapitolTrades", "pub_date": "2026-06-12T10:00:00Z"}
                ]
            }
            self.wfile.write(json.dumps(news).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        global MOCK_POSITIONS
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        
        # OpenAI Chat Completions (GPT-4o Mock)
        if self.path == "/openai/v1/chat/completions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            decision_content = {
                "action": "BUY",
                "confidence": 0.85,
                "entry_price": 150.0,
                "stop_loss": 145.0,
                "take_profit": 160.0,
                "position_size": 10,
                "reasoning": "Strong technical breakout combined with positive senator buying and bullish news sentiment."
            }
            resp = {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4o",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(decision_content)
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
            }
            self.wfile.write(json.dumps(resp).encode('utf-8'))
            return

        # Gemini Model Content Generation (Gemini 2.0 Flash Mock)
        if self.path == "/gemini/v1beta/models/gemini-2.0-flash:generateContent":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "0.75"}]
                    },
                    "finishReason": "STOP"
                }]
            }
            self.wfile.write(json.dumps(resp).encode('utf-8'))
            return

        # Alpaca REST API: Place Order
        if self.path == "/alpaca/v2/orders":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                payload = json.loads(post_data.decode('utf-8'))
                ticker = payload.get("symbol", "AAPL")
                side = payload.get("side", "buy")
                qty = payload.get("qty", "10")
                
                order_id = f"order_{int(time.time())}"
                
                if side == "buy":
                    existing = next((p for p in MOCK_POSITIONS if p["symbol"] == ticker), None)
                    if existing:
                        existing["qty"] = str(int(existing["qty"]) + int(qty))
                    else:
                        MOCK_POSITIONS.append({
                            "asset_id": "904837e3-3b76-47b7-8d28-d17604f33b77",
                            "symbol": ticker,
                            "exchange": "NASDAQ",
                            "asset_class": "us_equity",
                            "avg_entry_price": "150.00",
                            "qty": str(qty),
                            "side": "long",
                            "market_value": str(150.0 * float(qty)),
                            "cost_basis": str(150.0 * float(qty)),
                            "unrealized_pl": "0.00",
                            "unrealized_plpc": "0.0000",
                            "current_price": "150.00"
                        })
                
                resp = {
                    "id": order_id,
                    "client_order_id": payload.get("client_order_id", "client-123"),
                    "created_at": "2026-06-14T08:34:34Z",
                    "symbol": ticker,
                    "qty": str(qty),
                    "filled_qty": str(qty),
                    "type": payload.get("type", "market"),
                    "side": side,
                    "status": "filled",
                    "legs": []
                }
                self.wfile.write(json.dumps(resp).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.wfile.write(str(e).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        global MOCK_POSITIONS
        
        # Alpaca REST API: Close All Positions
        if self.path == "/alpaca/v2/positions":
            MOCK_POSITIONS = []
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "All positions closed."}).encode('utf-8'))
            return
            
        self.send_response(404)
        self.end_headers()

    def handle_websocket(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_response(400)
            self.end_headers()
            return
        
        accept_val = (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode('utf-8')
        accept_key = base64.b64encode(hashlib.sha1(accept_val).digest()).decode('utf-8')
        
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept_key)
        self.end_headers()
        
        self.send_ws_frame('{"stream": "authorization", "data": {"status": "authorized"}}')
        
        while True:
            try:
                opcode, payload = self.recv_ws_frame()
                if opcode is None or opcode == 8:
                    break
                if opcode == 1:
                    msg = json.loads(payload.decode('utf-8'))
                    action = msg.get("action")
                    if action == "subscribe":
                        self.send_ws_frame(json.dumps({"stream": "listening", "data": {"streams": ["AM.AAPL"]}}))
                        mock_trade = {
                            "stream": "AM.AAPL",
                            "data": {
                                "ev": "AM",
                                "sym": "AAPL",
                                "v": 100,
                                "av": 50000,
                                "op": 150.0,
                                "vw": 150.5,
                                "c": 151.0,
                                "h": 152.0,
                                "l": 149.0,
                                "a": 150.8,
                                "s": 1781426074,
                                "e": 1781426074
                            }
                        }
                        self.send_ws_frame(json.dumps(mock_trade))
            except Exception:
                break

    def send_ws_frame(self, text):
        payload = text.encode('utf-8')
        header = bytearray()
        header.append(0x81)
        payload_len = len(payload)
        if payload_len <= 125:
            header.append(payload_len)
        elif payload_len <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", payload_len))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", payload_len))
        try:
            self.wfile.write(header + payload)
            self.wfile.flush()
        except Exception:
            pass

    def recv_ws_frame(self):
        try:
            data = self.rfile.read(2)
            if len(data) < 2:
                return None, None
            byte1, byte2 = data[0], data[1]
            opcode = byte1 & 0x0F
            masked = bool(byte2 & 0x80)
            payload_len = byte2 & 0x7F
            
            if payload_len == 126:
                len_bytes = self.rfile.read(2)
                payload_len = struct.unpack("!H", len_bytes)[0]
            elif payload_len == 127:
                len_bytes = self.rfile.read(8)
                payload_len = struct.unpack("!Q", len_bytes)[0]
                
            if masked:
                mask_key = self.rfile.read(4)
                
            payload = self.rfile.read(payload_len)
            if len(payload) < payload_len:
                return None, None
                
            if masked:
                unmasked = bytearray(payload_len)
                for i in range(payload_len):
                    unmasked[i] = payload[i] ^ mask_key[i % 4]
                payload = bytes(unmasked)
                
            return opcode, payload
        except Exception:
            return None, None

def start_mock_server(port):
    server = HTTPServer(("localhost", port), MockHTTPHandler)
    server.serve_forever()
