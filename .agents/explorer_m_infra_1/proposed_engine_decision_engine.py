import os
import json
import requests

def screen_ticker(ticker: str, data: dict) -> float:
    """
    Tier 1 screening score (0.0 to 1.0) using Gemini 2.0 Flash API (or local mock).
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    gemini_base_url = os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com")
    
    # Payload format for Gemini API
    url = f"{gemini_base_url}/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_api_key}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": f"Evaluate technical data for {ticker} and screen for potential buy opportunities. Return only a float score between 0.0 and 1.0. Data: {json.dumps(data)}"
            }]
        }]
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            res_json = response.json()
            # Parse Gemini response candidate text
            text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            score = float(text)
            return max(0.0, min(1.0, score))
        else:
            # Fallback on API failure
            return 0.5
    except Exception:
        # Fallback
        return 0.5

def make_decision(ticker: str, data: dict) -> dict:
    """
    Tier 2 premium decision using GPT-4o API (or local mock).
    Returns dict with keys: action (BUY/SELL/HOLD), confidence, entry_price, stop_loss, take_profit, position_size, reasoning.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    
    url = f"{openai_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional trading system decision agent. Output a JSON object containing: 'action' (BUY/SELL/HOLD), 'confidence' (0.0-1.0), 'entry_price' (float), 'stop_loss' (float), 'take_profit' (float), 'position_size' (integer number of shares), and 'reasoning' (text)."
            },
            {
                "role": "user",
                "content": f"Decide whether to trade ticker {ticker} given the combined signals: {json.dumps(data)}"
            }
        ],
        "response_format": {"type": "json_object"}
    }

    fallback_decision = {
        "action": "HOLD",
        "confidence": 0.0,
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "position_size": 0,
        "reasoning": "Fallback to HOLD due to LLM or processing error."
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            res_json = response.json()
            content = res_json["choices"][0]["message"]["content"].strip()
            decision = json.loads(content)
            
            # Post-processing validation
            action = decision.get("action", "HOLD").upper()
            if action not in ["BUY", "SELL", "HOLD"]:
                decision["action"] = "HOLD"
                
            # Stop loss boundary checks (e.g. stop loss below entry price for BUY)
            entry = float(decision.get("entry_price", 0.0))
            sl = float(decision.get("stop_loss", 0.0))
            tp = float(decision.get("take_profit", 0.0))
            
            if action == "BUY" and sl >= entry:
                # Override invalid stop loss
                decision["stop_loss"] = entry * 0.95
            if action == "BUY" and tp <= entry:
                decision["take_profit"] = entry * 1.05
                
            return decision
        else:
            return fallback_decision
    except Exception:
        return fallback_decision
