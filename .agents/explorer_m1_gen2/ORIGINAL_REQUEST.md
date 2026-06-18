## 2026-06-18T15:27:13Z

You are an explorer (teamwork_preview_explorer). Your identity is explorer_m1_gen2.
Your working directory is /home/umanzor/ai-trading-bot/.agents/explorer_m1_gen2.
Your task is to investigate the 6 failure categories reported in our baseline test run:
1. Mixed Timezone Index / DST transitions: `tests/unit/test_stress.py::test_scanner_dst_transitions`. Look at `automation/scanner.py` and `tests/unit/test_stress.py` to see why pd.to_datetime with mixed offsets returns object index and how to handle it.
2. Politician Signal Recency Decay: Look at `politician/copy_mode.py` and the test files (`tests/e2e/test_r1_r5_e2e.py`, `tests/e2e/test_tier1_feature.py`, `tests/e2e/test_tier2_boundary.py`). Why is the score decaying and how can we mock/adjust this so tests pass without changing the production logic? Or if the logic needs a change, how should we modify it?
3. News Sentiment Fallback Mismatch: News sentiment tests fail fallback because `torch` and `transformers` are missing. Look at `sentiment/finbert_client.py` and `tests/e2e/test_tier1_feature.py`. How does `_score_with_keywords` calculate scores? Should we adjust keyword list or mock the news sentiment response in E2E tests?
4. WebSocket Route Handshake Mismatch: E2E tests connect to `ws://localhost:8000/ws` but legacy dashboard server might not implement it. Look at `dashboard/app.py` and the E2E tests. How is the websocket route defined?
5. Dashboard Portfolio Endpoint Mismatch: Look at `dashboard/app.py` and `tests/e2e/test_r1_r5_e2e.py`'s `test_r3_dashboard_existing_portfolio_endpoint`. What does `/api/portfolio` or `/api/account` return? Why is the test expecting `account` key but receiving a raw dictionary?
6. Outage Recovery ConnectionError Not Propagated: `tests/e2e/test_tier4_scenarios.py::test_scenario_extended_api_outage_recovery` expects `ConnectionError` from Alpaca executor on outage. Look at `execution/order_manager.py` (specifically `AlpacaExecutor.place_bracket_order` or `execute_bracket_order` in `execution/order_manager.py`).

Analyze the relevant source code files and E2E tests for these 6 points. Do NOT write or edit code (you are read-only). Produce a detailed investigation report named `handoff.md` in your working directory with the exact changes needed for each file.
