import json
import socket
import threading
import base64
import hashlib
import struct
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingTCPServer

class AlpacaHTTPHandler(BaseHTTPRequestHandler):
    orders = []
    positions = []
    account_info = {
        "id": "mock-account-id",
        "account_number": "MOCK12345",
        "status": "ACTIVE",
        "currency": "USD",
        "buying_power": "400000.00",
        "cash": "100000.00",
        "portfolio_value": "100000.00"
    }
    realized_loss = 0.0
    loss_limit = 1000.0

    def log_message(self, format, *args):
        # Suppress logging to keep output clean during tests
        pass

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self):
        if self.path == "/v2/account":
            self._set_headers(200)
            self.wfile.write(json.dumps(self.account_info).encode())
        elif self.path == "/v2/orders":
            self._set_headers(200)
            self.wfile.write(json.dumps(self.orders).encode())
        elif self.path == "/v2/positions":
            self._set_headers(200)
            self.wfile.write(json.dumps(self.positions).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "not found"}).encode())

    def do_POST(self):
        if self.path == "/v2/orders":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode())

            # Create mock order
            order_id = f"order-{int(time.time())}"
            mock_order = {
                "id": order_id,
                "client_order_id": body.get("client_order_id", f"client-{order_id}"),
                "created_at": "2026-06-14T08:34:34Z",
                "updated_at": "2026-06-14T08:34:34Z",
                "submitted_at": "2026-06-14T08:34:34Z",
                "type": body.get("type", "market"),
                "side": body.get("side", "buy"),
                "qty": body.get("qty", "1"),
                "status": "accepted",
                "symbol": body.get("symbol"),
                "take_profit": body.get("take_profit"),
                "stop_loss": body.get("stop_loss")
            }
            self.orders.append(mock_order)

            # Update position (simplified for test verification)
            if body.get("side") == "buy":
                self.positions.append({
                    "symbol": body.get("symbol"),
                    "qty": body.get("qty", "1"),
                    "avg_entry_price": "150.00",
                    "side": "long"
                })

            self._set_headers(200)
            self.wfile.write(json.dumps(mock_order).encode())
        else:
            self._set_headers(404)

    def do_DELETE(self):
        if self.path == "/v2/positions":
            # Close all positions
            self.positions.clear()
            self._set_headers(200)
            self.wfile.write(json.dumps([]).encode())
        elif self.path.startswith("/v2/orders/"):
            # Cancel order
            order_id = self.path.split("/")[-1]
            self.orders = [o for o in self.orders if o["id"] != order_id]
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "canceled"}).encode())
        else:
            self._set_headers(404)

class ThreadingHTTPServer(ThreadingTCPServer):
    allow_reuse_address = True

class AlpacaMockWS:
    def __init__(self, host='127.0.0.1', port=8002):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = []
        self.running = False

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.sock.close()
        for c in self.clients:
            try:
                c.close()
            except:
                pass

    def _listen_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
                if self._handshake(conn):
                    client_thread = threading.Thread(target=self._client_handler, args=(conn,), daemon=True)
                    client_thread.start()
                    self.clients.append(conn)
            except Exception:
                break

    def _handshake(self, conn):
        try:
            data = conn.recv(1024).decode('utf-8')
            headers = {}
            for line in data.split('\r\n')[1:]:
                if ': ' in line:
                    k, v = line.split(': ', 1)
                    headers[k.lower()] = v
            key = headers.get('sec-websocket-key')
            if not key:
                return False
            guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            accept = base64.b64encode(hashlib.sha1((key + guid).encode('utf-8')).digest()).decode('utf-8')
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                "Sec-WebSocket-Accept: {}\r\n\r\n"
            ).format(accept)
            conn.sendall(response.encode('utf-8'))
            return True
        except Exception:
            return False

    def _client_handler(self, conn):
        # Send welcome message
        welcome = {"stream": "authorization", "data": {"status": "authorized"}}
        self._send_frame(conn, json.dumps(welcome))
        
        while self.running:
            try:
                # Basic WebSocket frame reading (minimal implementation)
                header = conn.recv(2)
                if not header:
                    break
                # Check for client messages if needed, otherwise just keep connection alive
            except Exception:
                break
        if conn in self.clients:
            self.clients.remove(conn)

    def _send_frame(self, conn, message):
        try:
            data = message.encode('utf-8')
            length = len(data)
            frame = bytearray()
            frame.append(0x81) # Fin + Text frame
            if length <= 125:
                frame.append(length)
            elif length <= 65535:
                frame.append(126)
                frame.extend(struct.pack("!H", length))
            else:
                frame.append(127)
                frame.extend(struct.pack("!Q", length))
            frame.extend(data)
            conn.sendall(frame)
        except Exception:
            pass

    def broadcast(self, message):
        for c in self.clients:
            self._send_frame(c, message)

class AlpacaMockServer:
    def __init__(self, http_port=8001, ws_port=8002):
        self.http_port = http_port
        self.ws_port = ws_port
        self.http_server = None
        self.ws_server = None

    def start(self):
        # Start REST API Server
        self.http_server = ThreadingHTTPServer(('127.0.0.1', self.http_port), AlpacaHTTPHandler)
        self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.http_thread.start()

        # Start WS Server
        self.ws_server = AlpacaMockWS('127.0.0.1', self.ws_port)
        self.ws_server.start()

    def stop(self):
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
        if self.ws_server:
            self.ws_server.stop()
