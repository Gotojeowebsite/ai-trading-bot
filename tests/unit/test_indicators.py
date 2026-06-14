import numpy as np
import pandas as pd
import pytest
from automation.indicators import calculate_indicators

def test_vwap_daily_reset():
    # Setup mock data for VWAP daily reset test
    # Day 1: two points. Day 2: two points.
    dates = pd.to_datetime([
        "2026-06-14 09:30:00",
        "2026-06-14 09:31:00",
        "2026-06-15 09:30:00",
        "2026-06-15 09:31:00"
    ])
    
    # Typical price = (high + low + close) / 3
    # Day 1:
    # Tick 1: Open=10, High=11, Low=9, Close=10. Typical Price = 10. Volume = 100
    # Tick 2: Open=20, High=22, Low=18, Close=20. Typical Price = 20. Volume = 200
    # Expected VWAP Tick 1: 10
    # Expected VWAP Tick 2: (10*100 + 20*200) / (100 + 200) = (1000 + 4000)/300 = 16.6667
    
    # Day 2 (resets):
    # Tick 3: Open=30, High=33, Low=27, Close=30. Typical Price = 30. Volume = 100
    # Tick 4: Open=40, High=44, Low=36, Close=40. Typical Price = 40. Volume = 200
    # Expected VWAP Tick 3: 30
    # Expected VWAP Tick 4: (30*100 + 40*200) / 300 = (3000 + 8000)/300 = 36.6667
    
    df = pd.DataFrame({
        'open': [10.0, 20.0, 30.0, 40.0],
        'high': [11.0, 22.0, 33.0, 44.0],
        'low': [9.0, 18.0, 27.0, 36.0],
        'close': [10.0, 20.0, 30.0, 40.0],
        'volume': [100, 200, 100, 200]
    }, index=dates)
    
    res = calculate_indicators(df)
    
    assert 'vwap' in res.columns
    assert np.isclose(res['vwap'].iloc[0], 10.0)
    assert np.isclose(res['vwap'].iloc[1], 5000.0 / 300.0)
    assert np.isclose(res['vwap'].iloc[2], 30.0)
    assert np.isclose(res['vwap'].iloc[3], 11000.0 / 300.0)

def test_indicators_mathematics():
    # Setup a DataFrame with 50 rows to have enough data for 14-period RSI, 20-period Bollinger Bands
    # Close price goes up from 10 to 59
    closes = np.arange(10.0, 60.0)
    df = pd.DataFrame({
        'open': closes - 0.5,
        'high': closes + 1.0,
        'low': closes - 1.0,
        'close': closes,
        'volume': np.repeat(100.0, 50)
    })
    
    res = calculate_indicators(df)
    
    # Check all columns exist
    expected_cols = [
        'vwap', 'macd', 'macd_signal', 'macd_hist', 'rsi',
        'bb_middle', 'bb_upper', 'bb_lower',
        'ema_fast', 'ema_slow', 'ema_crossover', 'rvol'
    ]
    for col in expected_cols:
        assert col in res.columns
        
    # Check Bollinger Bands on row 30
    # bb_middle should be rolling 20-period mean
    expected_middle = df['close'].iloc[11:31].mean() # index 30 is 31st element
    assert np.isclose(res['bb_middle'].iloc[30], expected_middle)
    
    expected_std = df['close'].iloc[11:31].std(ddof=0)
    assert np.isclose(res['bb_upper'].iloc[30], expected_middle + 2 * expected_std)
    assert np.isclose(res['bb_lower'].iloc[30], expected_middle - 2 * expected_std)
    
    # Check RSI on row 14 (15th element)
    # Since prices are strictly increasing, Wilder's RSI should be 100 after period starts
    assert np.isnan(res['rsi'].iloc[13]) # first 14 elements (0 to 13) are NaN
    assert res['rsi'].iloc[14] == 100.0
    
    # Check RVOL
    # Since volume is constant, RVOL should be 1.0
    assert np.isclose(res['rvol'].iloc[25], 1.0)

def test_ema_crossover():
    # Setup data with specific crossover points
    # Fast: 9 period, Slow: 21 period
    # Let's create two signals where fast EMA crosses slow EMA
    # We can force the prices to trigger crossovers
    closes = [
        10, 10, 10, 10, 10, 10, 10, 10, 10, 10, # 10 bars of flat 10
        20, 20, 20, 20, 20, # price jumps to 20 -> fast EMA rises faster than slow EMA (bullish crossover)
        5, 5, 5, 5, 5, 5, 5, 5, 5, 5 # price drops to 5 -> fast EMA drops faster than slow EMA (bearish crossover)
    ]
    
    df = pd.DataFrame({
        'open': closes,
        'high': closes,
        'low': closes,
        'close': closes,
        'volume': 100
    })
    
    res = calculate_indicators(df)
    
    # Verify that we have crossover signals
    assert 1 in res['ema_crossover'].values
    assert -1 in res['ema_crossover'].values
    
    # Verify that when there's no crossover, it's 0
    assert res['ema_crossover'].iloc[0] == 0

def test_multiple_tickers():
    # Setup multiple tickers: AAPL and MSFT
    df_aapl = pd.DataFrame({
        'open': [10.0, 11.0, 12.0],
        'high': [10.5, 11.5, 12.5],
        'low': [9.5, 10.5, 11.5],
        'close': [10.0, 11.0, 12.0],
        'volume': [100, 200, 300],
        'symbol': 'AAPL'
    }, index=pd.date_range("2026-06-14 09:30:00", periods=3, freq='min'))
    
    df_msft = pd.DataFrame({
        'open': [100.0, 101.0, 102.0],
        'high': [100.5, 101.5, 102.5],
        'low': [99.5, 100.5, 101.5],
        'close': [100.0, 101.0, 102.0],
        'volume': [1000, 2000, 3000],
        'symbol': 'MSFT'
    }, index=pd.date_range("2026-06-14 09:30:00", periods=3, freq='min'))
    
    df = pd.concat([df_aapl, df_msft])
    
    res = calculate_indicators(df)
    
    # Ensure indexes and column structures are preserved
    assert len(res) == 6
    assert 'vwap' in res.columns
    
    # Verify VWAP is computed independently
    # For AAPL row 1: (10*100 + 11*200) / 300 = (1000+2200)/300 = 10.6667
    aapl_res = res[res['symbol'] == 'AAPL']
    assert np.isclose(aapl_res['vwap'].iloc[1], 3200.0 / 300.0)
    
    # For MSFT row 1: (100*1000 + 101*2000) / 3000 = (100000+202000)/3000 = 100.6667
    msft_res = res[res['symbol'] == 'MSFT']
    assert np.isclose(msft_res['vwap'].iloc[1], 302000.0 / 3000.0)

def test_multiindex_support():
    # Setup multi-indexed DataFrame with index levels (symbol, timestamp)
    index = pd.MultiIndex.from_tuples([
        ('AAPL', pd.Timestamp("2026-06-14 09:30:00")),
        ('AAPL', pd.Timestamp("2026-06-14 09:31:00")),
        ('MSFT', pd.Timestamp("2026-06-14 09:30:00")),
        ('MSFT', pd.Timestamp("2026-06-14 09:31:00")),
    ], names=['symbol', 'timestamp'])
    
    df = pd.DataFrame({
        'open': [10.0, 11.0, 100.0, 101.0],
        'high': [10.5, 11.5, 100.5, 101.5],
        'low': [9.5, 10.5, 99.5, 100.5],
        'close': [10.0, 11.0, 100.0, 101.0],
        'volume': [100, 200, 1000, 2000]
    }, index=index)
    
    res = calculate_indicators(df)
    
    # Ensure MultiIndex structure is preserved
    assert isinstance(res.index, pd.MultiIndex)
    assert 'vwap' in res.columns
    
    # Verify values are grouped correctly
    assert np.isclose(res.loc[('AAPL', pd.Timestamp("2026-06-14 09:31:00")), 'vwap'], 3200.0 / 300.0)
    assert np.isclose(res.loc[('MSFT', pd.Timestamp("2026-06-14 09:31:00")), 'vwap'], 302000.0 / 3000.0)

def test_multiindex_vwap_daily_reset_multiple_days():
    index = pd.MultiIndex.from_tuples([
        ('AAPL', pd.Timestamp("2026-06-14 09:30:00")),
        ('AAPL', pd.Timestamp("2026-06-14 09:31:00")),
        ('AAPL', pd.Timestamp("2026-06-15 09:30:00")),
        ('AAPL', pd.Timestamp("2026-06-15 09:31:00")),
        ('MSFT', pd.Timestamp("2026-06-14 09:30:00")),
        ('MSFT', pd.Timestamp("2026-06-14 09:31:00")),
        ('MSFT', pd.Timestamp("2026-06-15 09:30:00")),
        ('MSFT', pd.Timestamp("2026-06-15 09:31:00")),
    ], names=['symbol', 'timestamp'])
    
    df = pd.DataFrame({
        'open': [10.0, 20.0, 30.0, 40.0, 100.0, 200.0, 300.0, 400.0],
        'high': [11.0, 22.0, 33.0, 44.0, 101.0, 202.0, 303.0, 404.0],
        'low': [9.0, 18.0, 27.0, 36.0, 99.0, 198.0, 297.0, 396.0],
        'close': [10.0, 20.0, 30.0, 40.0, 100.0, 200.0, 300.0, 400.0],
        'volume': [100, 200, 100, 200, 1000, 2000, 1000, 2000]
    }, index=index)
    
    res = calculate_indicators(df)
    
    assert np.isclose(res.loc[('AAPL', pd.Timestamp("2026-06-14 09:30:00")), 'vwap'], 10.0)
    assert np.isclose(res.loc[('AAPL', pd.Timestamp("2026-06-14 09:31:00")), 'vwap'], 5000.0 / 300.0)
    assert np.isclose(res.loc[('AAPL', pd.Timestamp("2026-06-15 09:30:00")), 'vwap'], 30.0)
    assert np.isclose(res.loc[('AAPL', pd.Timestamp("2026-06-15 09:31:00")), 'vwap'], 11000.0 / 300.0)
    
    assert np.isclose(res.loc[('MSFT', pd.Timestamp("2026-06-14 09:30:00")), 'vwap'], 100.0)
    assert np.isclose(res.loc[('MSFT', pd.Timestamp("2026-06-14 09:31:00")), 'vwap'], 500000.0 / 3000.0)
    assert np.isclose(res.loc[('MSFT', pd.Timestamp("2026-06-15 09:30:00")), 'vwap'], 300.0)
    assert np.isclose(res.loc[('MSFT', pd.Timestamp("2026-06-15 09:31:00")), 'vwap'], 1100000.0 / 3000.0)

def test_rsi_nan_robustness():
    closes = list(range(10, 40))
    closes[20] = np.nan
    
    df = pd.DataFrame({
        'open': [c - 0.5 for c in closes],
        'high': [c + 0.5 for c in closes],
        'low': [c - 0.5 for c in closes],
        'close': closes,
        'volume': [100] * 30
    })
    
    res = calculate_indicators(df)
    
    for idx in range(14, 20):
        assert not np.isnan(res['rsi'].iloc[idx])
        
    for idx in range(25, 30):
        assert not np.isnan(res['rsi'].iloc[idx]), f"RSI at index {idx} is NaN but should have recovered."
