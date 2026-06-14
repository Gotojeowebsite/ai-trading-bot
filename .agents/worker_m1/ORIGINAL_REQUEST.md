## 2026-06-14T08:35:48Z

Your identity: Milestone 1 Implementer/Worker.
Your working directory is /home/mint/Desktop/ai-trading-bot/.agents/worker_m1/

Task:
Implement Milestone 1 (Market Data & Technical Indicators) of the Autonomous AI Day-Trading Bot.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Milestone 1 Scope:
1. Establish a live market data client (via Alpaca WebSocket or yfinance) that continuously receives ticker price updates.
2. Build an indicator module (`automation/indicators.py`) that computes the following indicators on a per-ticker basis: VWAP, MACD, RSI, Bollinger Bands, EMA crossovers, and Relative Volume (RVOL).
3. Build a pre-market scanner (`automation/scanner.py`) that runs before 9:30 AM EST and identifies top watchlist stocks based on gap percentage, volume, and news catalysts.

Steps to take:
1. Read PROJECT.md at /home/mint/Desktop/ai-trading-bot/.agents/orchestrator/PROJECT.md
2. Read SCOPE.md at /home/mint/Desktop/ai-trading-bot/.agents/teamwork_preview_orchestrator_m1/SCOPE.md
3. Read the synthesized plan at /home/mint/Desktop/ai-trading-bot/.agents/teamwork_preview_orchestrator_m1/synthesis.md
4. Create and install dependencies from `requirements.txt` at the root directory containing necessary packages (pandas, numpy, yfinance, alpaca-py, pytz, pytest, pytest-mock, etc.).
5. Create the `automation/` package:
   - Implement `automation/__init__.py` (empty or package metadata).
   - Implement `automation/indicators.py` containing:
     `def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame` which calculates VWAP (resets daily if datetime timestamp exists), MACD (macd, macd_signal, macd_hist), RSI (14-period Wilder's), Bollinger Bands (20-period, 2 std dev), EMA Crossover (ema_fast, ema_slow, ema_crossover), and RVOL (20-period average volume). Ensure it handles multiple tickers gracefully if present (e.g. grouped by symbol/ticker column or index if multi-indexed).
   - Implement `automation/data_client.py` containing `MarketDataClient` with Alpaca StockDataStream client (configurable urls for offline mocks) and a yfinance polling thread fallback.
   - Implement `automation/scanner.py` containing `PreMarketScanner` that calculates gap percentage and volume during pre-market hours (US/Eastern timezone) and logs to a SQLite database. Implement a CLI interface for the scanner.
6. Create `tests/` directory:
   - Implement `tests/unit/test_indicators.py` verifying each indicator calculation mathematically with a local DataFrame of mock prices.
   - Implement `tests/unit/test_data_client.py` and `tests/unit/test_scanner.py` using unittest mock or pytest-mock to test logic offline (since network requests are blocked in sandbox environment).
7. Run all tests:
   `pytest tests/`
   Document the test output and commands.
8. Write a detailed handoff report to `/home/mint/Desktop/ai-trading-bot/.agents/worker_m1/handoff.md` summarizing:
   - Target files created/modified and their purposes.
   - Design details and how the interface contracts are fulfilled.
   - How dependencies were handled.
   - Test execution commands and full results.
9. Send a message to the caller (id: c11e1ea8-9fb6-45f4-9262-e5419da6bcd1) indicating you are done and providing the path to your handoff.md.
