import os
import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from engine.research_engine import run_morning_research, get_today_research, _get_json_path

@pytest.fixture
def temp_env(tmp_path):
    """Setup temporary environment for testing database and JSON paths."""
    temp_json = tmp_path / "morning_research.json"
    temp_db = tmp_path / "test_trading.db"
    
    with patch("engine.research_engine._get_json_path", return_value=temp_json), \
         patch.dict(os.environ, {"DATABASE_PATH": str(temp_db)}):
        yield temp_json, temp_db

def test_get_today_research_from_file(temp_env):
    temp_json, temp_db = temp_env
    
    # Save a mock JSON file
    mock_data = {"macro_outlook": "Bullish", "vix": 12.0}
    with open(temp_json, "w") as f:
        json.dump(mock_data, f)
        
    res = get_today_research()
    assert res == mock_data

def test_get_today_research_fallback_sqlite(temp_env):
    temp_json, temp_db = temp_env
    
    # Ensure JSON file does not exist
    if temp_json.exists():
        temp_json.unlink()
        
    # Write to SQLite settings table
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    mock_data = {"macro_outlook": "Bearish", "vix": 22.5}
    cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("morning_research", json.dumps(mock_data)))
    conn.commit()
    conn.close()
    
    res = get_today_research()
    assert res == mock_data

def test_get_today_research_empty_fallback(temp_env):
    temp_json, temp_db = temp_env
    
    # Ensure JSON file does not exist
    if temp_json.exists():
        temp_json.unlink()
        
    # No DB file either
    if temp_db.exists():
        temp_db.unlink()
        
    res = get_today_research()
    assert res == {}

@patch("requests.post")
def test_run_morning_research_openai(mock_post, temp_env):
    temp_json, temp_db = temp_env
    
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": json.dumps({"macro_outlook": "Neutral", "vix": 15.0})
            }
        }]
    }
    mock_post.return_value = mock_response
    
    res = run_morning_research(provider="openai", model="o3-mini")
    
    # Check returned data
    assert res["macro_outlook"] == "Neutral"
    assert res["vix"] == 15.0
    
    # Check JSON file written
    assert temp_json.exists()
    with open(temp_json, "r") as f:
        saved_json = json.load(f)
    assert saved_json == res
    
    # Check DB settings updated
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", ("morning_research",))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert json.loads(row[0]) == res

@patch("requests.post")
def test_run_morning_research_gemini(mock_post, temp_env):
    temp_json, temp_db = temp_env
    
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": json.dumps({"macro_outlook": "Bullish", "vix": 13.5})}]
            }
        }]
    }
    mock_post.return_value = mock_response
    
    res = run_morning_research(provider="gemini", model="gemini-2.0-flash-thinking")
    
    assert res["macro_outlook"] == "Bullish"
    assert res["vix"] == 13.5
    
    # Check JSON file written
    assert temp_json.exists()
    
    # Check DB settings updated
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", ("morning_research",))
    row = cursor.fetchone()
    conn.close()
    assert row is not None

def test_run_morning_research_invalid_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        run_morning_research(provider="unsupported")
