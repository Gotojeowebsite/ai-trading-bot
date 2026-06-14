import os
import json
import requests

def screen_ticker(ticker: str, data: dict) -> float:
    """
    Tier 1 screening score (0.0 to 1.0) using Gemini Mock API.
    """
    api_url = os.environ.get("GEMINI_API_BASE", "http://localhost:8001/gemini")
    try:
        payload = {"contents": [{"parts": [{"text": f"Screen {ticker} with data: {data}"}]}]}
        response = requests.post(f"{api_url}/v1beta/models/gemini-2.0-flash:generateContent", json=payload, timeout=5)
        if response.status_code == 200:
            val_str = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return float(val_str)
    except Exception:
        pass
    return 0.0

def make_decision(ticker: str, data: dict) -> dict:
    """
    Tier 2 premium JSON decision using OpenAI Mock API.
    Enforces risk boundary rules on the response.
    """
    api_url = os.environ.get("OPENAI_API_BASE", "http://localhost:8001/openai")
    fallback = {
        "action": "HOLD",
        "confidence": 0.0,
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "position_size": 0,
        "reasoning": "Fallback decision: Error or Timeout."
    }
    try:
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": f"Make decision for {ticker}"}]
        }
        response = requests.post(f"{api_url}/v1/chat/completions", json=payload, timeout=5)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            decision = json.loads(content)
            
            action = decision.get("action", "HOLD").upper()
            if action not in ["BUY", "SELL", "HOLD"]:
                action = "HOLD"
            decision["action"] = action
            
            # Check for empty reasoning
            if not decision.get("reasoning") or not str(decision["reasoning"]).strip():
                decision["action"] = "HOLD"
                decision["reasoning"] = "Overruled to HOLD: Missing reasoning."
                
            # Check for invalid stop loss boundary
            entry = float(decision.get("entry_price", 0.0))
            sl = float(decision.get("stop_loss", 0.0))
            tp = float(decision.get("take_profit", 0.0))
            if action == "BUY":
                if sl >= entry or tp <= entry:
                    decision["action"] = "HOLD"
                    decision["reasoning"] = f"Overruled to HOLD: Invalid stop-loss ({sl}) or take-profit ({tp}) relative to entry ({entry})."
            elif action == "SELL":
                if sl <= entry or tp >= entry:
                    decision["action"] = "HOLD"
                    decision["reasoning"] = f"Overruled to HOLD: Invalid stop-loss ({sl}) or take-profit ({tp}) relative to entry ({entry})."
                    
            return decision
    except Exception:
        pass
        
    return fallback

