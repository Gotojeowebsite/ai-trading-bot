## 2026-06-19T16:56:15Z
You are a worker agent. Your working directory is /home/umanzor/ai-trading-bot/.agents/worker_m4_gen3.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task is to implement the Bloomberg Terminal-Grade Dashboard (R3) requirements:
1. Update `/home/umanzor/ai-trading-bot/dashboard/app.py` to add:
   - `GET /api/research`: returns `get_today_research()` (import from `engine.llm_brain`).
   - `GET /api/analytics`: queries the SQLite database table `trades` and `portfolio_snapshots` to compute and return a JSON object with: `win_rate`, `avg_pnl`, `sharpe_ratio`, `max_drawdown`, and `equity_curve` (list of values). Fallback to realistic mock values if the database has no trades.
   - `GET /api/settings` and `POST /api/settings`: to retrieve and update settings in the SQLite database table `settings`.
2. Update `/home/umanzor/ai-trading-bot/dashboard/index.html` to:
   - Add a **Morning Research panel** displaying macro outlook, VIX, sector trends, and company catalysts (using data from `/api/research`).
   - Add a **Settings Configuration Drawer/Modal** that lets users view and update API keys, broker, and risk profile settings (saving via `/api/settings` POST).
   - Add a **Performance Analytics panel** displaying win rate, Sharpe ratio, drawdown, and average P&L (using data from `/api/analytics`).
   - Enhance the Portfolio Performance chart to support timeframe selection (1D, 5D, 1M, All) filtering the database data.
   - Elevate the styling to a 10/10 Bloomberg Terminal-grade dark glassmorphism interface. Add particle background effects (using an HTML5 canvas or CSS), gradient animations, glowing borders, and smooth transition animations.
   - Ensure the layout remains responsive for desktop and tablet.
3. Prepend the virtual environment bin path to PATH and run pytest sequentially to verify:
   `PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest tests/e2e/test_r1_r5_e2e.py -k R3`
   Ensure all R3-related tests pass successfully.

Write a handoff report (handoff.md) describing the changes and test results. Provide the path of the handoff report and test log in your response.
