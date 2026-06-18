# BRIEFING — 2026-06-18T10:20:00-05:00

## Mission
Orchestrate the implementation and verification of the APEX AI trading bot features (R1-R5).

## 🔒 My Identity
- Archetype: teamwork_preview_orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: /home/umanzor/ai-trading-bot/.agents/orchestrator_gen2
- Original parent: parent
- Original parent conversation ID: f60d8d0c-a377-4750-866c-3d8a655105ba

## 🔒 My Workflow
- **Pattern**: Project
- **Scope document**: /home/umanzor/ai-trading-bot/.agents/orchestrator_gen2/PROJECT.md
1. **Decompose**: Decompose the project into the requested features (R1 to R5) and execute dual-track E2E testing and Implementation.
2. **Dispatch & Execute**: Spawn sub-orchestrators for milestones or run the Explorer -> Worker -> Reviewer loop per milestone.
3. **On failure** (in this order):
   - Retry: nudge stuck agent or re-send task
   - Replace: spawn fresh agent with partial progress
   - Skip: proceed without (only if non-critical)
   - Redistribute: split stuck agent's remaining work
   - Redesign: re-partition decomposition
   - Escalate: report to parent (sub-orchestrators only, last resort)
4. **Succession**: Self-succeed at 16 spawns. Write handoff.md, spawn successor, and exit.
- **Work items**:
  1. Explore and analyze existing codebase [in-progress]
  2. Implement/Fix M1: API Mismatch & Cleanup [pending]
  3. Implement R1/M2: Morning Deep Research Engine [pending]
  4. Implement R2/M3: Enhanced Autonomous Trading Engine [pending]
  5. Implement R3/M4: Premium Dashboard Enhancements [pending]
  6. Implement R4/M5: Cross-Platform Distribution [pending]
  7. Implement R5/M6: Comprehensive Testing & Documentation [pending]
- **Current phase**: 1
- **Current focus**: Explore and analyze existing codebase

## 🔒 Key Constraints
- NEVER write, modify, or create source code files directly.
- NEVER run build/test commands yourself — require workers to do so.
- You MAY use file-editing tools ONLY for metadata/state files (.md) in your .agents/ folder.
- Never reuse a subagent after it has delivered its handoff — always spawn fresh.
- Hard veto on forensic audit failure.

## Current Parent
- Conversation ID: f60d8d0c-a377-4750-866c-3d8a655105ba
- Updated: not yet

## Key Decisions Made
- Resuming project execution in a new session.
- Created PROJECT.md to manage milestones and interface contracts.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| worker_test_runner | teamwork_preview_worker | Run pytest suite to baseline codebase | completed | 397d700e-444a-4b40-853b-6f11d75dfd62 |
| explorer_m1_gen2 | teamwork_preview_explorer | Investigate baseline test failures | in-progress | 8853d033-99d5-47a6-a54d-0aa9159c2dd4 |

## Succession Status
- Succession required: no
- Spawn count: 2 / 16
- Pending subagents: 8853d033-99d5-47a6-a54d-0aa9159c2dd4
- Predecessor: /home/umanzor/ai-trading-bot/.agents/orchestrator
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: task-29
- Safety timer: none
- On succession: kill all timers before spawning successor
- On context truncation: run `manage_task(Action="list")` — re-create if missing

## Artifact Index
- /home/umanzor/ai-trading-bot/.agents/orchestrator_gen2/PROJECT.md — Global project architecture, milestones, interfaces, and code layout
- /home/umanzor/ai-trading-bot/.agents/orchestrator_gen2/progress.md — Heartbeat and progress checklist
