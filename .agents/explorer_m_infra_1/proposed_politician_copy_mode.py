import os
import requests
import datetime

def get_politician_signals(ticker: str) -> dict:
    """
    Returns latest congressional trade disclosures for the ticker, scored weight, and recency.
    Fetches disclosure files from the configured environment URL (points to local mock during test).
    """
    disclosures_url = os.getenv("CONGRESS_DISCLOSURES_URL", "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json")
    
    try:
        response = requests.get(disclosures_url, timeout=5)
        if response.status_code == 200:
            all_txs = response.json()
        else:
            all_txs = []
    except Exception:
        all_txs = []

    # Filter transactions for this ticker
    ticker_txs = [tx for tx in all_txs if tx.get("ticker") == ticker]

    if not ticker_txs:
        return {
            "ticker": ticker,
            "disclosures": [],
            "scored_weight": 0.0,
            "recency_days": 999
        }

    # Score disclosures based on size and recency
    scored_weight = 0.0
    recency_days = 999
    now = datetime.datetime.now().date()

    for tx in ticker_txs:
        # Parse transaction date
        try:
            tx_date = datetime.datetime.strptime(tx.get("transaction_date", ""), "%Y-%m-%d").date()
            days_ago = (now - tx_date).days
        except Exception:
            days_ago = 180 # Default to max lookback if missing/corrupt
            
        if days_ago < 0:
            # Future transaction date, reject or ignore
            continue
            
        recency_days = min(recency_days, days_ago)

        # Skip if older than lookback (e.g. 180 days)
        if days_ago > 180:
            continue

        # Score by amount
        amount_str = tx.get("amount", "")
        # E.g. "$15,001 - $50,000", "$50,000,000+"
        amount_val = 15000.0
        if "50,000,000" in amount_str:
            amount_val = 50000000.0
        elif "1,000,000" in amount_str:
            amount_val = 1000000.0
        elif "100,001" in amount_str:
            amount_val = 100000.0
        elif "50,001" in amount_str:
            amount_val = 50000.0
        
        # Recency decay (exponential or linear decay)
        decay = max(0.0, 1.0 - (days_ago / 180.0))
        
        # Transaction type multiplier (purchase is bullish, sale is bearish)
        tx_type = tx.get("type", "purchase").lower()
        if tx_type == "purchase":
            multiplier = 1.0
        elif tx_type == "sale":
            multiplier = -1.0
        else:
            multiplier = 0.0

        # Calculate score component
        size_score = min(10.0, amount_val / 50000.0) # Cap size score contribution
        scored_weight += size_score * decay * multiplier

    return {
        "ticker": ticker,
        "disclosures": ticker_txs,
        "scored_weight": float(scored_weight),
        "recency_days": int(recency_days)
    }
