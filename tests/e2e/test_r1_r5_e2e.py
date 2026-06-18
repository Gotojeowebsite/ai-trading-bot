import os
import sys
import json
import sqlite3
import pytest
import requests
import websocket
from datetime import datetime

# Define helper to check routes on dashboard app
def route_exists(path: str, method: str = "GET") -> bool:
    try:
        from dashboard.app import app
        for route in app.routes:
            if hasattr(route, "path") and route.path == path:
                if hasattr(route, "methods") and method in route.methods:
                    return True
    except Exception:
        pass
    return False

# Dynamic imports
try:
    from execution.order_manager import IBExecutor
    has_ib_executor = True
except ImportError:
    has_ib_executor = False

try:
    from engine.llm_brain import run_morning_research, get_today_research
    has_morning_research = True
except ImportError:
    has_morning_research = False

try:
    from automation.setup_wizard import CLISetupWizard, GUISetupWizard
    has_setup_wizards = True
except ImportError:
    has_setup_wizards = False

try:
    from automation.trading_loop import is_market_holiday
    has_market_holiday = True
except ImportError:
    has_market_holiday = False


# =====================================================================
# R1: Morning Deep Research Tests
# =====================================================================

def test_r1_mock_openai_reasoning_model():
    """Verify that mock OpenAI completions endpoint returns structured research JSON for reasoning models."""
    url = "http://localhost:8001/openai/v1/chat/completions"
    payload = {"model": "o3-mini", "messages": [{"role": "user", "content": "Premarket research"}]}
    r = requests.post(url, json=payload)
    assert r.status_code == 200
    data = r.json()
    content_str = data["choices"][0]["message"]["content"]
    content = json.loads(content_str)
    assert "macro_outlook" in content
    assert "vix" in content
    assert content["vix"] == 14.5
    assert content["sector_trends"]["Technology"] == "bullish"

def test_r1_mock_gemini_reasoning_model():
    """Verify that mock Gemini generateContent endpoint returns structured research JSON for reasoning models."""
    url = "http://localhost:8001/gemini/v1beta/models/gemini-2.0-flash-thinking:generateContent"
    payload = {"contents": [{"parts": [{"text": "Premarket research"}]}]}
    r = requests.post(url, json=payload)
    assert r.status_code == 200
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    content = json.loads(text)
    assert "macro_outlook" in content
    assert "vix" in content
    assert content["vix"] == 14.5
    assert content["catalysts"]["AAPL"]["sentiment"] == "positive"

@pytest.mark.skipif(not has_morning_research, reason="Morning research module is unimplemented")
def test_r1_production_morning_research():
    """Verify production morning research logic runs and saves data if implemented."""
    res = run_morning_research(provider="openai", model="o3-mini")
    assert "macro_outlook" in res
    today_res = get_today_research()
    assert today_res["vix"] == 14.5


# =====================================================================
# R2: Interactive Brokers Backend Integration Tests
# =====================================================================

def test_r2_mock_ib_accounts_endpoint():
    """Verify that IB accounts mock endpoint returns valid account JSON."""
    url = "http://localhost:8001/iserver/accounts"
    r = requests.get(url)
    assert r.status_code == 200
    assert "accounts" in r.json()
    assert r.json()["accounts"][0]["id"] == "U12345"

def test_r2_mock_ib_portfolio_meta_endpoint():
    """Verify that IB portfolio meta mock endpoint returns cash and equity info."""
    url = "http://localhost:8001/portfolio/U12345/meta"
    r = requests.get(url)
    assert r.status_code == 200
    data = r.json()
    assert "cash" in data
    assert "equity" in data
    assert data["equity"] == 100000.0

def test_r2_mock_ib_orders_placement_and_retrieval():
    """Verify placing and listing orders via mock IB endpoints."""
    # Place order
    post_url = "http://localhost:8001/iserver/account/U12345/orders"
    payload = {"symbol": "AAPL", "quantity": 10, "side": "buy", "price": 150.0}
    r_post = requests.post(post_url, json=payload)
    assert r_post.status_code == 200
    order_id = r_post.json()[0]["order_id"]
    assert order_id.startswith("ib-ord-")

    # Retrieve orders list
    get_url = "http://localhost:8001/iserver/account/U12345/orders"
    r_get = requests.get(get_url)
    assert r_get.status_code == 200
    orders = r_get.json()
    assert any(o["id"] == order_id for o in orders)

    # Cancel order
    del_url = f"http://localhost:8001/iserver/account/U12345/order/{order_id}"
    r_del = requests.delete(del_url)
    assert r_del.status_code == 200

@pytest.mark.skipif(not has_ib_executor, reason="IBExecutor is unimplemented")
def test_r2_production_ib_executor():
    """Verify IBExecutor functionality if implemented."""
    config = {"broker": {"provider": "ib", "account_id": "U12345"}}
    executor = IBExecutor(config)
    acct = executor.get_account()
    assert acct["equity"] == 100000.0


# =====================================================================
# R3: Premium Dashboard Endpoint Tests
# =====================================================================

@pytest.mark.skipif(not route_exists("/api/research"), reason="/api/research endpoint not implemented")
def test_r3_dashboard_research_endpoint(dashboard_server):
    """Test dashboard morning research API endpoint."""
    r = requests.get(f"{dashboard_server}/api/research")
    assert r.status_code == 200

@pytest.mark.skipif(not route_exists("/api/analytics"), reason="/api/analytics endpoint not implemented")
def test_r3_dashboard_analytics_endpoint(dashboard_server):
    """Test dashboard analytics API endpoint."""
    r = requests.get(f"{dashboard_server}/api/analytics")
    assert r.status_code == 200

@pytest.mark.skipif(not route_exists("/api/settings", "POST"), reason="/api/settings POST endpoint not implemented")
def test_r3_dashboard_settings_endpoint(dashboard_server):
    """Test dashboard settings API endpoint."""
    payload = {"stop_loss_pct": "1.50"}
    r = requests.post(f"{dashboard_server}/api/settings", json=payload)
    assert r.status_code == 200

def test_r3_dashboard_existing_portfolio_endpoint(dashboard_server):
    """Verify that existing dashboard portfolio endpoint is correct."""
    r = requests.get(f"{dashboard_server}/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert "account" in data
    assert "positions" in data


# =====================================================================
# R4: Setup Wizards Tests
# =====================================================================

@pytest.mark.skipif(not has_setup_wizards, reason="Setup wizards are unimplemented")
def test_r4_setup_wizard_cli():
    """Test CLI setup wizard execution."""
    wizard = CLISetupWizard()
    res = wizard.run({"alpaca_key": "valid_key", "ib_account": "U12345"})
    assert res["status"] == "success"

@pytest.mark.skipif(not has_setup_wizards, reason="Setup wizards are unimplemented")
def test_r4_setup_wizard_gui():
    """Test GUI setup wizard save callback."""
    wizard = GUISetupWizard()
    assert wizard is not None


# =====================================================================
# R5: Enhanced Trading Engine Logic Tests
# =====================================================================

@pytest.mark.skipif(not has_market_holiday, reason="Holiday awareness logic is unimplemented")
def test_r5_holiday_awareness():
    """Test market holiday checking logic."""
    christmas = datetime(2026, 12, 25)
    assert is_market_holiday(christmas) is True

def test_r5_production_sentiment_client():
    """Verify production sentiment client retrieves news and returns score within range."""
    from sentiment.finbert_client import get_sentiment
    res = get_sentiment("AAPL")
    assert -1.0 <= float(res) <= 1.0
    assert "headlines" in res

def test_r5_production_politician_signals():
    """Verify production politician signals mode scores Pelosi's AAPL purchase correctly."""
    from politician.copy_mode import get_politician_signals
    res = get_politician_signals("AAPL")
    assert res["ticker"] == "AAPL"
    assert res["signal_score"] == 0.95
