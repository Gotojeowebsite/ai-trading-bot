# Project Plan: Autonomous AI Day-Trading Bot

This document outlines the execution and verification plan for building the Production-Quality, Fully Autonomous AI Day-Trading Bot.

## 1. Project Goal
Develop an autonomous trading bot running under the Alpaca Markets API. The bot scans the market, scores sentiment, tracks politician disclosures, and runs a Tiered LLM Architecture (Gemini 2.0 Flash screening + Premium LLM decision engine) to place bracket trades. A glassmorphism dashboard monitors operations in real-time.

## 2. Dual-Track Execution Strategy
To guarantee software quality and prevent cheating or dummy implementations, we will execute two tracks in parallel:
1. **E2E Testing Track**: Spawns an E2E Testing Orchestrator to define the test runner, test framework, and write Tiers 1-4 tests before implementation code is verified. This track publishes `TEST_READY.md` once complete.
2. **Implementation Track**: Implements features across Milestones M1 to M6. The final Milestone M7 imports the test suite from the E2E Testing Track and ensures 100% test completion, followed by Tier 5 adversarial testing.

### E2E Testing Tiers
- **Tier 1 - Feature Coverage**: Minimum of 5 test cases per feature (happy-path, basic triggers).
- **Tier 2 - Boundary & Corner Cases**: Minimum of 5 test cases per feature (e.g., empty watchlists, zero prices, API timeouts, negative numbers, overflow).
- **Tier 3 - Cross-Feature Combinations**: Pairwise testing of interacting features (e.g., circuit breaker triggering during active LLM screening).
- **Tier 4 - Real-World Application Scenarios**: Comprehensive end-to-end user journeys (e.g., full trading day simulation: pre-market scan -> news sentiment ingest -> politician copy trigger -> buy order placed -> market close pre-exit).

## 3. Implementation Milestones
- **M1: Market Data & Technical Indicators**: Setup WS/yfinance client, pre-market scanner, and compute technical metrics (VWAP, RSI, MACD, BB, EMA, RVOL).
- **M2: News Sentiment Analysis**: Setup financial news headlines ingestion and compute FinBERT-based sentiment scores.
- **M3: Politician Copy Mode**: Gather, score, and weight U.S. congressional stock trade disclosures.
- **M4: Tiered LLM Engine**: Integrate Tier 1 (Gemini 2.0 Flash) and Tier 2 (premium GPT-4o) LLMs. Support fallback configurations.
- **M5: Automated Execution**: Connect Alpaca Markets API, handle bracket orders, enforce position rules, daily loss circuit breakers, pre-close logic, and implement watchdog crash-recovery.
- **M6: Dark Glassmorphism Dashboard**: Develop real-time dashboard with WebSockets displaying portfolio values, trade logs, LLM reasoning, Capitol trades feed, and configuration panel.
- **M7: Integration & Hardening**: Integration verification of E2E tests and Challenger-led Tier 5 adversarial testing.

## 4. Subagent Allocation & Workflow
Each milestone is assigned to a dedicated **Sub-orchestrator** (spawned using `self` or TypeName `teamwork_preview_orchestrator`).
Each sub-orchestrator executes the standard loop:
1. Decompose the milestone scope into local sub-milestones (`SCOPE.md`).
2. Run iteration loop:
   - Spawn **3 Explorers** to analyze failures and formulate a strategy.
   - Spawn **1 Worker** to implement/fix features and run unit tests.
   - Spawn **2 Reviewers** to independently review correctness and compatibility.
   - Spawn **2 Challengers** to execute stress tests.
   - Spawn **1 Forensic Auditor** to run integrity checks (detecting hardcoded mocks or dummy behaviors).
3. Gate check: If any test fails, review vetoes, or audit warns of integrity violation, rollback and re-iterate.

## 5. Heartbeat & Liveness Safety
- A cron check is run every 10 minutes (task-17).
- If any agent's `progress.md` becomes stale for >10 minutes, we retry (send a query) and replace (kill and respawn) if needed.
- Hard deadline: 20 minutes from dispatch.
