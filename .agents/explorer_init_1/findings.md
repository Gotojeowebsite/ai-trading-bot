# APEX AI Trading Bot — Baseline Exploration Findings

## 1. Sentiment Engine (`sentiment/finbert_client.py`)
- **Module Purpose**: News Sentiment Engine using FinBERT local model or a fallback keyword-based scoring mechanism.
- **`get_sentiment` Signature**: `get_sentiment(ticker: str) -> Dict`
- **Return Type & Structure**: Returns a dictionary representing the score, headlines fetched, and the data source:
  ```python
  {
      "score": float,       # Normalized to [-1.0, 1.0]
      "headlines": List[str], # Headlines fetched from NewsAPI or placeholder
      "source": str         # e.g., "newsapi", "cache", or "placeholder"
  }
  ```
- **Test Mismatch**: In `tests/e2e/test_tier1_feature.py` (lines 110, 118, 126, 132), tests expect `get_sentiment` to return a `float` directly (e.g., `score = get_sentiment("AAPL"); assert score == pytest.approx(0.85)`). This contract mismatch causes test failures.

---

## 2. Politician Trade Tracker (`politician/copy_mode.py`)
- **Module Purpose**: Congressional stock disclosure tracker that fetches trade data from Quiver Quantitative API or demo trades and scores politicians based on historical alpha weights.
- **`get_politician_signals` Signature**: `get_politician_signals(ticker: str, config: dict = None) -> Dict`
- **Return Type & Structure**: Returns a dictionary containing composite scores and trade details:
  ```python
  {
      "composite_score": float,  # Normalized to [-1.0, 1.0], rounded to 3 decimal places
      "trade_count": int,        # Count of contributing trades in lookback window
      "trades": List[dict],      # List of trade details (name, action, amount, date, etc.)
      "direction": str           # "BULLISH" | "BEARISH" | "NEUTRAL"
  }
  ```
- **Test Mismatch**: In `tests/e2e/test_tier1_feature.py` (lines 161, 169, 192, 198), tests expect the returned dict to conform to a different schema:
  - `data["ticker"]`
  - `data["signal_score"]`
  - `data["trade_type"]`
  Since these keys are absent in the production code, tests raise `KeyError`.

---

## 3. Order Manager (`execution/order_manager.py`)
- **Module Purpose**: Fully automated bracket order placement, position closing, and EOD auto-close via the Alpaca API.
- **`execute_bracket_order` Signature**: 
  `execute_bracket_order(ticker: str, side: str, qty: int, take_profit: float, stop_loss: float, entry_price: float = None) -> str`
- **Demo Mode Bypass Investigation**:
  - Does it bypass demo mode? **No, it does not bypass demo mode.**
  - **Mechanism**:
    - `execute_bracket_order` instantiates or fetches a default executor using `_get_executor()`.
    - In `AlpacaExecutor.place_bracket_order`, it checks `self._is_configured()`.
    - `_is_configured()` returns `True` only if `ALPACA_API_KEY` is present in the environment and does not start with `"your_"`.
    - If `_is_configured()` is `False`, the executor enters the **demo branch** (returning a mock order ID prefixed with `"demo-"` and logging the trade without hitting any external API or mock server).
    - **Why this causes test failure**: The test environment configures a mock server base URL override (`ALPACA_API_BASE_URL = "http://localhost:8001/alpaca"`) in `tests/e2e/conftest.py` but does not populate `ALPACA_API_KEY`. As a result, the code falls back to returning `"demo-..."` instead of posting to the mock server and receiving an `"ord-..."` ID. The test assertion `assert order_id.startswith("ord-")` fails.

---

## 4. Macro Context Signal (`config/config.yaml`)
- **Configuration**: `macro_context` is configured in `config/config.yaml` on line 35 under `weights`:
  ```yaml
  weights:
    ...
    macro_context: 0.10
  ```
- **Why it is not computed**:
  - The trading loop (`automation/trading_loop.py`) only fetches `get_market_data` (technical indicators), `get_sentiment` (news), and `get_politician_signals` (congressional copying) within its cycles.
  - There is no calculation logic or helper module in the codebase designed to fetch macro market stats (e.g., indices, VIX, bond yields, or sector rotations).
  - The SQLite table definition for `signals` in `init_db` lacks a column for storing `macro_context`.
  - The Tier 1 and Tier 2 LLM prompts in `engine/llm_brain.py` do not accept, reference, or prompt for any macro context metrics.

---

## 5. Test Suite Failures & Diagnostics
- **Test Structure**:
  - **Unit Tests (`tests/unit/`)**: 3 files with 14 tests covering indicators math, data client thread-safety/callbacks, and scanner filters/nan handling.
  - **E2E Tests (`tests/e2e/`)**: 5 files with 71 tests validating system behaviors, LLM boundary scenarios, execution limits, and websocket updates.
- **Failures**: Running `pytest tests/` fails on 9 test cases with exit code 1.
- **Root Causes**:
  1. **Sentiment API Mismatch**: `test_sentiment_happy_path`, `test_sentiment_score_range`, `test_sentiment_empty_news`, and `test_sentiment_invalid_ticker` assert directly on floats, but the sentiment client returns dictionaries.
  2. **Politician API Mismatch**: `test_politician_happy_path` and `test_politician_scoring_weight` query schema keys (`ticker`, `signal_score`, `trade_type`) that do not exist in the production response dictionary.
  3. **Order Manager Demo Fallback**: `test_exec_bracket_order` fails because the test environment lacks a valid dummy `ALPACA_API_KEY`, forcing the production order executor to skip mock API endpoints.
  4. **Settings DB Table Missing**: `test_exec_circuit_breaker` attempts to insert into the `settings` table, which is not setup in the sqlite3 DB schema used by the test execution environment.
  5. **Cache Monkeypatch Namespace**: `test_sentiment_cache` patches `sentiment.finbert_client.get_sentiment` but `test_tier1_feature.py` imports `get_sentiment` directly beforehand, rendering the patch ineffective.
  6. **Syntax Error**: `test_llm_context_window_overflow` contains a dictionary multiplication syntax bug: `{"indicators": {"vwap": 1.0} * 1000}`.
  7. **Port Contention**: All dashboard REST/WebSocket tests fail with `ConnectionRefusedError` because port 8000 is occupied by an orphaned python process.

---

## 6. Dashboard Structure (`dashboard/`)
- **Structure**:
  - `dashboard/__init__.py`: Package initializer.
  - `dashboard/__main__.py`: Calls `start_dashboard` when run using `python -m dashboard`.
  - `dashboard/app.py`:
    - FastAPI web backend.
    - Serves `dashboard/index.html` as the static UI at the root path (`/`).
    - Provides REST endpoints (`/api/portfolio`, `/api/portfolio/history`, `/api/trades`, `/api/decisions`, `/api/signals`, `/api/politicians`, `/api/config`).
    - Exposes a WebSocket path (`/ws`) which periodically queries the SQLite database every 5 seconds and pushes JSON updates (containing technical signals, LLM decisions, and timestamps) to all connected clients.
  - `dashboard/index.html`: Real-time web panel styled with CSS/Tailwind, glassmorphism card layouts, Google Inter font, and interactive charting using `Chart.js`.

---

## 7. Requirements.txt and Unused Dependencies
- **Summary**: `requirements.txt` contains 19 packages including pandas, numpy, yfinance, alpaca-py, pytz, requests, python-dotenv, pyyaml, fastapi, uvicorn, websockets, apscheduler, google-generativeai, openai, anthropic, transformers, torch, beautifulsoup4, aiohttp.
- **Unused Dependencies**:
  - `beautifulsoup4`: Parsing congressional data or sentiment is done via API requests; no HTML scraping logic is implemented using BeautifulSoup.
  - `aiohttp`: HTTP requests in the code are synchronous and use the `requests` library.
  - `apscheduler`: Pre-market scans and day trading loop scheduling are implemented via standard time comparisons and loops in `trading_loop.py` rather than an active cron framework.
  - `websockets`: Real-time client updates are served using FastAPI's native WebSocket support; the standalone `websockets` library is not imported.
