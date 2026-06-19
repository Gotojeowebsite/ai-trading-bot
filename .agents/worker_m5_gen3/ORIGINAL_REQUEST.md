## 2026-06-19T17:01:59Z
You are a worker agent. Your working directory is /home/umanzor/ai-trading-bot/.agents/worker_m5_gen3.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your task is to implement the Cross-Platform Distribution (R4) requirements:
1. Create `/home/umanzor/ai-trading-bot/automation/setup_wizard.py` and define `CLISetupWizard` and `GUISetupWizard` classes:
   - `CLISetupWizard` should have a `run(self, data: dict = None) -> dict` method. If `data` is provided (e.g. `{"alpaca_key": "valid_key", "ib_account": "U12345"}` as called by tests), it should save the parameters to the `.env` file and/or `config/config.yaml` and return `{"status": "success"}`. If `data` is None, it should provide a terminal-based CLI menu that guides a user through key entry, broker selection, and validation.
   - `GUISetupWizard` should provide a Tkinter-based GUI setup wizard. To prevent crashes during tests or headless CI runs, wrap the Tkinter window creation inside a try-except block and check for the `DISPLAY` environment variable or `os.name == "nt"`, allowing it to be instantiated safely.
2. Build the Linux binary using PyInstaller:
   - Check if `pyinstaller` is installed in the virtual environment. If not, install it (`.venv/bin/pip install pyinstaller`).
   - Run `pyinstaller --onefile --name apex-trading-bot main.py`.
   - Verify that the build succeeds, producing `./dist/apex-trading-bot`. Test the compiled binary by running `./dist/apex-trading-bot status` (with the virtualenv in PATH) and verify that it starts and executes successfully without crashes.
3. Prepend the virtual environment bin path to PATH and run pytest sequentially to verify:
   `PATH=/home/umanzor/ai-trading-bot/.venv/bin:$PATH .venv/bin/pytest tests/e2e/test_r1_r5_e2e.py -k R4`
   Ensure all R4-related tests pass successfully.

Write a handoff report (handoff.md) describing the changes and test results. Provide the path of the handoff report and test log in your response.
