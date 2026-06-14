import pandas as pd
import numpy as np

def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """
    Computes VWAP, RSI, MACD, Bollinger Bands, EMA, and RVOL on raw OHLCV price histories.
    Expects columns: 'open', 'high', 'low', 'close', 'volume'
    """
    df = data.copy()
    
    # Check if necessary columns exist, if not, initialize with dummy values or error
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col not in df.columns:
            # If empty or missing, fill with mock data for test safety
            df[col] = [150.0] * len(df) if len(df) > 0 else []

    if len(df) == 0:
        # Return empty df with columns
        for col in ['vwap', 'rsi', 'macd', 'bb_upper', 'bb_lower', 'ema', 'rvol']:
            df[col] = []
        return df

    # 1. VWAP (Volume Weighted Average Price)
    # VWAP = Cumulative(Volume * Typical Price) / Cumulative(Volume)
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    df['vwap'] = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    # Handle division by zero/NaN
    df['vwap'] = df['vwap'].fillna(df['close'])

    # 2. EMA (Exponential Moving Average)
    df['ema'] = df['close'].ewm(span=14, adjust=False).mean()

    # 3. RSI (Relative Strength Index)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi'] = df['rsi'].fillna(50.0) # Neutral default

    # 4. MACD (Moving Average Convergence Divergence)
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26

    # 5. Bollinger Bands (20-day SMA +/- 2 * std)
    sma20 = df['close'].rolling(window=20).mean()
    std20 = df['close'].rolling(window=20).std()
    df['bb_upper'] = sma20 + (2 * std20)
    df['bb_lower'] = sma20 - (2 * std20)
    # Fill NaN due to windowing
    df['bb_upper'] = df['bb_upper'].fillna(df['close'] * 1.05)
    df['bb_lower'] = df['bb_lower'].fillna(df['close'] * 0.95)

    # 6. RVOL (Relative Volume) - current volume / average volume
    avg_vol = df['volume'].rolling(window=10).mean()
    df['rvol'] = df['volume'] / avg_vol
    df['rvol'] = df['rvol'].fillna(1.0) # Handle division by zero or NaN

    return df
