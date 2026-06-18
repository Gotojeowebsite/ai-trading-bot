# APEX AI — Live Handoff Document
**Last updated:** 2026-06-18T10:55 CST
**Status:** 🔨 IN PROGRESS — Building critical components

---

## What's Being Built (Priority Order)

### ✅ = Done | 🔨 = In Progress | ⏳ = Not Started

| # | Component | Status | Notes |
|---|-----------|--------|-------|
| R1 | Morning Deep Research Engine | 🔨 | New module `research/` — deep pre-market AI analysis |
| R3 | Bloomberg Terminal-Grade Dashboard | ⏳ | Elevate existing dashboard to 10/10 |
| R2 | Enhanced Trading Engine (Alpaca + IB) | ⏳ | Add IB via ib_insync, fix API mismatches |
| R4 | Cross-Platform Distribution | ⏳ | Windows .exe + Linux binary with setup wizards |
| R5 | Testing & Documentation | ⏳ | Fix existing tests + new coverage |

---

## R1. Morning Deep Research Engine

### Design
- New module: `research/deep_research.py`
- Uses advanced AI reasoning models (Gemini 2.5 Pro thinking, OpenAI o3, Claude extended thinking)
- Produces structured JSON research report consumed by trading engine
- Covers: macro analysis, company catalysts, insider/politician trades, sector sentiment, calendar events
- Runs on configurable schedule before market open
- Integrates with existing `engine/llm_brain.py` LLM calling infrastructure

### Files to Create
- [ ] `research/__init__.py`
- [ ] `research/deep_research.py` — Main research engine
- [ ] `research/macro_analyzer.py` — VIX, indices, sector rotation
- [ ] `research/catalyst_detector.py` — Earnings, FDA, M&A, analyst actions
- [ ] `research/research_scheduler.py` — Pre-market scheduling

### Integration Points
- Trading loop (`automation/trading_loop.py`) calls research before market open
- Dashboard (`dashboard/app.py`) serves research results via REST + WebSocket
- Config (`config/config.yaml`) has schedule and model settings

---

## R3. Bloomberg Terminal-Grade Dashboard

### Design
- Elevate existing `dashboard/index.html` (699 lines, dark glassmorphism)
- Add: morning research panel, interactive candlestick charts, heatmap, equity curve
- Add: settings page, performance analytics, particle effects
- Use lightweight-charts (TradingView) for candlestick charts
- Keep FastAPI + WebSocket backend

### Files to Modify
- [ ] `dashboard/index.html` — Complete redesign to Bloomberg-grade
- [ ] `dashboard/app.py` — New API endpoints for research, analytics, settings

---

## R2. Enhanced Trading Engine

### API Mismatches to Fix
- `get_sentiment()` returns dict in production but tests expect float
- `get_politician_signals()` schema mismatch between production and tests
- `execute_bracket_order()` demo mode bypass issue
- `macro_context` signal configured but never computed

### Files to Modify/Create
- [ ] `execution/ib_executor.py` — New Interactive Brokers executor via ib_insync
- [ ] `execution/order_manager.py` — Add broker abstraction layer
- [ ] `automation/trading_loop.py` — Integrate research signals + IB support
- [ ] `engine/llm_brain.py` — Add rate limiting

---

## R4. Cross-Platform Distribution

### Files to Create
- [ ] `setup_wizard/gui_wizard.py` — Tkinter GUI wizard for Windows
- [ ] `setup_wizard/cli_wizard.py` — CLI wizard for Linux
- [ ] `build_scripts/build_windows.py` — PyInstaller Windows build
- [ ] `build_scripts/build_linux.py` — PyInstaller Linux build
- [ ] `apex_ai.spec` — PyInstaller spec file

---

## R5. Testing & Documentation

### Files to Fix/Create
- [ ] `tests/` — Fix API contract mismatches
- [ ] `tests/test_research.py` — New research engine tests
- [ ] `tests/test_ib_executor.py` — New IB integration tests
- [ ] `tests/test_setup_wizard.py` — Wizard integration tests
- [ ] `README.md` — Updated comprehensive documentation
- [ ] `docs/USER_GUIDE.md` — Full user guide

---

## Architecture Notes

### Existing LLM Infrastructure
The bot already has `engine/llm_brain.py` with:
- `_call_gemini()` — Google Gemini API (gemini-2.0-flash)
- `_call_openai()` — OpenAI API (gpt-4o)
- `_call_anthropic()` — Anthropic Claude API
- Tiered decision system: Tier 1 (fast) → Tier 2 (deep) → Fallback

### Existing Dashboard
- FastAPI backend at `dashboard/app.py`
- Single-page HTML at `dashboard/index.html` (699 lines)
- Chart.js for charts, WebSocket for live updates
- Dark glassmorphism CSS theme with Inter font

### Config Structure
- `config/config.yaml` — watchlist, risk, LLM tiers, broker, notifications

---

*If quota runs out, the next agent should pick up from the first ⏳ item above.*
