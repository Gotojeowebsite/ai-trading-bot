## 2026-06-19T16:41:06Z
You are a worker agent. Your working directory is /home/umanzor/ai-trading-bot/.agents/worker_m2_gen3.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task is to:
1. Create a new file `/home/umanzor/ai-trading-bot/engine/research_engine.py` and implement the morning deep research logic:
   - `def run_morning_research(provider="openai", model="o3-mini") -> dict`: Executes deep research via AI reasoning model. It should support both "openai" (pointing to `OPENAI_API_BASE` endpoint if set, otherwise defaulting to standard completions endpoint) and "gemini" (pointing to `GEMINI_API_BASE` generateContent endpoint if set). Parse the response, save it to `morning_research.json` and as a setting 'morning_research' in SQLite database.
   - `def get_today_research() -> dict`: Retrieves today's research findings from the file `morning_research.json` or fallback to SQLite database (table `settings`, key 'morning_research').
2. Modify `/home/umanzor/ai-trading-bot/engine/llm_brain.py` to import and expose `run_morning_research` and `get_today_research` so they can be imported correctly from `engine.llm_brain`.
3. Prepend the virtual environment bin path to PATH and run pytest sequentially to verify:
   `PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest tests/e2e/test_r1_r5_e2e.py -k R1`
   Ensure all R1-related tests pass (including `test_r1_production_morning_research`).

Write a handoff report (handoff.md) describing the changes, the rationale, and the test results. Provide the path of the handoff report and test log in your response.
