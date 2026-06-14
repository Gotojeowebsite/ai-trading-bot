import numpy as np
import pandas as pd

def _calculate_wilders_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    if len(close) <= period:
        return pd.Series(np.nan, index=close.index)
        
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    alpha = 1 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    zero_loss_rsi = pd.Series(np.nan, index=close.index)
    zero_loss_rsi.loc[(avg_loss == 0) & (avg_gain > 0)] = 100.0
    zero_loss_rsi.loc[(avg_loss == 0) & (avg_gain == 0)] = 50.0
    
    rsi = rsi.fillna(zero_loss_rsi)
    rsi.iloc[:period] = np.nan
    
    return rsi

def _calculate_indicators_single(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    # Ensure necessary columns exist
    required = ['open', 'high', 'low', 'close', 'volume']
    for col in required:
        if col not in df.columns:
            if col.upper() in df.columns:
                df[col] = df[col.upper()]
            elif col.capitalize() in df.columns:
                df[col] = df[col.capitalize()]
            else:
                raise ValueError(f"Missing required column: {col}")
                
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    # 1. VWAP (resets daily if datetime timestamp exists)
    dates = None
    if isinstance(df.index, pd.MultiIndex) and 'timestamp' in df.index.names:
        dates = pd.to_datetime(df.index.get_level_values('timestamp')).date
    elif isinstance(df.index, pd.DatetimeIndex):
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
        
    df['vwap'] = cum_tp_v / cum_v.replace(0, np.nan)
    df['vwap'] = df['vwap'].fillna(close)
    
    # 2. MACD (macd, macd_signal, macd_hist)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # 3. RSI (14-period Wilder's)
    df['rsi'] = _calculate_wilders_rsi(close, 14)
    
    # 4. Bollinger Bands (20-period, 2 std dev)
    bb_middle = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std(ddof=0)
    df['bb_middle'] = bb_middle
    df['bb_upper'] = bb_middle + 2 * bb_std
    df['bb_lower'] = bb_middle - 2 * bb_std
    
    # 5. EMA Crossover (ema_fast: 9, ema_slow: 21)
    ema_fast = close.ewm(span=9, adjust=False).mean()
    ema_slow = close.ewm(span=21, adjust=False).mean()
    df['ema_fast'] = ema_fast
    df['ema_slow'] = ema_slow
    
    crossover = pd.Series(0, index=df.index, dtype=int)
    prev_fast = ema_fast.shift(1)
    prev_slow = ema_slow.shift(1)
    
    bullish = (ema_fast > ema_slow) & (prev_fast <= prev_slow)
    bearish = (ema_fast < ema_slow) & (prev_fast >= prev_slow)
    crossover[bullish] = 1
    crossover[bearish] = -1
    df['ema_crossover'] = crossover
    
    # 6. RVOL (Relative Volume: 20-period average volume)
    rolling_vol_avg = volume.rolling(window=20).mean()
    df['rvol'] = volume / rolling_vol_avg.replace(0, np.nan)
    
    # Uppercase aliases to support main.py and test expectations
    df['VWAP'] = df['vwap']
    df['RSI'] = df['rsi']
    df['MACD'] = df['macd']
    df['BB_mid'] = df['bb_middle']
    df['BB_upper'] = df['bb_upper']
    df['BB_lower'] = df['bb_lower']
    df['EMA'] = close.ewm(span=20, adjust=False).mean()
    df['RVOL'] = df['rvol']
    
    return df

def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """
    Computes VWAP, RSI, MACD, Bollinger Bands, EMA crossover, and RVOL on raw OHLCV price histories.
    Handles multiple tickers if grouped by 'symbol' or 'ticker' column, or multi-indexed.
    """
    if data.empty:
        return data.copy()
        
    group_col = None
    if 'symbol' in data.columns:
        group_col = 'symbol'
    elif 'ticker' in data.columns:
        group_col = 'ticker'
        
    group_idx_level = None
    if isinstance(data.index, pd.MultiIndex):
        for name in ['symbol', 'ticker']:
            if name in data.index.names:
                group_idx_level = name
                break
                
    # To maintain the original row ordering and avoid duplications with non-unique indexes,
    # we inject a temporary unique ID / position column
    data_with_pos = data.copy()
    data_with_pos['_orig_pos'] = np.arange(len(data))
    
    if group_col is not None:
        results = []
        for _, group in data_with_pos.groupby(group_col, group_keys=False):
            res = _calculate_indicators_single(group)
            results.append(res)
        if results:
            combined = pd.concat(results)
            combined = combined.sort_values('_orig_pos').drop(columns=['_orig_pos'])
            return combined
        else:
            return data.copy()
            
    elif group_idx_level is not None:
        results = []
        for _, group in data_with_pos.groupby(level=group_idx_level, group_keys=False):
            res = _calculate_indicators_single(group)
            results.append(res)
        if results:
            combined = pd.concat(results)
            combined = combined.sort_values('_orig_pos').drop(columns=['_orig_pos'])
            return combined
        else:
            return data.copy()
    else:
        res = _calculate_indicators_single(data_with_pos)
        res = res.sort_values('_orig_pos').drop(columns=['_orig_pos'])
        return res
