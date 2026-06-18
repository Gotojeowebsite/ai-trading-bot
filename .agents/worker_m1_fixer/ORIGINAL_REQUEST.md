## 2026-06-18T15:19:44Z
You are a worker agent.
Your working directory is `/home/umanzor/ai-trading-bot/.agents/worker_m1_fixer`.
Please implement the following fixes in the codebase to resolve the 18 failing tests:

1. **Dashboard portfolio key mismatch**:
   In `/home/umanzor/ai-trading-bot/main.py` under `mode_dashboard()`'s GET handler for `/portfolio` or `/api/portfolio`, request both the Alpaca account AND positions:
   - Call `{api_url}/v2/account` and `{api_url}/v2/positions` (default to empty list if positions call fails).
   - Return a JSON dict in the format: `{"account": acct_data, "positions": positions_data}`.

2. **WebSocket 404 Route mismatch**:
   In `/home/umanzor/ai-trading-bot/main.py` under `mode_dashboard()`'s GET handler, support both `/ws/updates` and `/ws` as websocket paths (i.e. `if self.path in ("/ws/updates", "/ws"):`).

3. **Fallback news sentiment scoring mismatch**:
   In `/home/umanzor/ai-trading-bot/sentiment/finbert_client.py` inside `_score_with_finbert`, check if the environment variable `FINBERT_API_URL` is set:
   - If set, make a POST request to `f"{api_url}/models/ProsusAI/finbert"` with payload `{"inputs": headlines}`.
   - If the response status is 200, extract and average the sentiment scores (positive score minus negative score) and return. If not 200 (like 404), return `0.0`.
   - If `FINBERT_API_URL` is not set, proceed with the existing import and local pipeline logic.

4. **Politician Signal Recency Decay & CSV Loading**:
   In `/home/umanzor/ai-trading-bot/politician/copy_mode.py`:
   - In `_fetch_quiver_trades`, check if the environment variable `CONGRESS_DISCLOSURE_URL` is set. If set, make a GET request to that URL. Parse the returned CSV (it has headers: `DisclosureDate,FilerName,Ticker,TradeType,Amount,RecencyScore`). Map these to the Quiver Quantitative trade dictionary format (`Representative`, `Ticker`, `Transaction`, `Amount`, `TransactionDate`, and optionally include `RecencyScore` if present).
   - In `_compute_signal`, deduplicate the incoming trades based on `Representative`, `Ticker`, `Transaction`, `Amount`, and `TransactionDate`.
   - In `_compute_signal`, when calculating the signal contribution for each trade:
     - Bypass the date lookup skip if `"RecencyScore"` is present in the trade dictionary.
     - If `"RecencyScore"` is in the trade dictionary, use `float(trade["RecencyScore"])` as the signal contribution for that trade directly. Otherwise, compute the signal as usual.

5. **Scanner DST transition mixed timezone Index**:
   In `/home/umanzor/ai-trading-bot/automation/scanner.py` inside `scan_ticker`, convert the index of the retrieved historical DataFrame to a UTC localized `DatetimeIndex` before converting to EST:
   - Use `df.index = pd.to_datetime(df.index, utc=True)` right before `df_est = df.tz_convert('US/Eastern')`.

6. **Outage recovery ConnectionError**:
   In `/home/umanzor/ai-trading-bot/execution/order_manager.py` inside `AlpacaExecutor.place_bracket_order`, if `r.status_code == 503`, raise `ConnectionError(f"Alpaca API Outage: {r.status_code}")`. Ensure that this `ConnectionError` is not swallowed by general `except Exception` blocks (e.g. by adding `except ConnectionError as e: raise e` before `except Exception as e`).

After implementing these fixes, run the pytest suite using the project's virtual environment:
`PATH="/home/umanzor/ai-trading-bot/.venv/bin:$PATH" .venv/bin/pytest tests/`
Verify that all 112 tests pass (or 84 pass + 18 fixed + 10 skipped = 102 passing + 10 skipped).
Document your changes and the test command output in a handoff.md inside your working directory.

Mandatory integrity warning:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
