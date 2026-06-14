import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingTCPServer

class FeedsHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_GET(self):
        # Mocking Congress disclosures (House Stock Watcher JSON)
        if "all_transactions.json" in self.path or "house_disclosures" in self.path:
            disclosures = [
                {
                    "disclosure_year": 2026,
                    "disclosure_date": "06/10/2026",
                    "transaction_date": "2026-06-08",
                    "owner": "self",
                    "ticker": "AAPL",
                    "asset_description": "Apple Inc. Common Stock",
                    "type": "purchase",
                    "amount": "$15,001 - $50,000",
                    "representative": "Nancy Pelosi",
                    "district": "CA-11"
                },
                {
                    "disclosure_year": 2026,
                    "disclosure_date": "06/12/2026",
                    "transaction_date": "2026-06-11",
                    "owner": "self",
                    "ticker": "MSFT",
                    "asset_description": "Microsoft Corp.",
                    "type": "purchase",
                    "amount": "$50,001 - $100,000",
                    "representative": "John Doe",
                    "district": "NY-02"
                }
            ]
            self._set_headers(200)
            self.wfile.write(json.dumps(disclosures).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Feeds path not mocked"}).encode())

    def do_POST(self):
        # If news/sentiment endpoint uses POST (e.g. mock FinBERT API)
        if "/models/ProsusAI/finbert" in self.path:
            # FinBERT usually returns logits or pipeline labels like positive/negative/neutral
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode())
            
            inputs = body.get("inputs", [])
            # Return high positive sentiment by default
            scores = [[
                {"label": "positive", "score": 0.9},
                {"label": "negative", "score": 0.05},
                {"label": "neutral", "score": 0.05}
            ]]
            
            self._set_headers(200)
            self.wfile.write(json.dumps(scores).encode())
        else:
            self._set_headers(404)

class ThreadingHTTPServer(ThreadingTCPServer):
    allow_reuse_address = True

class FeedsMockServer:
    def __init__(self, port=8004):
        self.port = port
        self.http_server = None

    def start(self):
        self.http_server = ThreadingHTTPServer(('127.0.0.1', self.port), FeedsHTTPHandler)
        self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.http_thread.start()

    def stop(self):
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
