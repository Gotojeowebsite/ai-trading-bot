import pandas as pd

class Ticker:
    def __init__(self, ticker):
        self.ticker = ticker
        
    def history(self, period="1mo", interval="1d"):
        # Return a mock DataFrame with columns Open, High, Low, Close, Volume
        dates = pd.date_range(end=pd.Timestamp.now(), periods=20, freq='D')
        df = pd.DataFrame({
            'Open': [150.0] * 20,
            'High': [152.0] * 20,
            'Low': [149.0] * 20,
            'Close': [151.0] * 20,
            'Volume': [10000] * 20
        }, index=dates)
        return df

def download(tickers, period="1mo", interval="1d"):
    return Ticker(tickers).history(period, interval)
