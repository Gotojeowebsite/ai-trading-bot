# Handoff Report — Milestone 1 Review

## 1. Observation
I have performed an independent, adversarial, and quality review of the Milestone 1 implementation. The following items were directly observed in the source code files:

### Cache Locking Thread-Safety
In `automation/data_client.py` (lines 79–106):
```python
    def _update_cache(self, symbol: str, new_row: dict):
        with self._lock:
            df = self.cache.get(symbol, pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'timestamp']))
            timestamp = new_row['timestamp']
            
            # Check for duplicate timestamp
            if not df.empty and timestamp in df['timestamp'].values:
                # Update existing row
                idx = df[df['timestamp'] == timestamp].index[0]
                for k, v in new_row.items():
                    df.at[idx, k] = v
            else:
                # Append row
                new_df = pd.DataFrame([new_row])
                df = pd.concat([df, new_df], ignore_index=True)
                
            # Limit cache size
            if len(df) > self.max_cache_bars:
                df = df.iloc[-self.max_cache_bars:].reset_index(drop=True)
                
            self.cache[symbol] = df
            
        if self.on_bar_callback:
            try:
                self.on_bar_callback(symbol, df.copy())
            except Exception as e:
                logger.error(f"Error in user callback for {symbol}: {e}")
```

### VWAP Daily Reset for MultiIndex
In `automation/indicators.py` (lines 67–85):
```python
    # 1. VWAP (resets daily if datetime timestamp exists)
    dates = None
    if isinstance(df.index, pd.DatetimeIndex):
        dates = df.index.date
    elif 'timestamp' in df.columns:
        dates = pd.to_datetime(df['timestamp']).dt.date
        
    typical_price = (high + low + close) / 3.0
    tp_v = typical_price * volume
    
    if dates is not None:
        cum_tp_v = tp_v.groupby(dates).cumsum()
        cum_v = volume.groupby(dates).cumsum()
    else:
        cum_tp_v = tp_v.cumsum()
        cum_v = volume.cumsum()
```

### Custom Wilder's RSI Loop & NaNs
In `automation/indicators.py` (lines 23–25):
```python
    # Wilder's smoothing
    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gain_vals[i]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + loss_vals[i]) / period
```

### Unit Test Execution
Running `python3 -m pytest tests/` outputs:
```
======================== 14 passed, 1 warning in 4.78s =========================
```

---

## 2. Logic Chain
- **Step 1 (Thread Safety Vulnerability)**: The shared data cache (`self.cache`) is protected by `self._lock` inside `_update_cache`. However, the lock is released *before* calling `self.on_bar_callback`. Outside the lock, the thread executes `df.copy()`. Because `df` is the same object stored in `self.cache[symbol]`, another concurrent thread (e.g. streaming new ticks) can acquire `self._lock` and mutate this very same `df` object in-place (specifically using `df.at[idx, k] = v`). Concurrently executing `df.copy()` on one thread and modifying `df` on another thread results in a classic data race. This can cause index corruption, value discrepancies, or `RuntimeError` during execution under heavy data loads.
- **Step 2 (VWAP Daily Reset Bug)**: For a multi-indexed DataFrame with index levels `(symbol, timestamp)` (which is a supported interface style), the index is of type `pd.MultiIndex`, not `pd.DatetimeIndex`. Thus `isinstance(df.index, pd.DatetimeIndex)` is `False`. Since `timestamp` is a level name rather than a column, `'timestamp' in df.columns` is also `False`. Consequently, `dates` evaluates to `None`, bypassing the daily group and calculating a cumulative VWAP across all days.
- **Step 3 (RSI Robustness Bug)**: The custom implementation of Wilder's RSI relies on a manual recursive loop. If any price point in the middle of a dataset is `NaN` (e.g., due to a data ingestion drop or faulty API response), the corresponding `gain_vals[i]` or `loss_vals[i]` becomes `NaN`. The formula then propagates this `NaN` through the recursion permanently. As a result, *all* subsequent RSI values for the rest of the session become `NaN`.
- **Step 4 (EMA Crossover Warmup)**: The EMA crossover signals are calculated right from the second bar without warmup masking. Because both EMAs are initialized to `close[0]`, the first tick divergence triggers a crossover signal (either `1` or `-1`) immediately, which can result in premature trades.

---

## 3. Caveats
- I did not test websocket performance under simulated high network latency since external network access is blocked in the CODE_ONLY sandbox environment.
- I assume the downstream modules (sentiment, politician copy, etc.) are implemented according to their respective specifications in `PROJECT.md`.

---

## 4. Conclusion

### Review Summary
**Verdict**: REQUEST_CHANGES

### Findings

#### [Critical] Finding 1: Cache Lock Thread-Safety Data Race
- **What**: Data race during `df.copy()` execution outside the lock block.
- **Where**: `automation/data_client.py` (lines 99–103)
- **Why**: Concurrently copying the cached DataFrame while another thread acquires the lock and mutates it in-place using `.at` will trigger data races or `RuntimeError`.
- **Suggestion**: Perform `df.copy()` inside the `with self._lock` context manager block and pass that copied instance to the callback.

#### [Major] Finding 2: VWAP Daily Reset Fails on MultiIndex DataFrames
- **What**: MultiIndex levels are not checked when determining datetime dates for VWAP grouping.
- **Where**: `automation/indicators.py` (lines 68–72)
- **Why**: `isinstance(df.index, pd.DatetimeIndex)` and `'timestamp' in df.columns` both fail for a MultiIndex with levels `(symbol, timestamp)`, so VWAP falls back to cumulative calculation.
- **Suggestion**: Check if `isinstance(df.index, pd.MultiIndex)` and extract the date component from the relevant index level (e.g. `df.index.get_level_values('timestamp').date`).

#### [Major] Finding 3: RSI custom Wilder's loop permanently propagates NaNs
- **What**: A single NaN price point in the middle of the series renders all future RSI values `NaN`.
- **Where**: `automation/indicators.py` (lines 23–25, 35–44)
- **Why**: The recursive smoothing formula `(avg_gain[i-1] * 13 + gain_vals[i]) / 14` does not filter out or fill middle NaNs, resulting in total loss of RSI signals after any transient data issue.
- **Suggestion**: Use standard pandas EWM methods (like `.ewm(alpha=1/period, adjust=False)`) which handle intermediate NaNs robustly.

#### [Minor] Finding 4: Pre-market Scanner CLI missing symbol override validation
- **What**: Scanner splits `--symbols` by comma, but does not sanitize spaces or validate format.
- **Where**: `automation/scanner.py` (line 200)
- **Why**: Leading/trailing whitespace is stripped, but malformed ticker names will crash yfinance fetches inside a try-catch, failing silently with an error status in database.
- **Suggestion**: Validate ticker patterns before making API calls.

---

### Verified Claims
- **Claim**: VWAP resets daily on DatetimeIndex/timestamp columns -> verified via `tests/unit/test_indicators.py::test_vwap_daily_reset` -> PASS.
- **Claim**: RSI Wilder's method computes correct math -> verified via `tests/unit/test_indicators.py::test_indicators_mathematics` -> PASS.
- **Claim**: Bollinger Bands (ddof=0) match standard calculations -> verified via `tests/unit/test_indicators.py::test_indicators_mathematics` -> PASS.
- **Claim**: Pre-market scanner filters by gap % and volume and checks 9:30 AM EST restrictions -> verified via `tests/unit/test_scanner.py` -> PASS.

---

### Coverage Gaps
- **MultiIndex VWAP reset over multiple days**: The multiindex tests only use a single day of data, which masked the fact that `dates` is `None` and therefore daily resets are bypassed.
- **Thread race on client updates**: The unit tests do not run multiple threads modifying the same symbol cache concurrently, which masked the thread-safety violation.

---

### Unverified Items
- **Alpaca WebSockets reconnect stability**: Unable to verify real-world reconnection behavior during network dropouts due to sandbox restrictions.

---

### Challenge Summary (Adversarial Review)
**Overall risk assessment**: MEDIUM

### Challenges

#### [High] Challenge 1: Data-Race under concurrent WebSocket tick events
- **Assumption challenged**: Cache updates are thread-safe.
- **Attack scenario**: Multiple fast-paced WebSocket ticks for the same symbol trigger callback functions while `_update_cache` is performing `.at` modifications. The thread calling the callback performs `df.copy()` on a half-modified or currently-modifying block, yielding a segmentation fault or a python `RuntimeError`.
- **Blast radius**: Crashes the WebSocket ingest thread, causing the bot to go offline or fall back permanently to yfinance polling.
- **Mitigation**: Perform the copy inside the lock.

#### [Medium] Challenge 2: VWAP computation discrepancy on MultiIndex
- **Assumption challenged**: MultiIndex is supported with full feature parity.
- **Attack scenario**: A multi-symbol trader passes MultiIndex data containing 5 days of data. The daily reset is completely bypassed, so the bot uses incorrect, cumulative VWAP values for its trading signals.
- **Blast radius**: Faulty signals leading to incorrect buying/selling.
- **Mitigation**: Add MultiIndex level checking for Datetime indices.

#### [Medium] Challenge 3: Ingestion noise causing RSI NaN blowout
- **Assumption challenged**: Inputs are clean and lack middle NaNs.
- **Attack scenario**: A brief network glitch or yfinance API scrape error outputs a single `NaN` in a close price series.
- **Blast radius**: All subsequent RSI signals become `NaN`, disabling all RSI-based trading rules.
- **Mitigation**: Wrap Wilder's loop calculations to ignore or interpolate NaNs.

---

## 5. Verification Method
1. Run pytest suite:
   ```bash
   python3 -m pytest tests/
   ```
2. Inspect `automation/data_client.py` at lines 99–103 to verify the lock release position relative to `df.copy()`.
3. Inspect `automation/indicators.py` at lines 68–72 to verify how DatetimeIndex is checked on a MultiIndex.
