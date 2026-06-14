## 2026-06-14T08:40:46Z
Your identity: Milestone 1 Implementer/Worker (Generation 2).
Your working directory is /home/mint/Desktop/ai-trading-bot/.agents/worker_m1_gen2/

Task:
Fix the bugs and implement the enhancements identified during the Milestone 1 reviews.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Here are the specific findings and bugs you must fix:

1. Thread-Safety Data Race in `automation/data_client.py`:
   - In `_update_cache`, the shared cache DataFrame is copied outside the lock `self.on_bar_callback(symbol, df.copy())`. Concurrently, another thread updating the cache can mutate this DataFrame using `.at`.
   - Fix: Copy the DataFrame inside the `with self._lock` block (e.g. `df_copy = df.copy()`), and pass `df_copy` to `self.on_bar_callback` outside the lock.

2. Redundant Callback Triggers in yfinance Fallback Mode (`automation/data_client.py`):
   - In `_run_yfinance_polling`, we pull a full day's history of 1-minute bars and iterate over them, calling `_update_cache` on each bar. This unconditionally updates/appends and fires `on_bar_callback` for all 390 bars on every poll, causing heavy lag.
   - Fix: Inside `_update_cache`, check if the bar values have actually changed or if it is a new timestamp. Only modify the cache DataFrame and flag it as "changed" if there is a real update or new row. Only trigger the callback if it has actually changed/appended.

3. VWAP Daily Reset Bug on MultiIndex DataFrames (`automation/indicators.py`):
   - When a MultiIndex is used (e.g. index levels `(symbol, timestamp)`), `isinstance(df.index, pd.DatetimeIndex)` and `'timestamp' in df.columns` are both False. Thus, the daily reset group is bypassed, calculating a cumulative VWAP across all days.
   - Fix: Update `calculate_indicators` (and `_calculate_indicators_single` if applicable) to detect if `df.index` is a `MultiIndex` and has a level named `'timestamp'`. If so, extract dates using `pd.to_datetime(df.index.get_level_values('timestamp')).date` so that daily-reset grouping works correctly on MultiIndex inputs. Ensure DatetimeIndex and column fallbacks still work.

4. Wilder's RSI NaN Robustness Bug (`automation/indicators.py`):
   - The recursive loop in `_calculate_wilders_rsi` permanently propagates any intermediate `NaN` value, disabling RSI signals for all future ticks.
   - Fix: Re-implement Wilder's RSI calculation using standard pandas EWM methods (`gain.ewm(alpha=1/period, adjust=False).mean()`, etc.) which natively handle NaNs robustly. Maintain the Wilder's warmup mask by setting the first `period` elements of the returned RSI series to `NaN`.

5. Pre-market Scanner NaN Handling & Symbol Validation (`automation/scanner.py`):
   - Clean the historical DataFrame in `scan_ticker` using `dropna` on Close and Volume columns to prevent NaN gaps and volumes from being calculated and inserted into SQLite.
   - Sanitize and validate symbols in the CLI entry point to reject malformed ticker strings.

Steps to take:
1. Examine `automation/indicators.py`, `automation/data_client.py`, and `automation/scanner.py`.
2. Apply the required fixes.
3. Run all tests: `python3 -m pytest tests/`
4. Add extra unit tests verifying:
   - MultiIndex VWAP daily reset over multiple days (confirming it groups and resets daily).
   - RSI robustness to a single intermediate NaN (asserting that subsequent elements are successfully computed and not NaN).
   - Data client thread-safety / callback optimization (no callbacks for duplicate unchanged bars).
5. Document all changes and test outputs in `/home/mint/Desktop/ai-trading-bot/.agents/worker_m1_gen2/handoff.md`.
6. Send a message to the caller (id: c11e1ea8-9fb6-45f4-9262-e5419da6bcd1) with your handoff path.
