import os
import json
import sqlite3
import requests
import logging
from pathlib import Path

logger = logging.getLogger("research_engine")

def _get_json_path() -> Path:
    """Helper to find/resolve morning_research.json in the project root."""
    try:
        project_root = Path(__file__).parent.parent.resolve()
        return project_root / "morning_research.json"
    except Exception:
        return Path("morning_research.json")

def run_morning_research(provider="openai", model="o3-mini") -> dict:
    """
    Executes deep research via AI reasoning model.
    Supports both 'openai' and 'gemini' providers.
    """
    logger.info(f"Running morning research via {provider} using model {model}")

    if provider == "openai":
        openai_base = os.environ.get("OPENAI_API_BASE")
        if openai_base:
            openai_base = openai_base.rstrip("/")
            if "v1/chat/completions" in openai_base:
                url = openai_base
            elif openai_base.endswith("/v1"):
                url = f"{openai_base}/chat/completions"
            else:
                url = f"{openai_base}/v1/chat/completions"
        else:
            url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Content-Type": "application/json"
        }
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Execute premarket deep research on macro outlook, VIX, sector trends, catalysts, and insider sentiment."}
            ]
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        content_str = data["choices"][0]["message"]["content"]
        
    elif provider == "gemini":
        # Map default model if provider is gemini and model is default o3-mini
        if model == "o3-mini":
            model = "gemini-2.0-flash-thinking"

        gemini_base = os.environ.get("GEMINI_API_BASE")
        if gemini_base:
            gemini_base = gemini_base.rstrip("/")
            if "generateContent" in gemini_base:
                url = gemini_base
            else:
                url = f"{gemini_base}/v1beta/models/{model}:generateContent"
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        headers = {
            "Content-Type": "application/json"
        }
        api_key = os.environ.get("GEMINI_API_KEY")
        params = {}
        if api_key:
            params["key"] = api_key

        payload = {
            "contents": [
                {"parts": [{"text": "Execute premarket deep research on macro outlook, VIX, sector trends, catalysts, and insider sentiment."}]}
            ]
        }

        response = requests.post(url, json=payload, headers=headers, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        content_str = data["candidates"][0]["content"]["parts"][0]["text"]
        
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    # Parse and clean the response content
    cleaned = content_str.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0] if "```" in cleaned else cleaned
        cleaned = cleaned.strip()
    
    research_data = json.loads(cleaned)
    if not isinstance(research_data, dict):
        raise ValueError("Research response is not a valid JSON object/dictionary.")

    # Save to morning_research.json
    json_path = _get_json_path()
    with open(json_path, "w") as f:
        json.dump(research_data, f, indent=2)

    # Save to SQLite database
    db_path = os.environ.get("DATABASE_PATH", "trading.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("morning_research", json.dumps(research_data)))
        conn.commit()
    finally:
        conn.close()

    return research_data

def get_today_research() -> dict:
    """
    Retrieves today's research findings from the file morning_research.json.
    Falls back to SQLite database (table settings, key 'morning_research').
    """
    # 1. Try to read from morning_research.json
    try:
        json_path = _get_json_path()
        if json_path.exists():
            with open(json_path, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception as e:
        logger.warning(f"Failed to read morning_research.json: {e}")

    # 2. Fallback to SQLite
    db_path = os.environ.get("DATABASE_PATH", "trading.db")
    try:
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", ("morning_research",))
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                if isinstance(data, dict):
                    return data
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to read from SQLite database: {e}")

    return {}
