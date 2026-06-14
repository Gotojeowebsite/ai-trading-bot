## 2026-06-14T08:35:34Z
You are M_INFRA Worker. Your working directory is /home/mint/Desktop/ai-trading-bot/.agents/worker_m_infra.
Your task is to implement the E2E test infrastructure and module stubs based on the design in /home/mint/Desktop/ai-trading-bot/.agents/explorer_m_infra_2/analysis.md.
Specifically, create the following files:
1. tests/e2e/mocks/__init__.py (empty)
2. tests/e2e/mocks/mock_server.py (containing MockServerState, MockHTTPRequestHandler, MockWebSocketServer)
3. tests/e2e/conftest.py (containing mock_servers fixture, clean_database fixture, run_cli fixture)
4. automation/indicators.py (conforming to calculate_indicators contract)
5. sentiment/finbert_client.py (conforming to get_sentiment contract)
6. politician/copy_mode.py (conforming to get_politician_signals contract)
7. engine/decision_engine.py (conforming to screen_ticker and make_decision contracts)
8. execution/order_manager.py (conforming to execute_bracket_order and close_all_positions contracts)
9. main.py (conforming to CLI modes)
10. tests/__init__.py (empty)
11. tests/e2e/__init__.py (empty)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Make sure that you write all these files, create the necessary directories, run pytest to ensure the runner initializes, and write your report in /home/mint/Desktop/ai-trading-bot/.agents/worker_m_infra/handoff.md. Send a message when complete.
