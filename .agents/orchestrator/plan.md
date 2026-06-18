# Project Plan: APEX AI Trading Bot Features (R1-R5)

This document outlines the execution and verification plan for implementing the APEX AI trading bot features.

## 1. Project Goal
Deliver a production-ready, fully autonomous AI trading bot with morning research capabilities, dual broker support (Alpaca + Interactive Brokers), premium UI features, easy cross-platform installation, and a fully passing test suite.

## 2. Dual-Track Execution Strategy
To guarantee software quality and prevent cheating or dummy implementations, we will execute two tracks in parallel:
1. **E2E Testing Track**: Spawns an E2E Testing Orchestrator to write Tiers 1-4 tests covering the morning deep research engine, IB integration, setup wizards, settings page, and dashboard analytics. It publishes `TEST_READY.md` once complete.
2. **Implementation Track**: Implements features across Milestones M1 to M5. Milestone M6 imports the test suite from the E2E Testing Track, runs all tests to 100% completion, and conducts Tier 5 adversarial testing.

### E2E Testing Tiers
- **Tier 1 - Feature Coverage**: Minimum of 5 test cases per feature (morning research scheduling/generation, Alpaca/IB selection, UI rendering, setups).
- **Tier 2 - Boundary & Corner Cases**: Minimum of 5 test cases per feature (e.g., failed LLM APIs, missing configuration, market holiday trade prevention, rate limiting triggers, invalid setup wizard keys).
- **Tier 3 - Cross-Feature Combinations**: Pairwise testing (e.g., EOD close triggering when trading via Interactive Brokers with failing LLM APIs).
- **Tier 4 - Real-World Application Scenarios**: End-to-end user journeys (e.g., pre-market research -> trading loop using IB paper mode -> dashboard telemetry updates -> EOD auto-close).

## 3. Implementation Milestones
- **M1: API Mismatch & Cleanup**: Fix the existing E2E test failures (dict vs float in sentiment/politician APIs, missing DB tables, port conflicts, requirements cleanup).
- **M2: Morning Deep Research Engine**: Implement pre-market AI research (Gemini Deep Think or equivalent), scraping/fetching catalysts, macro, sector, insider trades, scheduling, and database persistence.
- **M3: Enhanced Autonomous Trading Engine**: Support Interactive Brokers (IB) + Alpaca, macro_context indicator, market holiday check, rate-limiting, pre-close safety, paper trading by default.
- **M4: Premium Dashboard Enhancements**: Add Research findings panel, interactive zoom/pan charts, Settings configuration tab, and Performance analytics panel.
- **M5: Cross-Platform Distribution**: Build GUI setup wizard for Windows (.exe via PyInstaller), CLI setup wizard for Linux (binary), with input validation and sign-up links.
- **M6: Integration & Hardening**: Run final integration, pass 100% E2E tests, run Challenger-led Tier 5 adversarial testing.

## 4. Subagent Allocation & Workflow
Each milestone is assigned to a dedicated **Sub-orchestrator** (spawned using `self` or TypeName `teamwork_preview_orchestrator`).
Each sub-orchestrator executes the standard loop:
1. Decompose the milestone scope into local sub-milestones (`SCOPE.md`).
2. Run iteration loop:
   - Spawn **3 Explorers** to analyze failures and formulate a strategy.
   - Spawn **1 Worker** to implement/fix features and run unit tests.
   - Spawn **2 Reviewers** to independently review correctness and compatibility.
   - Spawn **2 Challengers** to execute stress tests.
   - Spawn **1 Forensic Auditor** to run integrity checks.
3. Gate check: If any test fails, review vetoes, or audit warns of integrity violation, rollback and re-iterate.

## 5. Heartbeat & Liveness Safety
- A cron check is run every 10 minutes (task-31).
- If any agent's `progress.md` becomes stale for >10 minutes, we retry (send a query) and replace (kill and respawn) if needed.
- Hard deadline: 20 minutes from dispatch.
