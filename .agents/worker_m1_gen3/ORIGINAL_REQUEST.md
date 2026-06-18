## 2026-06-18T06:30:43Z
You are the Worker agent. Your working directory is /workspaces/ai-trading-bot/.agents/worker_m1_gen3.
Your parent is 810252a6-97bd-4ecf-9e29-13aae8c3ffe4.
Read /workspaces/ai-trading-bot/.agents/sub_orch_m1/SCOPE.md and /workspaces/ai-trading-bot/.agents/explorer_init_1/findings.md.
Do NOT follow the handoffs of explorer_m1_1/2/3 as they got confused by a different project state.
You must implement the following 8 tasks:

1. **Sentiment API Mismatch**: In `sentiment/finbert_client.py`, create a class `SentimentResult` that inherits from `float` and implements dict methods: `__getitem__`, `get`, `__contains__`, `keys`, `items`, `values` to act both as a float and as a dict with keys "score" (the float itself), "headlines" (list), and "source" (str). Modify `get_sentiment(ticker)` to return an instance of this `SentimentResult` class.
2. **Politician API Schema Mismatch**: In `politician/copy_mode.py`, modify `get_politician_signals(ticker, config)` to return a dictionary containing both the production keys ("composite_score", "trades", "direction") and the test-expected keys: "ticker" (set to ticker), "signal_score" (set to the composite score), and "trade_type" (set to "purchase" if the first trade is a purchase/buy, "sale" if sale, or "neutral" if no trades).
3. **Order Manager Demo Fallback**: In `tests/e2e/conftest.py`, inside the `mock_servers` fixture (around line 72), set `os.environ["ALPACA_API_KEY"] = "mock_key"` and `os.environ["ALPACA_SECRET_KEY"] = "mock_secret"` so the order manager does not fallback to demo mode.
4. **Settings DB Table**: In `automation/trading_loop.py` under `init_db`, also add creation of the `settings` table: `CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)` to ensure it is always initialized.
5. **Monkeypatch Namespace**: In `tests/e2e/test_tier1_feature.py` inside `test_sentiment_cache` (around line 147), change the monkeypatch target from `"sentiment.finbert_client.get_sentiment"` to `"tests.e2e.test_tier1_feature.get_sentiment"`.
6. **Context Window Overflow Syntax**: In `tests/e2e/test_tier2_boundary.py` inside `test_llm_context_window_overflow` (around line 258), change `{"indicators": {"vwap": 1.0} * 1000}` to `{"indicators": {f"vwap_{i}": 1.0 for i in range(1000)}}`.
7. **Port 8000 Conflict**: In `tests/e2e/conftest.py` inside `dashboard_server` fixture (around line 158), before starting the dashboard process, run a command or use Python to kill any process currently using port 8000 (e.g. running `subprocess.run(["fuser", "-k", "8000/tcp"], capture_output=True)`).
8. **Clean up requirements.txt**: Remove unused dependencies: `beautifulsoup4`, `aiohttp`, `apscheduler`, `websockets` from `/workspaces/ai-trading-bot/requirements.txt`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

After implementing the fixes, run all E2E and unit tests using `pytest` to verify that they all pass (you should have 80 passing tests).
Write your handoff report to /workspaces/ai-trading-bot/.agents/worker_m1_gen3/handoff.md and send a message back to the parent sub-orchestrator.
