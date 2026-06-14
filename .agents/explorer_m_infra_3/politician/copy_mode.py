import os
import requests

def get_politician_signals(ticker: str) -> dict:
    testing = os.getenv("TESTING", "false").lower() == "true"
    mock_url = os.getenv("POLITICIAN_API_URL")
    
    if testing and mock_url:
        try:
            r = requests.get(f"{mock_url}?ticker={ticker}", timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
            
    return {
        "ticker": ticker,
        "trades": [],
        "score": 0.0
    }
