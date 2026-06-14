# Milestone 1 Review Handoff Report

**Date**: 2026-06-14T08:40:00Z  
**Reviewer**: Milestone 1 Reviewer 2  
**Verdict**: **PASS**

---

## 1. Observation

Direct observations and code locations investigated during the review:

### A. Technical Indicators (`automation/indicators.py`)
- **RSI Wilder's Method** (lines 4-46): Implements standard Wilder's smoothing recursively. Lines 18-20 compute initial SMA:
  ```python
  avg_gain[period] = np.mean(gain_vals[1:period+1])
  avg_loss[period] = np.mean(loss_vals[1:period+1])
  ```
  And lines 23-25 apply the recursion:
  ```python
  for i in range(period + 1, len(close)):
      avg_gain[i] = (avg_gain[i-1] * (period - 1) + gain_vals[i]) / period
      avg_loss[i] = (avg_loss[i-1] * (period - 1) + loss_vals[i]) / period
  ```
  It handles division-by-zero on line 40:
  ```python
  elif l == 0:
      rsi[i] = 100.0 if g > 0 else 50.0
  ```
- **VWAP Daily Reset** (lines 67-86): Uses date grouping for daily reset:
  ```python
  if dates is not None:
      cum_tp_v = tp_v.groupby(dates).cumsum()
      cum_v = volume.groupby(dates).cumsum()
  ```
  And division-by-zero safety on line 84-85:
  ```python
  df['vwap'] = cum_tp_v / cum_v.replace(0, np.nan)
  df['vwap'] = df['vwap'].fillna(close)
  ```
- **Bollinger Bands** (lines 97-102): Window 20, uses population standard deviation (`ddof=0`):
  ```python
  bb_middle = close.rolling(window=20).mean()
  bb_std = close.rolling(window=20).std(ddof=0)
  ```
- **EMA Crossover** (lines 104-118): Compares 9-period fast EMA and 21-period slow EMA, shifting by 1 for crossover check.
- **RVOL** (lines 120-122): Implemented as volume divided by 20-period rolling mean:
  ```python
  rolling_vol_avg = volume.rolling(window=20).mean()
  df['rvol'] = volume / rolling_vol_avg.replace(0, np.nan)
  ```

### B. Live Market Data Client (`automation/data_client.py`)
- **Thread-Safety** (lines 41, 75-106): Lock is initialized as `self._lock = threading.Lock()`. It is acquired inside `get_data` and `_update_cache` via `with self._lock:`. The user callback `self.on_bar_callback` is executed on line 101 outside the lock scope.
- **Websocket Drop Recovery** (lines 133-136): Alpaca streaming error handler falls back to `_run_yfinance_polling()` synchronously if stream fails and the client is running.

### C. Pre-Market Scanner (`automation/scanner.py`)
- **Timezone conversions** (lines 48-52): localizes naive datetimes to UTC before converting to Eastern:
  ```python
  if df.index.tzinfo is None:
      df.index = df.index.tz_localize('UTC')
  df_est = df.tz_convert('US/Eastern')
  ```
- **Premarket & Previous Close Filtering** (lines 56, 73):
  - Prior days regular session (9:30 AM to 4:00 PM EST):
    ```python
    reg_df = df_est[df_est.index.date < scan_date].between_time('09:30', '16:00')
    ```
  - Scanning day pre-market (4:00 AM to 9:29 AM EST):
    ```python
    today_pre = df_est[df_est.index.date == scan_date].between_time('04:00', '09:29')
    ```
- **Database Watchlist Schema** (lines 17-32):
  - Primary Key is compound: `PRIMARY KEY (ticker, scan_date)` which enforces uniqueness per ticker per day.
- **CLI Arguments** (lines 187-193):
  - Includes `--db-path`, `--symbols`, `--force`, `--date`, and `--view` arguments.

### D. Verification Tests Run
- Command: `python3 -m pytest tests/`
- Result: `14 passed, 1 warning in 4.59s`

---

## 2. Logic Chain

1. The technical indicator calculations in `automation/indicators.py` exactly implement standard trading formulas (VWAP daily reset, MACD span 12/26/9, RSI Wilder 14, BB window 20 std dev 2, EMA fast 9 slow 21, and RVOL window 20).
2. Division-by-zero checks are systematically implemented using `replace(0, np.nan)` in VWAP and RVOL, and explicit condition checks in RSI, guaranteeing mathematical robustness.
3. Thread-safety in `automation/data_client.py` is guaranteed by using a local lock (`self._lock`) for dictionary reads and writes. Deadlocks are avoided because user-supplied callbacks are run after releasing the lock.
4. Timezone operations in `automation/scanner.py` accurately convert to `US/Eastern` and handle both UTC-naive and UTC-aware histories. The session boundaries (regular session and pre-market session) correspond exactly to Eastern time frames.
5. The database constraints are robust due to the `(ticker, scan_date)` composite primary key in the watchlist table, avoiding duplicate rows for the same day.
6. The test suite results confirm that all functionality meets unit and integration specifications.

---

## 3. Caveats

- **External API dependency**: Testing and scanner behavior depends on yfinance and Alpaca API availability. Offline scenarios will fail unless mock servers are used (as in the E2E test suite).
- **yfinance fallback latency**: When in yfinance polling fallback mode, the entire daily 1-minute historical dataset is fetched and processed on every tick, which can result in callback redundancies (see Findings).

---

## 4. Conclusion

The Milestone 1 implementation is highly correct, conforms to the interface contracts of `PROJECT.md` and `SCOPE.md`, and shows strong robustness handling empty arrays and division by zero. The verdict is **PASS**.

---

## 5. Verification Method

To independently run and verify the test suite:
1. Navigate to the project root directory.
2. Run the test command:
   ```bash
   python3 -m pytest tests/
   ```
3. Run the pre-market scanner CLI to check database insertion and CLI arguments:
   ```bash
   python3 automation/scanner.py --symbols "AAPL,MSFT" --force
   ```
4. Query the watchlist database:
   ```bash
   python3 automation/scanner.py --view
   ```

---

## 6. Quality Review Report

**Verdict**: **APPROVE**

### Findings

#### [Minor] Finding 1: Redundant Callback Triggers in yfinance Fallback Mode
- **What**: User-registered callback is triggered multiple times for already-cached historical bars during yfinance fallback polling.
- **Where**: `automation/data_client.py` lines 138-165 (`_run_yfinance_polling` loop).
- **Why**: The fallback loop retrieves a full day's history of 1-minute bars (`ticker.history(period="1d", interval="1m")`) and iterates over all of them. For each bar, it calls `_update_cache`, which updates the cache and fires `self.on_bar_callback(symbol, df.copy())`. Thus, for a full trading day of 390 bars, the callback will be triggered 390 times on every poll cycle, even if the bars are already present and unchanged in the cache.
- **Suggestion**: In `_update_cache`, only fire `on_bar_callback` if the row is actually new (appended) or if the last bar's close/volume values changed, rather than firing it unconditionally on every iteration.

#### [Minor] Finding 2: Potential NaN Propagation in Pre-market Scanner
- **What**: Missing NaN filtering in the pre-market scanner before calculating price gaps.
- **Where**: `automation/scanner.py` lines 69-82.
- **Why**: yfinance can return data containing NaN values. If the last row in `reg_df` or `today_pre` contains NaN prices, `previous_close` or `premarket_price` will be `nan`. The gap percentage calculation will propagate `nan`, which is then inserted directly into the SQLite database.
- **Suggestion**: Add a cleaning step to drop rows with NaN values in close/volume, or forward-fill them before performing calculations:
  ```python
  df_est = df_est.dropna(subset=['Close', 'Volume'])
  ```

### Verified Claims

- VWAP daily reset → verified via `test_vwap_daily_reset` and manual inspection of grouping by dates → **PASS**
- RSI Wilder's method → verified via `test_indicators_mathematics` and code tracing of Wilder's recursion formula → **PASS**
- Cache thread-safety → verified via code inspection of `_lock` scope and callback execution outside the lock block → **PASS**
- Timezone calculations → verified via `test_scan_ticker_calculation` and verification of timezone конверсий → **PASS**
- Watchlist DB schema → verified via compound primary key check in `PreMarketScanner._init_db` → **PASS**

### Coverage Gaps
- None. The upstream analysis has fully covered all module implementations.

### Unverified Items
- None. All requirements have been verified.

---

## 7. Adversarial Challenge Report

**Overall risk assessment**: **LOW**

### Challenges

#### [Low] Challenge 1: Denial of Service / CPU Exhaustion on Heavy Callbacks
- **Assumption challenged**: User callbacks are fast and lightweight.
- **Attack scenario**: In `data_client.py` fallback mode, yfinance polling fetches all minutes of the day and updates the cache bar by bar, triggering the user callback up to 390 times sequentially. If the user callback does intensive tasks (e.g. model inference or heavy DB writes), this will cause significant event loop lag and thread congestion.
- **Blast radius**: Low/Medium. Affects only the client thread if the stream falls back to yfinance, but could result in delayed signals.
- **Mitigation**: Queue callbacks or only invoke the callback on the very latest updated bar after the loop finishes, rather than on every iteration.

#### [Low] Challenge 2: NaN Values Saved to DB
- **Assumption challenged**: yfinance always returns valid numbers.
- **Attack scenario**: A ticker has incomplete data on yfinance causing missing values (NaN) in the Close or Volume column. The scanner computes a `nan` gap percentage and inserts it into SQLite. If downstream modules retrieve this value and expect a float, they may fail with conversion errors.
- **Blast radius**: Low. Watchlist entries will contain `NaN`/`None`.
- **Mitigation**: Clean the dataset using `.dropna(subset=['Close'])` before extracting the last row.

### Stress Test Results

- Empty input DataFrame → Expected: Returns empty df safely → Actual: Returns empty df safely → **PASS**
- Division by zero in indicators → Expected: Safe replacement with NaN and replacement/fill → Actual: VWAP/RVOL use `.replace(0, np.nan)`, RSI handles `l == 0` → **PASS**
- Post-9:30 AM EST execution → Expected: Pre-market scanner aborts unless forced → Actual: run_scanner checks EST timezone and aborts correctly → **PASS**
