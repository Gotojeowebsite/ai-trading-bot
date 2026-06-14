# Scope: Milestone 1 — Market Data & Technical Indicators

## Architecture
Milestone 1 establishes the foundational data ingestion and technical analysis layer of the AI Trading Bot. The modules reside in the `automation/` folder and interact as follows:
1. **Live Market Data Client**: Connects to Alpaca WebSocket (real-time stream) or yfinance (polling/historical fetch fallback) to stream or retrieve OHLCV bars.
2. **Indicator Module**: Computes core day-trading technical indicators (VWAP, MACD, RSI, Bollinger Bands, EMA crossovers, RVOL) on pandas DataFrames of raw price history.
3. **Pre-market Scanner**: Evaluates market opportunities before 9:30 AM EST by screening stocks on pre-market volume, price gap percentage, and news catalysts.

## Target Modules & Code Layout
- `automation/data_client.py`: Ingestion client for real-time market data (via Alpaca WebSocket or yfinance).
- `automation/indicators.py`: Technical indicator library matching the interface contract.
- `automation/scanner.py`: Pre-market scanner logic and scheduling.

## Interface Contracts
### `automation/indicators.py`
- `def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame`:
  - **Inputs**: `data` (pandas DataFrame with columns `open`, `high`, `low`, `close`, `volume`, and optionally `timestamp` or DatetimeIndex).
  - **Outputs**: DataFrame with the original columns plus the computed indicators:
    - `vwap`: Volume Weighted Average Price.
    - `macd`, `macd_signal`, `macd_hist`: MACD indicator components.
    - `rsi`: Relative Strength Index.
    - `bb_upper`, `bb_middle`, `bb_lower`: Bollinger Bands (20-period, 2 std dev).
    - `ema_fast`, `ema_slow`, `ema_crossover`: EMA components (e.g., 9-period and 21-period EMAs, and crossover signals: 1 for bullish crossover, -1 for bearish, 0 otherwise).
    - `rvol`: Relative Volume (current volume compared to average volume over a baseline window, e.g. 20 periods).

### `automation/data_client.py`
- Establish connection to Alpaca WebSocket (with paper/live config support) or fall back to yfinance to continuously receive updates.
- Save or expose raw/aggregated OHLCV data for technical indicator computation.

### `automation/scanner.py`
- Identify top stocks to watch before 9:30 AM EST.
- Filter by:
  - Gap percentage (difference between previous close and current pre-market price).
  - Pre-market volume.
  - News catalysts (if news/sentiment data is available).

## Milestones / Components
| # | Component Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Indicators Module | Build `automation/indicators.py` and verify all required technical indicator calculations. | None | PLANNED |
| 2 | Live Market Data Client | Build `automation/data_client.py` using Alpaca WebSocket or yfinance. | None | PLANNED |
| 3 | Pre-market Scanner | Build `automation/scanner.py` to identify top stocks before 9:30 AM EST. | 1, 2 | PLANNED |
| 4 | Verification & Auditing | Run full unit/functional tests on components and pass forensic integrity audit. | 1, 2, 3 | PLANNED |
