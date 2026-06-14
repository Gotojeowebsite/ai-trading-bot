import os
import requests
import json

def screen_ticker(ticker: str, data: dict) -> float:
    testing = os.getenv("TESTING", "false").lower() == "true"
    gemini_base = os.getenv("GEMINI_API_BASE_URL")
    
    if testing and gemini_base:
        try:
            r = requests.post(f"{gemini_base}/v1beta/models/gemini-2.0-flash:generateContent", json={"prompt": f"screen {ticker}"}, timeout=5)
            if r.status_code == 200:
                res = r.json()
                text = res["candidates"][0]["content"]["parts"][0]["text"]
                return float(text)
        except Exception:
            return 0.0
            
    # Default fallback
    return 0.5

def make_decision(ticker: str, data: dict) -> dict:
    testing = os.getenv("TESTING", "false").lower() == "true"
    openai_base = os.getenv("OPENAI_API_BASE_URL")
    
    if testing and openai_base:
        try:
            r = requests.post(f"{openai_base}/v1/chat/completions", json={"model": "gpt-4o", "messages": [{"role": "user", "content": f"decide {ticker}"}]}, timeout=5)
            if r.status_code == 200:
                res = r.json()
                content = res["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception:
            return {"action": "HOLD", "confidence": 0.0, "reasoning": "Fallback due to LLM API failure"}
            
    # Default fallback JSON decision
    return {
        "action": "HOLD",
        "confidence": 0.5,
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "position_size": 0,
        "reasoning": "Default stub decision"
    }
