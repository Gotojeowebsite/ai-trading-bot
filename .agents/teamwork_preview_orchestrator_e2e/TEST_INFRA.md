# E2E Test Infra: AI Trading Bot

## Test Philosophy
- **Opaque-Box & Requirement-Driven**: Tests interact only with the public interfaces, CLI, databases, and network APIs of the system.
- **Offline / Deterministic Execution**: External services (Alpaca, yfinance, LLMs, news, Congress) are fully simulated/mocked locally.
- **Methodology**: Systematically designed using Category-Partition (feature coverage), Boundary Value Analysis (corner cases), Pairwise Combinatorial testing, and Real-World Workload simulations.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | FEAT-SCAN: Market Scanner & Technical Indicators | PROJECT.md §1 & §37 | 5 | 5 | ✓ |
| 2 | FEAT-SENT: News Sentiment Analysis (FinBERT NLP) | PROJECT.md §2 & §40 | 5 | 5 | ✓ |
| 3 | FEAT-POLY: Congress Trade Copying | PROJECT.md §3 & §43 | 5 | 5 | ✓ |
| 4 | FEAT-LLM: Tiered LLM Decision Pipeline | PROJECT.md §4 & §46 | 5 | 5 | ✓ |
| 5 | FEAT-EXEC: Alpaca Bracket Orders & Risk Circuit Breakers | PROJECT.md §5 & §50 | 5 | 5 | ✓ |
| 6 | FEAT-DASH: Real-Time Glassmorphism Web Dashboard | PROJECT.md §6 & §20 | 5 | 5 | ✓ |

## Test Architecture
- **Test Runner**: Pytest. Invoked via `pytest tests/e2e/`. Exit code 0 indicates success.
- **Directory Layout**:
  - `tests/e2e/conftest.py`: Shared pytest fixtures, mock servers, DB setup.
  - `tests/e2e/mocks/`: Custom simulation servers (Alpaca API server, LLM API server).
  - `tests/e2e/test_tier1_feature_coverage.py`: Happy path coverage.
  - `tests/e2e/test_tier2_boundary_cases.py`: Boundary and error inputs.
  - `tests/e2e/test_tier3_cross_feature.py`: Multi-feature interactions.
  - `tests/e2e/test_tier4_real_world.py`: Comprehensive workflow workloads.
- **Database**: SQLite database isolated for testing (`test_trading.db`).

## Test Case Inventory

### Tier 1 - Feature Coverage
1. `test_scan_happy_path`: Scanner retrieves prices, computes indicators, and saves to database.
2. `test_scan_yfinance_fallback`: Scanner falls back to yfinance when Alpaca historical API fails.
3. `test_scan_indicators_non_empty`: Verifies calculated indicators (RSI, MACD, VWAP, BB, EMA, RVOL) are valid floats.
4. `test_scan_schedule`: Scanner completes execution in expected pre-market timeline.
5. `test_scan_output_format`: Verify output scanner database schema matches specification.
6. `test_sentiment_happy_path`: Ingests headlines and computes sentiment score.
7. `test_sentiment_score_range`: FinBERT client returns scores strictly in [-1.0, 1.0].
8. `test_sentiment_empty_news`: Default to neutral score (0.0) when no news matches ticker.
9. `test_sentiment_invalid_ticker`: Handles invalid symbols and returns neutral sentiment.
10. `test_sentiment_cache`: Sentiment scoring fetches from local cache if within TTL.
11. `test_politician_happy_path`: Scrapes/reads disclosures and extracts congressional trades.
12. `test_politician_scoring_weight`: Higher scores are assigned to recent/large trades.
13. `test_politician_blended_signal`: Correctly blends politician scores with other metrics.
14. `test_politician_corrupt_data`: Handles malformed congressional disclosure inputs gracefully.
15. `test_politician_no_recent_trades`: Returns zero signal when trades are outside lookback.
16. `test_llm_happy_path`: Runs Tier 1 screening and Tier 2 decision, returning BUY/SELL/HOLD.
17. `test_llm_tier1_screening`: Low-performing tickers are filtered out during Tier 1 screen.
18. `test_llm_tier2_json_schema`: Tier 2 response parses into valid JSON with specified parameters.
19. `test_llm_fallback_tier1_fail`: Fallbacks to fallback configuration on Tier 1 LLM failure.
20. `test_llm_fallback_tier2_fail`: Fallbacks to Tier 1 score or HOLD on Tier 2 failure.
21. `test_exec_bracket_order`: Places bracket entry, take profit, and stop loss legs on Alpaca.
22. `test_exec_circuit_breaker`: Circuit breaker halts trading after daily realized losses exceed limit.
23. `test_exec_pre_close_liquidation`: Closes out open positions at 3:55 PM EST.
24. `test_exec_watchdog_restart`: Watchdog process restarts execution module if it dies.
25. `test_exec_position_sizing`: Position sizes do not exceed maximum capital allowance.
26. `test_dash_rest_portfolio`: API returns accurate balance, cash, and position stats.
27. `test_dash_rest_trades`: API returns complete history of trade logs.
28. `test_dash_websocket_updates`: WebSocket pushes updates on order placement and execution.
29. `test_dash_glassmorphism_static`: Web server successfully serves static dashboard assets.
30. `test_dash_settings_update`: Configuration parameters updated via dashboard API.

### Tier 2 - Boundary & Corner Cases
31. `test_scan_zero_volume`: Checks calculations for assets with zero trading volume.
32. `test_scan_extreme_prices`: Technical indicators calculated correctly for penny stocks ($0.0001).
33. `test_scan_incomplete_ohlcv`: Gracefully processes data sets with missing historical bars.
34. `test_scan_api_timeout`: API request timeout triggers retries before failing.
35. `test_scan_rvol_division_by_zero`: Prevents divide-by-zero during low average volume scans.
36. `test_sentiment_extremely_long_news`: News articles exceeding typical limits are handled safely.
37. `test_sentiment_api_down`: Return neutral sentiment if sentiment model backend is down.
38. `test_sentiment_special_chars`: News titles containing special/non-ASCII characters are parsed.
39. `test_sentiment_rate_limiting`: Sentiment client handles HTTP 429 rate limit errors from API.
40. `test_sentiment_contradictory_headlines`: Mixed positive and negative news balances to neutral.
41. `test_politician_disclosure_extreme_size`: Trades over $50 million are scored appropriately without overflow.
42. `test_politician_future_disclosed_date`: Rejects disclosures dated in the future.
43. `test_politician_duplicate_trades`: Deduplicates multiple identical politician filings.
44. `test_politician_missing_fields`: Handles records with missing amount/trade type fields.
45. `test_politician_historic_trades`: Zero weight assigned to filings older than lookback period (e.g. 180 days).
46. `test_llm_malformed_json_response`: Re-prompts or parses raw text on malformed JSON outputs.
47. `test_llm_hallucinated_action`: Flags and ignores action types other than BUY/SELL/HOLD.
48. `test_llm_stop_loss_out_of_bounds`: Overrules invalid stop loss levels (e.g., stop loss above entry price).
49. `test_llm_empty_reasoning`: Rejects decision when reasoning explanation is missing.
50. `test_llm_context_window_overflow`: Prompt compressor prevents exceeding LLM context limits.
51. `test_exec_insufficient_buying_power`: Handles Alpaca rejection for insufficient cash buying power.
52. `test_exec_order_fill_delay`: Watchdog flags or cancels orders that stay pending for too long.
53. `test_exec_circuit_breaker_exact_limit`: Triggers circuit breaker at exactly 100% of loss limit.
54. `test_exec_partial_fills`: Adjusts exit legs when order is only partially filled.
55. `test_exec_alpaca_disconnected_ws`: WebSockets auto-reconnect on socket loss.
56. `test_dash_websocket_flood`: UI server handles high message rate without lag or crashes.
57. `test_dash_unauthorized_access`: Unauthorized API calls return HTTP 401.
58. `test_dash_empty_db_state`: Serves dashboard UI correctly even if database is uninitialized.
59. `test_dash_concurrent_connections`: Handles multiple concurrent dashboard viewer sockets.
60. `test_dash_cors_config`: Enforces REST API cross-origin security.

### Tier 3 - Cross-Feature Combinations
61. `test_comb_scanner_to_sentiment`: Tickers selected by the scanner are evaluated by the sentiment module, filtering out those with negative scores before LLM input.
62. `test_comb_circuit_breaker_stops_all`: Activating the daily circuit breaker immediately pauses scanning, cancels active bracket orders, and locks the execution engine.
63. `test_comb_watchdog_restores_execution_and_dashboard`: Restores crashed processes (executor and web UI) and synchronizes internal databases with Alpaca.
64. `test_comb_politician_and_technical_concurrence`: A bullish politician disclosure overrides slightly bearish technical indicator trends, resulting in a BUY decision.
65. `test_comb_bracket_order_update_reflects_in_dashboard`: Placing an order triggers live WebSocket events that update the dashboard UI logs.
66. `test_comb_pre_close_liquidation_overrides_pending_orders`: Pre-close checks cancel outstanding orders, disable LLM calls, and liquidate all long/short positions.

### Tier 4 - Real-World Application Scenarios
67. `test_scenario_standard_trading_day`: Pre-market scanning (9:00 AM) -> Sentiment & Politician Signal ingestion -> Tier 1 & 2 LLM screening (BUY decision) -> Alpaca order entry (bracket order filled) -> position tracking -> Pre-close liquidation (3:55 PM).
68. `test_scenario_circuit_breaker_protection`: Simulates market downturn; multiple trades hit stop losses triggering circuit breaker; subsequent buy signals are successfully rejected.
69. `test_scenario_extended_api_outage_recovery`: Simulates Alpaca API outage during active trading; verifies bot pauses trading, handles exceptions gracefully, and checks for open positions when API recovers.
70. `test_scenario_high_frequency_news_and_trades`: Simulates high-density incoming news updates and filings, verifying signal blender processes feeds concurrently.
71. `test_scenario_watchdog_active_monitoring`: watchdog detects executor service crash during active trade, restarts executor, recovers order state from Alpaca API, and successfully exits trade when target is hit.

## Coverage Thresholds
- **Tier 1 (Feature Coverage)**: 30 / 30 tests implemented.
- **Tier 2 (Boundary & Corner Cases)**: 30 / 30 tests implemented.
- **Tier 3 (Cross-Feature Combinations)**: 6 / 6 tests implemented.
- **Tier 4 (Real-World Application Scenarios)**: 5 / 5 tests implemented.
- **Total Minimum Cases**: 71 tests. All tests must execute offline, mocks must isolate networking, and `pytest` execution must pass with 100% success.
