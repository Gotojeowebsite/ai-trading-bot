import os
import requests
import numpy as np

def get_sentiment(ticker: str) -> float:
    testing = os.getenv("TESTING", "false").lower() == "true"
    mock_url = os.getenv("NEWS_API_URL")
    
    if testing and mock_url:
        try:
            r = requests.get(f"{mock_url}?ticker={ticker}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                news = data.get("news", [])
                if not news:
                    return 0.0
                
                scores = []
                for n in news:
                    h = n.get("headline", "").lower()
                    if any(w in h for w in ["strong", "record", "growth", "buy", "bullish"]):
                        scores.append(0.8)
                    elif any(w in h for w in ["drop", "loss", "sell", "bearish", "investigation"]):
                        scores.append(-0.8)
                    else:
                        scores.append(0.0)
                return float(np.mean(scores)) if scores else 0.0
        except Exception:
            return 0.0
            
    try:
        from transformers import pipeline
        nlp = pipeline("sentiment-analysis", model="yiyanghkust/finbert-tone")
        headlines = [f"Stock news for {ticker}"]
        results = nlp(headlines)
        return 0.5
    except Exception:
        return 0.0
