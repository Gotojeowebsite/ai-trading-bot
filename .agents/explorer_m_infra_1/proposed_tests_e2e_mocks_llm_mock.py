import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingTCPServer

class LLMHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        body = json.loads(post_data.decode())

        # Check if it's OpenAI v1/chat/completions
        if "/v1/chat/completions" in self.path:
            # Check if model is gpt-4o
            model = body.get("model", "gpt-4o")
            # We can mock a decision response
            # Retrieve request text to see if there's any particular trigger
            messages = body.get("messages", [])
            prompt_content = ""
            for m in messages:
                if m.get("role") == "user":
                    prompt_content += m.get("content", "")

            # Default decision
            decision = {
                "action": "BUY",
                "confidence": 0.85,
                "entry_price": 150.0,
                "stop_loss": 145.0,
                "take_profit": 160.0,
                "position_size": 10,
                "reasoning": "Bullish signals and strong sentiment override other factors."
            }

            # We can customize the decision based on test triggers in the prompt content
            if "circuit breaker" in prompt_content.lower() or "losses" in prompt_content.lower():
                # Let's say if we want to test something else
                pass

            response = {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(decision)
                    },
                    "finish_reason": "stop"
                }]
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(response).encode())

        # Check if it's Gemini
        elif "gemini-2.0-flash" in self.path or "generateContent" in self.path:
            # Tier 1 screening score (0.0 to 1.0)
            score = "0.85"
            
            # Simple custom triggers
            contents = body.get("contents", [])
            prompt_text = ""
            for c in contents:
                for p in c.get("parts", []):
                    prompt_text += p.get("text", "")
            
            if "low-performing" in prompt_text.lower():
                score = "0.20"

            response = {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": score
                        }]
                    }
                }]
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(response).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "LLM path not mocked"}).encode())

class ThreadingHTTPServer(ThreadingTCPServer):
    allow_reuse_address = True

class LLMMockServer:
    def __init__(self, port=8003):
        self.port = port
        self.http_server = None

    def start(self):
        self.http_server = ThreadingHTTPServer(('127.0.0.1', self.port), LLMHTTPHandler)
        self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.http_thread.start()

    def stop(self):
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
