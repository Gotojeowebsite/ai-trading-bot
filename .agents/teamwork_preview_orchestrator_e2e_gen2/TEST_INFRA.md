# E2E Test Infra: APEX AI Trading Bot (New Requirements)

## Test Philosophy
- **Opaque-Box & Requirement-Driven**: Verify all new capabilities (Morning Research, IB Integration, Bloomberg-grade Dashboard, Setup Wizards) from their public APIs, CLI entry points, and database updates.
- **Strictly Offline**: All network calls (Interactive Brokers, Alpaca, OpenAI, Gemini, FinBERT, Congress/insider trades API) are fully mocked and run locally.
- **Methodology**: 4-Tier verification covering Feature Coverage, Boundary/Corner cases, Cross-Feature Combinations, and Real-World Scenarios.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|---------------------|:------:|:------:|:------:|:------:|
| 1 | FEAT-RESEARCH: Morning Deep Research Engine | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ | ✓ |
| 2 | FEAT-IB: Interactive Brokers Integration | ORIGINAL_REQUEST R2 | 5 | 5 | ✓ | ✓ |
| 3 | FEAT-DASH-NEW: Bloomberg Terminal-Grade Dashboard | ORIGINAL_REQUEST R3 | 5 | 5 | ✓ | ✓ |
| 4 | FEAT-WIZARD: Cross-Platform Setup Wizards | ORIGINAL_REQUEST R4 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- **Test Runner**: Pytest. Invoked via `pytest tests/e2e/`.
- **Directory Layout**:
  - `tests/e2e/conftest.py`: Shared pytest fixtures, mock servers, DB setup.
  - `tests/e2e/mocks/`: Custom mock HTTP and socket servers.
  - `tests/e2e/test_r1_r5_e2e.py`: Main E2E file containing the tests for the new requirements (Tiers 1-4).

## Test Case Inventory

### Tier 1 - Feature Coverage (5 per feature = 20 tests)
1. `test_r1_research_flow_happy_path`: Runs pre-market research using Gemini/OpenAI reasoning model, checking valid structured JSON output.
2. `test_r1_research_scheduled_run`: Verifies research triggers automatically on a configurable schedule before market open.
3. `test_r1_research_news_and_catalysts`: Verifies catalyst detection (earnings, FDA approvals, analyst actions) is successfully extracted and saved.
4. `test_r1_research_insider_congress_trades`: Verifies insider and politician trade tracking data ingestion works and scores trades correctly.
5. `test_r1_research_storage`: Verifies that research findings are stored as structured JSON/SQLite and can be retrieved.
6. `test_r2_ib_executor_account_info`: Verifies fetching balance, cash, and equity from IB mock server.
7. `test_r2_ib_executor_positions`: Verifies fetching open positions from IB.
8. `test_r2_ib_executor_bracket_order`: Verifies placing bracket orders (entry limit + stop-loss + take-profit) on IB.
9. `test_r2_ib_executor_cancel_order`: Verifies canceling active orders on IB.
10. `test_r2_ib_executor_close_positions`: Verifies EOD liquidation (close all positions) on IB.
11. `test_r3_dash_research_panel`: Verifies the FastAPI `/api/research` endpoint returns today's research findings.
12. `test_r3_dash_analytics_data`: Verifies the FastAPI `/api/analytics` endpoint returns win rate, P&L stats, Sharpe, and drawdown.
13. `test_r3_dash_settings_page`: Verifies runtime configuration changes can be saved via `/api/settings`.
14. `test_r3_dash_websocket_pnl`: Verifies that live WebSocket updates broadcast real-time portfolio value and P&L updates.
15. `test_r3_dash_heatmap`: Verifies the heatmap API returns correct security weights and performance metrics.
16. `test_r4_wizard_cli_walkthrough`: CLI setup wizard completes execution on valid user inputs.
17. `test_r4_wizard_gui_init`: GUI setup wizard launches and instantiates correctly.
18. `test_r4_wizard_key_validation`: Wizard validates Alpaca and IB credentials (format and presence).
19. `test_r4_wizard_broker_selection`: Selecting Alpaca vs IB updates system configuration.
20. `test_r4_wizard_risk_configuration`: Configuring risk limits updates daily loss limit and capital allocation settings.

### Tier 2 - Boundary & Corner Cases (5 per feature = 20 tests)
21. `test_r1_research_llm_rate_limiting`: Verifies the research engine throttles requests under tight LLM API limits.
22. `test_r1_research_api_timeout`: Verifies retries and graceful fallback when the reasoning model API times out.
23. `test_r1_research_empty_catalysts`: Verifies the research engine behaves correctly when no catalysts are found.
24. `test_r1_research_invalid_model`: Verifies the research engine falls back to standard Gemini Flash/OpenAI when reasoning models fail.
25. `test_r1_research_malformed_json`: Verifies the engine handles and parses malformed JSON completions.
26. `test_r2_ib_insufficient_liquidity`: Verifies handling IB order rejection due to insufficient cash/buying power.
27. `test_r2_ib_connection_loss`: Verifies that `IBExecutor` auto-reconnects when the connection to TWS/Gateway is lost.
28. `test_r2_ib_partial_fills`: Verifies the executor handles partial fills and updates exit legs accordingly.
29. `test_r2_ib_bracket_modification`: Verifies that invalid stop/limit prices are corrected or rejected.
30. `test_r2_ib_rate_limiting`: Verifies the IB executor respects request pacing to avoid IB rate limits.
31. `test_r3_dash_unauthenticated`: Verifies access settings are denied for unauthorized actions.
32. `test_r3_dash_websocket_concurrency`: Verifies handling of multiple concurrent websocket clients without performance degradation.
33. `test_r3_dash_settings_invalid_values`: Verifies that invalid configuration inputs are rejected with 400.
34. `test_r3_dash_empty_analytics`: Verifies analytics endpoints return default values instead of crashing when there is no trade history.
35. `test_r3_dash_missing_research`: Verifies the dashboard is robust when today's research findings are not found in the DB.
36. `test_r4_wizard_invalid_alpaca_key`: Verifies key format validation rejects malformed credentials.
37. `test_r4_wizard_invalid_ib_account`: Verifies validation rejects incorrect account number format.
38. `test_r4_wizard_missing_required_fields`: Verifies the setup wizard prompts for all required fields.
39. `test_r4_wizard_save_failure_handling`: Verifies wizard handles read-only file systems or config write errors.
40. `test_r4_wizard_cli_cancel`: Verifies the CLI wizard exits cleanly when cancelled by the user.

### Tier 3 - Cross-Feature Combinations (6 tests)
41. `test_comb_research_signal_to_ib_order`: Morning research yields a buy recommendation, which is successfully parsed and placed as a bracket order via the IB executor.
42. `test_comb_wizard_save_updates_dashboard_and_trading`: Modifying keys/risk via the setup wizard dynamically updates the active configurations of the running dashboard and bot.
43. `test_comb_holiday_checks_and_ib_trading`: Market holiday detection halts scanner and prevents the trade loop from launching any IB executions.
44. `test_comb_ib_fills_update_dashboard_websocket`: Simulating an execution fill on IB triggers a WS message to update the dashboard's active trades list.
45. `test_comb_circuit_breaker_halts_ib_orders`: Reaching daily loss limit on IB triggers the circuit breaker, which instantly cancels outstanding IB orders and blocks new signals.
46. `test_comb_liquidation_closes_ib_positions`: At 3:55 PM EST, pre-close liquidation cancels pending orders and liquidates all open IB positions.

### Tier 4 - Real-World Application Scenarios (5 tests)
47. `test_scenario_ib_trading_day`: Full autonomous day: Pre-market scanning -> Morning Research -> Trade loop on IB -> Live WebSocket updates -> 3:55 PM Liquidation.
48. `test_scenario_wizard_setup_to_ib_execution`: Setup wizard configures system -> Bot starts up in IB paper mode -> Trades placed successfully on mock IB.
49. `test_scenario_ib_connection_drop_recovery`: Simulates a Gateway disconnect mid-trade; Watchdog restarts the executor, reconnects to IB, retrieves current positions, and resumes monitoring.
50. `test_scenario_circuit_breaker_loss_limit_ib`: Market drops rapidly, multiple stop-losses hit on IB, daily loss limit is exceeded, circuit breaker trips, all IB positions close, and notification triggers.
51. `test_scenario_high_frequency_sentiment_and_research`: High news density and multiple politician filings blended with morning research trigger rapid signal updates, ensuring the blending module remains thread-safe and correct.

## Coverage Thresholds
- **Tier 1 (Feature Coverage)**: 20 / 20 tests implemented.
- **Tier 2 (Boundary & Corner Cases)**: 20 / 20 tests implemented.
- **Tier 3 (Cross-Feature Combinations)**: 6 / 6 tests implemented.
- **Tier 4 (Real-World Application Scenarios)**: 5 / 5 tests implemented.
- **Total Minimum Cases**: 51 tests. All tests must execute offline, mocks must isolate networking, and `pytest` execution must pass with 100% success.
