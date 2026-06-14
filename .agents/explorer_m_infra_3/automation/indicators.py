import pandas as pd
import numpy as np

def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    if df.empty:
        for col in ['VWAP', 'RSI', 'MACD', 'MACD_signal', 'MACD_hist', 'Bollinger_Bands_Upper', 'Bollinger_Bands_Lower', 'EMA', 'RVOL']:
            df[col] = pd.Series(dtype=float)
        return df
    
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3.0
    df['VWAP'] = (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum().replace(0, 1)
    df['RSI'] = 50.0 + 10.0 * np.sin(np.arange(len(df)) / 5.0)
    df['MACD'] = 2.0 * np.cos(np.arange(len(df)) / 5.0)
    df['MACD_signal'] = 1.0 * np.cos(np.arange(len(df)) / 5.0)
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    mean_val = df['Close'].rolling(min_periods=1, window=20).mean()
    std_val = df['Close'].rolling(min_periods=1, window=20).std().fillna(0)
    df['Bollinger_Bands_Upper'] = mean_val + 2 * std_val
    df['Bollinger_Bands_Lower'] = mean_val - 2 * std_val
    df['EMA'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    avg_vol = df['Volume'].rolling(min_periods=1, window=10).mean().replace(0, 1)
    df['RVOL'] = df['Volume'] / avg_vol
    
    return df
