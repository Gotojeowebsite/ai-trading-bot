# Handoff Report — E2E Test Review & Feedback Analysis

**Working Directory:** `/workspaces/ai-trading-bot/.agents/explorer_s2_2`  
**Parent Agent:** `1eb05cf6-6a57-4414-9b91-702becd89f74` (parent)  
**Milestone:** E2E Feedback Analysis  

---

## 1. Observation

### Observation A: Database Isolation Failure
* **File Path:** `/workspaces/ai-trading-bot/dashboard/app.py`, Lines 46-49:
  ```python
  def get_db():
      config = get_config()
      db_path = config.get("database", {}).get("path", "trading.db")
      return sqlite3.connect(db_path)
  ```
* **File Path:** `/workspaces/ai-trading-bot/tests/e2e/conftest.py`, Line 78:
  ```python
      os.environ["DATABASE_PATH"] = "test_trading.db"
  ```
* **Verbatim Critic Feedback (`reviewer_2/handoff.md`, Lines 11-15):**
  > * **Observation A: Database Isolation Failure**
  >   * In `dashboard/app.py` lines 46-49, the `get_db()` function reads the database path directly from `config/config.yaml` (`trading.db`). It does NOT check the `DATABASE_PATH` environment variable.
  >   * In `tests/e2e/conftest.py` line 78, `os.environ["DATABASE_PATH"] = "test_trading.db"` is set.
  >   * ... Because the dashboard app doesn't respect the environment variable, it queries the production database `trading.db` instead of `test_trading.db`.

### Observation B: Legacy Server Test Regressions
* **File Path:** `/workspaces/ai-trading-bot/tests/e2e/test_tier1_feature.py`, Lines 332 and 341:
  ```python
  332:     r = requests.get(f"{dashboard_server}/api/trades")
  ...
  341:     ws = websocket.create_connection(f"ws://localhost:8000/ws")
  ```
* **File Path:** `/workspaces/ai-trading-bot/main.py`, Lines 294 and 327 (Legacy HTTP Server in `mode_dashboard()`):
  ```python
  294:             if self.path == "/ws/updates":
  ...
  327:             elif self.path in ("/trades",):
  ```
* **Verbatim Critic Feedback (`reviewer_2/handoff.md`, Lines 16-19):**
  > * **Observation B: Legacy Server Test Regressions**
  >   * In `tests/e2e/test_tier1_feature.py` line 341, `test_dash_websocket_updates` was changed to connect to `ws://localhost:8000/ws`.
  >   * In `tests/e2e/test_tier1_feature.py` line 332, `test_dash_rest_trades` was changed to call `http://localhost:8000/api/trades`.
  >   * However, the `dashboard_server` fixture runs the legacy server on port 8000 (defined in `main.py` lines 262-371), which only supports WebSocket upgrades on `/ws/updates` (line 294) and GET requests on `/trades` (line 327). It returns `404 Not Found` for `/ws` and `/api/trades`.

---

## 2. Logic Chain

### Logic Chain A: Database Isolation Failure
1. **Observation A** indicates that `dashboard/app.py` resolves the database path strictly from `config/config.yaml` using `config.get("database", {}).get("path", "trading.db")`.
2. Even though `tests/e2e/conftest.py` sets `os.environ["DATABASE_PATH"] = "test_trading.db"`, `dashboard/app.py` never reads this environment variable.
3. Therefore, during E2E testing when the `dashboard_fastapi_app` is imported and run (e.g. in `test_r1_r5_e2e.py` on port 8003), any database calls route to the production database `trading.db`.
4. To solve this **without modifying production code** (i.e. leaving `dashboard/app.py` untouched), we can exploit Python's module caching mechanism (singletons).
5. By importing `dashboard.app` in `tests/e2e/conftest.py` during test setup and overriding the `get_db` function dynamically (`monkey-patching`), we can force the dashboard to connect to the test database.
6. The proposed patch is:
   ```python
   import os
   import sqlite3
   import dashboard.app

   dashboard.app.get_db = lambda: sqlite3.connect(os.environ.get("DATABASE_PATH", "test_trading.db"))
   ```
   When the test suite runs `uvicorn.run(dashboard_fastapi_app, ...)`, any calls to `get_db()` will invoke our patched version, correctly isolating the database.

### Logic Chain B: Legacy Server Test Regressions
1. **Observation B** establishes that the legacy dashboard server in `main.py` (which runs on port 8000 during E2E tests) expects WebSocket connections at `/ws/updates` and HTTP REST requests for trades at `/trades`.
2. However, the E2E tests in `tests/e2e/test_tier1_feature.py` make requests to `/ws` and `/api/trades`.
3. When the legacy server receives requests for `/ws` and `/api/trades`, it responds with `404 Not Found`, causing `test_dash_rest_trades` and `test_dash_websocket_updates` to fail.
4. To restore compatibility, we must revert the endpoint paths inside `tests/e2e/test_tier1_feature.py` to match the legacy server's expected paths:
   - Revert `ws://localhost:8000/ws` to `ws://localhost:8000/ws/updates`
   - Revert `/api/trades` to `/trades`

---

## 3. Caveats
* **WebSocket Hangs:** If the database lacks the required tables (e.g. `signals`), the `dashboard/app.py` WebSocket handler catches the exception silently and enters a sleeping loop without sending updates. If the E2E tests block on `ws.recv()`, they will hang indefinitely. We recommend configuring a connection timeout in all WebSocket tests:
  ```python
  ws = websocket.create_connection("ws://localhost:8000/ws/updates", timeout=5.0)
  ```
  to avoid silent hangs.

---

## 4. Conclusion
1. **Database Isolation** can be successfully solved at the test level by adding an autouse pytest fixture in `tests/e2e/conftest.py` that monkey-patches `dashboard.app.get_db` to return a connection to `DATABASE_PATH` (defaulting to `test_trading.db`).
2. **Legacy Server Compatibility** is restored by reverting the URL paths in `tests/e2e/test_tier1_feature.py` to `/ws/updates` (for WebSocket updates) and `/trades` (for trade history retrieval).

---

## 5. Verification Method

### 1. Verification of Database Isolation
* **Test Case:** Create a temporary test script or run a pytest test that starts the premium dashboard server, performs a REST query (e.g., `/api/portfolio/history`), and verify it queries the test database.
* **Code to Inspect:** Ensure that `tests/e2e/conftest.py` contains the dynamic override:
  ```python
  import dashboard.app
  # Check if get_db is successfully patched
  assert "test_trading.db" in str(dashboard.app.get_db)  # Depending on implementation
  ```

### 2. Verification of Legacy Server Compatibility
* **Test Command:** Run `pytest tests/e2e/test_tier1_feature.py -k "test_dash"` to verify the legacy server tests pass.
* **Files to Inspect:** Inspect `/workspaces/ai-trading-bot/tests/e2e/test_tier1_feature.py` at line 332 and line 341 to ensure they query `/trades` and `/ws/updates` respectively.

---

## Proposed Changes (Patch)

### Diff for `tests/e2e/conftest.py` (Database Isolation)
```diff
--- tests/e2e/conftest.py
+++ tests/e2e/conftest.py
@@ -87,4 +87,11 @@
 @pytest.fixture(autouse=True)
 def clean_database():
     """Ensures test_trading.db is empty and clean before each test runs."""
+    # Monkey-patch premium dashboard db connection to ensure isolation
+    try:
+        import dashboard.app
+        dashboard.app.get_db = lambda: sqlite3.connect(os.environ.get("DATABASE_PATH", "test_trading.db"))
+    except ImportError:
+        pass
+
     db_path = "test_trading.db"
```

### Diff for `tests/e2e/test_tier1_feature.py` (Legacy Server Compatibility)
```diff
--- tests/e2e/test_tier1_feature.py
+++ tests/e2e/test_tier1_feature.py
@@ -329,3 +329,3 @@
 
-    r = requests.get(f"{dashboard_server}/api/trades")
+    r = requests.get(f"{dashboard_server}/trades")
     assert r.status_code == 200
@@ -338,3 +338,3 @@
     # WebSocket path
-    ws = websocket.create_connection(f"ws://localhost:8000/ws")
+    ws = websocket.create_connection(f"ws://localhost:8000/ws/updates", timeout=5.0)
     resp = ws.recv()
```
