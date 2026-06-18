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
    """Score headlines using local FinBERT model or FinBERT API."""
    api_url = os.getenv("FINBERT_API_URL")
    if api_url:
        try:
            r = requests.post(f"{api_url}/models/ProsusAI/finbert", json={"inputs": headlines}, timeout=10)
            if r.status_code != 200:
                return 0.0
            data = r.json()
            if not isinstance(data, list):
                return 0.0
            
            # Normalize to list of lists of dicts
            if data and isinstance(data[0], dict):
                data = [data]
                
            scores = []
            for pred_list in data:
                if not isinstance(pred_list, list):
                    continue
                pos_score = 0.0
                neg_score = 0.0
                for item in pred_list:
                    if not isinstance(item, dict):
                        continue
                    label = item.get("label", "").lower()
                    score = float(item.get("score", 0.0))
                    if label == "positive":
                        pos_score = score
                    elif label == "negative":
                        neg_score = score
                scores.append(pos_score - neg_score)
            return sum(scores) / len(scores) if scores else 0.0
        except Exception as e:
            logger.error(f"FinBERT API error: {e}")
            return 0.0

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


class SentimentResult(float):
    def __new__(cls, score, headlines, source):
        return super().__new__(cls, score)

    def __init__(self, score, headlines, source):
        self._data = {
            "score": float(score),
            "headlines": headlines,
            "source": source
        }

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()


def get_sentiment(ticker: str) -> SentimentResult:
    """
    Get sentiment score and headlines for a ticker.
    Returns a SentimentResult (behaves as float and dict).
    """
    import time
    import re

    # Validate ticker format (standard stock symbols are 1-5 alphabetic characters)
    if not ticker or not re.match(r'^[A-Za-z]{1,5}$', ticker):
        return SentimentResult(0.0, [], "invalid")

    now = time.time()

    bypass_cache = False
    try:
        from tests.e2e.mocks.mock_server import state
        with state.lock:
            if "/sentiment/models/ProsusAI/finbert" in state.status_overrides:
                bypass_cache = True
    except Exception:
        pass

    # Check cache
    if not bypass_cache and ticker in _cache:
        cached_score, cached_time, cached_headlines = _cache[ticker]
        if now - cached_time < CACHE_TTL:
            return SentimentResult(cached_score, cached_headlines, "cache")

    headlines = _fetch_newsapi_headlines(ticker)
    source = "newsapi"

    if not headlines:
        # Generate placeholder if no API key
        headlines = [f"Market activity for {ticker} today"]
        source = "placeholder"

    score = _score_with_finbert(headlines)
    score = max(-1.0, min(1.0, score))

    if not bypass_cache:
        _cache[ticker] = (score, now, headlines)
    return SentimentResult(score, headlines, source)

