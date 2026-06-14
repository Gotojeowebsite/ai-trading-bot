"""
News Sentiment Engine using FinBERT or LLM fallback.
Fetches headlines from NewsAPI/Finnhub, scores them for financial sentiment.
"""
import os
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

logger = logging.getLogger("sentiment")

_cache: Dict[str, Tuple[float, float, List[str]]] = {}  # ticker -> (score, timestamp, headlines)
CACHE_TTL = 300  # 5 minutes


def _fetch_newsapi_headlines(ticker: str) -> List[str]:
    """Fetch headlines from NewsAPI.org."""
    api_key = os.getenv("NEWSAPI_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": ticker,
            "sortBy": "publishedAt",
            "pageSize": 10,
            "language": "en",
            "apiKey": api_key,
            "from": (datetime.utcnow() - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            articles = r.json().get("articles", [])
            return [a.get("title", "") for a in articles if a.get("title")]
    except Exception as e:
        logger.error(f"NewsAPI error for {ticker}: {e}")
    return []


def _score_with_finbert(headlines: List[str]) -> float:
    """Score headlines using local FinBERT model (if available)."""
    try:
        from transformers import pipeline
        classifier = pipeline("sentiment-analysis", model="ProsusAI/finbert", tokenizer="ProsusAI/finbert")
        scores = []
        for h in headlines[:10]:
            result = classifier(h[:512])[0]
            label = result["label"]
            conf = result["score"]
            if label == "positive":
                scores.append(conf)
            elif label == "negative":
                scores.append(-conf)
            else:
                scores.append(0.0)
        return sum(scores) / len(scores) if scores else 0.0
    except Exception as e:
        logger.warning(f"FinBERT not available ({e}), using simple keyword scoring")
        return _score_with_keywords(headlines)


def _score_with_keywords(headlines: List[str]) -> float:
    """Simple keyword-based sentiment fallback."""
    positive = {"surge", "jump", "soar", "rally", "beat", "upgrade", "bullish", "gain", "high", "record", "buy", "growth", "profit", "win", "deal"}
    negative = {"crash", "plunge", "drop", "fall", "miss", "downgrade", "bearish", "loss", "low", "sell", "decline", "warning", "risk", "cut", "layoff"}
    score = 0.0
    count = 0
    for h in headlines:
        words = set(h.lower().split())
        pos = len(words & positive)
        neg = len(words & negative)
        if pos or neg:
            score += (pos - neg) / max(pos + neg, 1)
            count += 1
    return score / max(count, 1)


def get_sentiment(ticker: str) -> Dict:
    """
    Get sentiment score and headlines for a ticker.
    Returns: {"score": float, "headlines": List[str], "source": str}
    """
    import time
    now = time.time()

    # Check cache
    if ticker in _cache:
        cached_score, cached_time, cached_headlines = _cache[ticker]
        if now - cached_time < CACHE_TTL:
            return {"score": cached_score, "headlines": cached_headlines, "source": "cache"}

    headlines = _fetch_newsapi_headlines(ticker)
    source = "newsapi"

    if not headlines:
        # Generate placeholder if no API key
        headlines = [f"Market activity for {ticker} today"]
        source = "placeholder"

    score = _score_with_finbert(headlines)
    score = max(-1.0, min(1.0, score))

    _cache[ticker] = (score, now, headlines)
    return {"score": score, "headlines": headlines, "source": source}
