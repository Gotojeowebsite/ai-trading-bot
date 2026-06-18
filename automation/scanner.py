import argparse
import logging
import sqlite3
import re
from datetime import datetime
from typing import List, Dict, Optional
import pytz
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

def is_valid_symbol(symbol: str) -> bool:
    """Sanitize and validate a symbol to reject malformed ticker strings."""
    if not symbol or len(symbol) > 15:
        return False
    # Only allow alphanumeric, dot, dash, caret, equals
    return bool(re.match(r'^[A-Za-z0-9.\-^=]+$', symbol))

class PreMarketScanner:
    def __init__(self, db_path: str, symbols: List[str]):
        self.db_path = db_path
        self.symbols = symbols
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT,
                scan_date TEXT,
                gap_percentage REAL,
                premarket_volume INTEGER,
                news_catalyst TEXT,
                timestamp TEXT,
                PRIMARY KEY (ticker, scan_date)
            )
        """)
        conn.commit()
        conn.close()
        
    def scan_ticker(self, symbol: str, current_time_est: datetime) -> dict:
        try:
            ticker = yf.Ticker(symbol)
            # Fetch 2 days of 1m data with prepost=True
            df = ticker.history(period="2d", interval="1m", prepost=True)
            if df.empty:
                logger.warning(f"No history returned for {symbol}")
                return {
                    'ticker': symbol,
                    'gap_percentage': 0.0,
                    'premarket_volume': 0,
                    'news_catalyst': 'No historical data'
                }
            
            # Clean historical DataFrame using dropna on Close and Volume columns
            cols_to_check = [c for c in ['Close', 'Volume'] if c in df.columns]
            if cols_to_check:
                df = df.dropna(subset=cols_to_check)
                
            if df.empty:
                logger.warning(f"No history returned for {symbol} after dropna")
                return {
                    'ticker': symbol,
                    'gap_percentage': 0.0,
                    'premarket_volume': 0,
                    'news_catalyst': 'No historical data'
                }
                
            df.index = pd.to_datetime(df.index, utc=True)
            df_est = df.tz_convert('US/Eastern')
            
            scan_date = current_time_est.date()
            
            # 1. Previous regular session close:
            # Look at prior days, between 9:30 AM and 4:00 PM EST
            reg_df = df_est[df_est.index.date < scan_date].between_time('09:30', '16:00')
            if reg_df.empty:
                # Fallback to daily bars for previous close
                daily_df = ticker.history(period="5d", interval="1d")
                if not daily_df.empty:
                    valid_daily = daily_df[daily_df.index.date < scan_date]
                    if not valid_daily.empty:
                        previous_close = float(valid_daily['Close'].iloc[-1])
                    else:
                        previous_close = float(daily_df['Close'].iloc[-1])
                else:
                    previous_close = float(df_est['Close'].iloc[0])
            else:
                previous_close = float(reg_df['Close'].iloc[-1])
                
            # 2. Current pre-market:
            # Today's date, between 4:00 AM and 9:29 AM EST
            today_pre = df_est[df_est.index.date == scan_date].between_time('04:00', '09:29')
            if not today_pre.empty:
                premarket_volume = int(today_pre['Volume'].sum())
                premarket_price = float(today_pre['Close'].iloc[-1])
            else:
                premarket_volume = 0
                premarket_price = previous_close
                
            if previous_close != 0:
                gap_percentage = ((premarket_price - previous_close) / previous_close) * 100.0
            else:
                gap_percentage = 0.0
                
            # Get news catalyst
            news_catalyst = 'None'
            try:
                news = ticker.news
                if news and len(news) > 0:
                    news_catalyst = news[0].get('title', 'None')
            except Exception:
                pass
                
            return {
                'ticker': symbol,
                'gap_percentage': gap_percentage,
                'premarket_volume': premarket_volume,
                'news_catalyst': news_catalyst,
                'previous_close': previous_close,
                'premarket_price': premarket_price
            }
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return {
                'ticker': symbol,
                'gap_percentage': 0.0,
                'premarket_volume': 0,
                'news_catalyst': f"Error: {str(e)}"
            }
            
    def save_to_db(self, scan_results: List[dict], scan_date_str: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        for res in scan_results:
            cursor.execute("""
                INSERT OR REPLACE INTO watchlist (ticker, scan_date, gap_percentage, premarket_volume, news_catalyst, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (res['ticker'], scan_date_str, res['gap_percentage'], res['premarket_volume'], res['news_catalyst'], timestamp))
        conn.commit()
        conn.close()

def view_watchlist(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, scan_date, gap_percentage, premarket_volume, news_catalyst, timestamp 
        FROM watchlist 
        ORDER BY scan_date DESC, ABS(gap_percentage) DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("No watchlist records found.")
        return
        
    print(f"{'Ticker':<8} | {'Scan Date':<10} | {'Gap %':<8} | {'Premarket Vol':<13} | {'News Catalyst':<40} | {'Timestamp':<26}")
    print("-" * 115)
    for row in rows:
        ticker, scan_date, gap, vol, news, ts = row
        print(f"{ticker:<8} | {scan_date:<10} | {gap:>7.2f}% | {vol:>13,} | {news[:40]:<40} | {ts:<26}")

def run_scanner(db_path: str, symbols: List[str], force: bool = False, date_override: Optional[str] = None):
    eastern = pytz.timezone('US/Eastern')
    now_est = datetime.now(eastern)
    
    if date_override:
        try:
            try:
                now_est = eastern.localize(datetime.strptime(date_override, "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                now_est = eastern.localize(datetime.strptime(date_override, "%Y-%m-%d"))
        except Exception as e:
            print(f"Error parsing date override '{date_override}': {e}. Using current time.")
            
    if not force:
        cutoff = now_est.replace(hour=9, minute=30, second=0, microsecond=0)
        if now_est >= cutoff:
            print(f"Current EST time {now_est.strftime('%H:%M:%S')} is after the 9:30 AM cutoff. Pre-market scanner aborted. Use --force to run anyway.")
            return []
            
    print(f"Running Pre-Market Scanner for symbols: {symbols} at {now_est.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    scanner = PreMarketScanner(db_path, symbols)
    
    results = []
    for sym in symbols:
        print(f"Scanning {sym}...")
        res = scanner.scan_ticker(sym, now_est)
        results.append(res)
        
    # Rank by absolute gap percentage
    results.sort(key=lambda x: abs(x['gap_percentage']), reverse=True)
    
    scan_date_str = now_est.strftime('%Y-%m-%d')
    scanner.save_to_db(results, scan_date_str)
    
    print("\nScan Results (Ranked by absolute Gap %):")
    print(f"{'Ticker':<8} | {'Gap %':<8} | {'Premarket Vol':<13} | {'News Catalyst':<40}")
    print("-" * 75)
    for res in results:
        print(f"{res['ticker']:<8} | {res['gap_percentage']:>7.2f}% | {res['premarket_volume']:>13,} | {res['news_catalyst'][:40]:<40}")
        
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-Market Scanner")
    parser.add_argument("--db-path", default="watchlist.db", help="Path to SQLite database")
    parser.add_argument("--symbols", default="AAPL,MSFT,GOOG,AMZN,NVDA,TSLA", help="Comma-separated ticker list")
    parser.add_argument("--force", action="store_true", help="Bypass 9:30 AM EST restrictions")
    parser.add_argument("--date", help="Override scan date in YYYY-MM-DD format")
    parser.add_argument("--view", action="store_true", help="View the historical scan results from the database")
    
    args = parser.parse_args()
    
    if args.view:
        view_watchlist(args.db_path)
    else:
        symbols_list = []
        for s in args.symbols.split(","):
            s_clean = s.strip()
            if not s_clean:
                continue
            if not is_valid_symbol(s_clean):
                raise ValueError(f"Malformed ticker string detected: '{s_clean}'")
            symbols_list.append(s_clean)
        run_scanner(args.db_path, symbols_list, force=args.force, date_override=args.date)
