"""
Master Trading Loop - Fully automated day trading bot.
Runs the complete daily cycle with time-aware scheduling:
  - Pre-market scan at 8:00 AM EST
  - Trading loop 9:30 AM - 3:55 PM EST
  - Auto-close all positions at 3:55 PM EST
  - Daily summary at 4:00 PM EST
  - Sleep overnight until next pre-market

Zero human intervention required once started.
"""
import os
import sys
import time
import json
import yaml
import logging
import sqlite3
import signal
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, env vars must be set manually

import pytz

from automation.indicators import calculate_indicators
from automation.scanner import run_scanner
from engine.llm_brain import tier1_screen, tier2_decide
from sentiment.finbert_client import get_sentiment
from politician.copy_mode import get_politician_signals, get_all_recent_trades
from execution.order_manager import AlpacaExecutor, IBExecutor
from notifications.alerts import notify_trade, notify_circuit_breaker, notify_daily_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("trading_bot.log")]
)
logger = logging.getLogger("trading_loop")

EST = pytz.timezone("US/Eastern")


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    logger.warning("No config.yaml found, using defaults")
    return {"watchlist": ["AAPL", "NVDA", "TSLA", "MSFT"], "llm": {}, "broker": {"mode": "paper"}}


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY, ticker TEXT, action TEXT, qty INTEGER,
        entry_price REAL, stop_loss REAL, take_profit REAL,
        confidence REAL, reasoning TEXT, timestamp TEXT, status TEXT DEFAULT 'open'
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, action TEXT,
        confidence REAL, reasoning TEXT, signals_json TEXT, timestamp TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, equity REAL, cash REAL,
        daily_pnl REAL, open_positions INTEGER, timestamp TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS signals (
        ticker TEXT PRIMARY KEY, rsi REAL, macd REAL, vwap REAL,
        rvol REAL, sentiment REAL, politician_score REAL,
        composite REAL, timestamp TEXT
    )""")
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn


def get_market_data(ticker: str) -> dict:
    """Fetch latest market data for a ticker using yfinance."""
    try:
        import yfinance as yf
        import pandas as pd

        stock = yf.Ticker(ticker)
        # Get intraday data (1-min candles for day trading)
        df = stock.history(period="1d", interval="1m")
        if df.empty:
            # Market might be closed, use daily data
            df = stock.history(period="5d", interval="5m")

        if df.empty:
            logger.warning(f"No data for {ticker}, using fallback")
            return _fallback_data(ticker)

        # Calculate indicators
        df.columns = [c.lower() for c in df.columns]
        if "adj close" in df.columns:
            df = df.rename(columns={"adj close": "close"})

        df_ind = calculate_indicators(df)
        last = df_ind.iloc[-1]

        return {
            "price": float(last.get("close", 0)),
            "vwap": float(last.get("VWAP", 0)),
            "rsi": float(last.get("RSI", 50)),
            "macd": float(last.get("MACD", 0)),
            "bb_upper": float(last.get("BB_upper", 0)),
            "bb_lower": float(last.get("BB_lower", 0)),
            "ema": float(last.get("EMA", 0)),
            "rvol": float(last.get("RVOL", 1.0)),
            "volume": float(last.get("volume", 0)),
            "bb_position": "upper" if float(last.get("close", 0)) > float(last.get("BB_upper", 999999)) else
                           "lower" if float(last.get("close", 0)) < float(last.get("BB_lower", 0)) else "middle",
            "ema_trend": "bullish" if float(last.get("close", 0)) > float(last.get("EMA", 0)) else "bearish",
        }
    except Exception as e:
        logger.error(f"Market data error for {ticker}: {e}")
        return _fallback_data(ticker)


def _fallback_data(ticker: str) -> dict:
    """Return neutral fallback data when market data is unavailable."""
    return {"price": 0, "vwap": 0, "rsi": 50, "macd": 0, "bb_upper": 0, "bb_lower": 0,
            "ema": 0, "rvol": 1.0, "volume": 0, "bb_position": "middle", "ema_trend": "neutral"}


def get_nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime.date:
    """Find the Nth occurrence of a weekday in a month (0=Monday, 6=Sunday)."""
    import datetime
    first_day = datetime.date(year, month, 1)
    days_to_add = (weekday - first_day.weekday()) % 7
    first_occurrence = first_day + datetime.timedelta(days=days_to_add)
    return first_occurrence + datetime.timedelta(weeks=n-1)


def get_last_weekday(year: int, month: int, weekday: int) -> datetime.date:
    """Find the last occurrence of a weekday in a month (0=Monday, 6=Sunday)."""
    import datetime
    if month == 12:
        next_month = datetime.date(year + 1, 1, 1)
    else:
        next_month = datetime.date(year, month + 1, 1)
    days_to_sub = (next_month.weekday() - weekday) % 7
    if days_to_sub == 0:
        days_to_sub = 7
    return next_month - datetime.timedelta(days=days_to_sub)


def get_easter_date(year: int) -> datetime.date:
    """Calculate Easter Sunday using the Anonymous Gregorian algorithm."""
    import datetime
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month = (h + L - 7 * m + 114) // 31
    day = ((h + L - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)


def is_market_holiday(dt) -> bool:
    """Check if the given date is a weekend or a US stock market holiday."""
    import datetime
    if isinstance(dt, datetime.datetime):
        d = dt.date()
    else:
        d = dt

    if d.weekday() >= 5:
        return True

    year = d.year
    holidays = set()

    # New Year's Day (Jan 1)
    ny = datetime.date(year, 1, 1)
    if ny.weekday() == 5:  # Saturday -> Friday Dec 31
        holidays.add(datetime.date(year - 1, 12, 31))
    elif ny.weekday() == 6:  # Sunday -> Monday Jan 2
        holidays.add(datetime.date(year, 1, 2))
    else:
        holidays.add(ny)

    # MLK Day (3rd Monday in Jan)
    holidays.add(get_nth_weekday(year, 1, 0, 3))

    # Presidents' Day (3rd Monday in Feb)
    holidays.add(get_nth_weekday(year, 2, 0, 3))

    # Good Friday (Easter - 2 days)
    holidays.add(get_easter_date(year) - datetime.timedelta(days=2))

    # Memorial Day (Last Monday in May)
    holidays.add(get_last_weekday(year, 5, 0))

    # Juneteenth (June 19)
    jt = datetime.date(year, 6, 19)
    if jt.weekday() == 5:
        holidays.add(datetime.date(year, 6, 18))
    elif jt.weekday() == 6:
        holidays.add(datetime.date(year, 6, 20))
    else:
        holidays.add(jt)

    # Independence Day (July 4)
    id4 = datetime.date(year, 7, 4)
    if id4.weekday() == 5:
        holidays.add(datetime.date(year, 7, 3))
    elif id4.weekday() == 6:
        holidays.add(datetime.date(year, 7, 5))
    else:
        holidays.add(id4)

    # Labor Day (1st Monday in Sep)
    holidays.add(get_nth_weekday(year, 9, 0, 1))

    # Thanksgiving Day (4th Thursday in Nov)
    holidays.add(get_nth_weekday(year, 11, 3, 4))

    # Christmas Day (Dec 25)
    xm = datetime.date(year, 12, 25)
    if xm.weekday() == 5:
        holidays.add(datetime.date(year, 12, 24))
    elif xm.weekday() == 6:
        holidays.add(datetime.date(year, 12, 26))
    else:
        holidays.add(xm)

    # Observed New Year's Day for next year if Dec 31 is a Friday
    next_ny = datetime.date(year + 1, 1, 1)
    if next_ny.weekday() == 5:
        holidays.add(datetime.date(year, 12, 31))

    return d in holidays


def calculate_macro_context() -> float:
    """Calculate macro context score between -1.0 and 1.0 based on morning research."""
    try:
        from engine.llm_brain import get_today_research
        research = get_today_research()
        if not research:
            return 0.0
        
        # 1. VIX Score
        vix = research.get("vix")
        vix_score = 0.0
        if vix is not None:
            try:
                vix = float(vix)
                vix_score = (20.0 - vix) / 10.0
                vix_score = max(-1.0, min(1.0, vix_score))
            except (ValueError, TypeError):
                pass
        
        # 2. Macro Outlook Score
        outlook = str(research.get("macro_outlook", "")).lower()
        outlook_score = 0.0
        if "bullish" in outlook or "strong" in outlook or "positive" in outlook:
            outlook_score += 0.8
        elif "bearish" in outlook or "weak" in outlook or "negative" in outlook:
            outlook_score -= 0.8
            
        # 3. Sector Trends Score
        sector_trends = research.get("sector_trends", {})
        sector_score = 0.0
        if isinstance(sector_trends, dict) and sector_trends:
            bullish_count = sum(1 for trend in sector_trends.values() if str(trend).lower() == "bullish")
            bearish_count = sum(1 for trend in sector_trends.values() if str(trend).lower() == "bearish")
            sector_score = (bullish_count - bearish_count) / len(sector_trends)
            
        scores = [vix_score, outlook_score, sector_score]
        return float(sum(scores) / len(scores))
    except Exception as e:
        logger.error(f"Error calculating macro context: {e}")
        return 0.0


class TradingBot:
    def __init__(self):
        self.config = load_config()
        db_path = self.config.get("database", {}).get("path", "trading.db")
        self.db = init_db(db_path)
        provider = self.config.get("broker", {}).get("provider", "alpaca")
        if provider == "ib":
            self.executor = IBExecutor(self.config)
        else:
            self.executor = AlpacaExecutor(self.config)
        self.watchlist = self.config.get("watchlist", [])
        self.running = True
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.tier1_calls = 0
        self.tier2_calls = 0
        self.circuit_breaker_tripped = False
        self.premarket_scan_done = False
        self.eod_close_done = False
        self.daily_summary_sent = False

        # Limits from config
        self.max_positions = self.config.get("max_concurrent_positions", 3)
        self.max_tier1 = self.config.get("llm", {}).get("max_tier1_calls_per_day", 2000)
        self.max_tier2 = self.config.get("llm", {}).get("max_tier2_calls_per_day", 300)
        self.tier1_threshold = self.config.get("tier1_opportunity_threshold", 7.0)
        self.interval = self.config.get("llm", {}).get("decision_interval_seconds", 60)

        # Time boundaries from config (EST)
        self.premarket_scan_time = self.config.get("premarket_scan_time", "08:00")
        self.trading_start = self.config.get("trading_hours_start", "09:30")
        self.trading_end = self.config.get("trading_hours_end", "15:55")

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info("🛑 Shutdown signal received")
        self.running = False

    def _now_est(self) -> datetime:
        """Get current time in EST."""
        return datetime.now(EST)

    def _time_str_to_today(self, time_str: str) -> datetime:
        """Convert HH:MM string to today's datetime in EST."""
        h, m = map(int, time_str.split(":"))
        now = self._now_est()
        return now.replace(hour=h, minute=m, second=0, microsecond=0)

    def _is_trading_day(self) -> bool:
        """Check if today is a weekday and not a US stock market holiday."""
        now = self._now_est()
        return not is_market_holiday(now.date())

    def check_circuit_breaker(self) -> bool:
        """Check if daily loss limit hit."""
        pnl = self.executor.get_daily_pnl()
        equity = self.executor.get_portfolio_value()
        if equity > 0 and pnl < 0 and abs(pnl / equity) > 0.02:  # 2% daily loss limit
            logger.critical("⚠️ CIRCUIT BREAKER: Daily loss limit (-2%) reached! Stopping trading.")
            self.circuit_breaker_tripped = True
            self.executor.close_all_positions()
            self.executor.cancel_all_orders()
            # Send notification
            notify_circuit_breaker(pnl, self.config)
            return True
        return False

    def run_premarket_scan(self):
        """Run the pre-market scanner on the watchlist."""
        logger.info("=" * 50)
        logger.info("🔍 RUNNING PRE-MARKET SCAN")
        logger.info("=" * 50)
        try:
            db_path = self.config.get("database", {}).get("path", "trading.db")
            results = run_scanner(db_path, self.watchlist, force=True)
            if results:
                # Log top movers
                for r in results[:5]:
                    gap = r.get("gap_percentage", 0)
                    vol = r.get("premarket_volume", 0)
                    arrow = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
                    logger.info(f"  {arrow} {r['ticker']}: gap {gap:+.2f}%, premarket vol {vol:,}, news: {r.get('news_catalyst', 'N/A')[:60]}")
            self.premarket_scan_done = True
        except Exception as e:
            logger.error(f"Pre-market scan error: {e}")

    def run_cycle(self, ticker: str):
        """Run one complete decision cycle for a ticker."""
        if self.circuit_breaker_tripped:
            return

        # 1. Get market data
        signals = get_market_data(ticker)
        if signals["price"] == 0:
            logger.info(f"[{ticker}] No market data available, skipping")
            return

        # 2. Get sentiment
        sentiment_data = get_sentiment(ticker)
        signals["sentiment"] = sentiment_data["score"]
        signals["headlines"] = "; ".join(sentiment_data.get("headlines", [])[:3])

        # 3. Get politician data
        pol_data = get_politician_signals(ticker, self.config)
        signals["politician_score"] = pol_data["composite_score"]
        signals["politician_details"] = json.dumps(pol_data.get("trades", [])[:3])

        # Populate macro context
        signals["macro_context"] = calculate_macro_context()

        # 4. Tier 1 screening
        if self.tier1_calls >= self.max_tier1:
            logger.warning("Tier 1 daily call limit reached")
            return

        t1_score = tier1_screen(ticker, signals, self.config)
        self.tier1_calls += 1
        logger.info(f"[{ticker}] Tier 1 score: {t1_score:.1f}/10")

        # Save signals to DB
        self.db.execute(
            """INSERT OR REPLACE INTO signals (ticker, rsi, macd, vwap, rvol, sentiment, politician_score, composite, timestamp) VALUES (?,?,?,?,?,?,?,?,?)""",
            (ticker, signals["rsi"], signals["macd"], signals["vwap"], signals["rvol"],
             signals["sentiment"], signals["politician_score"], t1_score, datetime.now().isoformat())
        )
        self.db.commit()

        # 5. Check if worth a Tier 2 call
        pol_override = pol_data["composite_score"] >= 0.8
        if t1_score < self.tier1_threshold and not pol_override:
            logger.info(f"[{ticker}] Below threshold ({t1_score:.1f} < {self.tier1_threshold}), skipping Tier 2")
            return

        if self.tier2_calls >= self.max_tier2:
            logger.warning("Tier 2 daily call limit reached")
            return

        # 6. Get portfolio state
        acct = self.executor.get_account()
        positions = self.executor.get_positions()
        portfolio = {
            "cash": float(acct.get("cash", 100000)),
            "current_position": next((p for p in positions if p.get("symbol") == ticker), "None"),
            "daily_pnl": float(acct.get("equity", 0)) - float(acct.get("last_equity", acct.get("equity", 0))),
            "open_positions": len(positions),
            "max_positions": self.max_positions,
        }

        # 7. Tier 2 premium decision
        if pol_override:
            logger.info(f"[{ticker}] 🏛️ Politician override! Strong congressional signal ({pol_data['composite_score']:.2f})")

        decision = tier2_decide(ticker, signals, portfolio, self.config)
        self.tier2_calls += 1

        logger.info(f"[{ticker}] 🧠 LLM Decision: {decision['action']} (confidence: {decision.get('confidence', 0):.2f})")
        logger.info(f"[{ticker}] 💬 Reasoning: {decision.get('reasoning', 'N/A')}")

        # Save decision to DB
        self.db.execute("""INSERT INTO decisions (ticker, action, confidence, reasoning, signals_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker, decision["action"], decision.get("confidence", 0),
             decision.get("reasoning", ""), json.dumps(signals), datetime.now().isoformat()))
        self.db.commit()

        # 8. Execute trade
        if decision["action"] == "BUY" and len(positions) < self.max_positions:
            equity = float(acct.get("equity", 100000))
            max_pct = self.config.get("max_portfolio_pct_per_trade", 20) / 100
            position_pct = min(decision.get("position_pct", 0.1), max_pct)
            cash_to_use = equity * position_pct
            price = decision.get("entry", signals["price"])
            qty = max(1, int(cash_to_use / price)) if price > 0 else 0

            if qty > 0:
                sl = decision.get("stop_loss", price * (1 - self.config.get("stop_loss_pct", 0.75) / 100))
                tp = decision.get("take_profit", price * (1 + self.config.get("take_profit_pct", 1.5) / 100))

                order_id = self.executor.place_bracket_order(
                    ticker=ticker, qty=qty, side="buy",
                    entry_price=price, stop_loss=sl, take_profit=tp
                )
                if order_id:
                    self.daily_trades += 1
                    self.db.execute("""INSERT OR REPLACE INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (order_id, ticker, "BUY", qty, price, sl, tp,
                         decision.get("confidence", 0), decision.get("reasoning", ""),
                         datetime.now().isoformat(), "filled"))
                    self.db.commit()
                    logger.info(f"[{ticker}] ✅ ORDER PLACED: BUY {qty} shares @ ${price:.2f}, SL=${sl:.2f}, TP=${tp:.2f}")

                    # Send trade notification
                    notify_trade(ticker, "BUY", qty, price, decision.get("reasoning", ""), self.config)

        elif decision["action"] == "SELL":
            current = next((p for p in positions if p.get("symbol") == ticker), None)
            if current:
                self.executor.close_position(ticker)
                logger.info(f"[{ticker}] ✅ POSITION CLOSED")
                notify_trade(ticker, "SELL", int(current.get("qty", 0)),
                           float(current.get("current_price", 0)),
                           decision.get("reasoning", ""), self.config)

    def snapshot_portfolio(self):
        """Save portfolio snapshot for dashboard charting."""
        acct = self.executor.get_account()
        positions = self.executor.get_positions()
        self.db.execute("""INSERT INTO portfolio_snapshots (equity, cash, daily_pnl, open_positions, timestamp)
            VALUES (?, ?, ?, ?, ?)""",
            (float(acct.get("equity", 0)), float(acct.get("cash", 0)),
             float(acct.get("equity", 0)) - float(acct.get("last_equity", acct.get("equity", 0))),
             len(positions), datetime.now().isoformat()))
        self.db.commit()

    def eod_close(self):
        """End-of-day: close all positions and cancel orders."""
        logger.info("=" * 50)
        logger.info("🏁 END OF DAY — Closing all positions")
        logger.info("=" * 50)
        self.executor.cancel_all_orders()
        self.executor.close_all_positions()
        self.eod_close_done = True

    def send_daily_summary(self):
        """Send daily P&L summary notification."""
        acct = self.executor.get_account()
        equity = float(acct.get("equity", 100000))
        pnl = self.executor.get_daily_pnl()

        # Calculate win rate from today's trades
        try:
            rows = self.db.execute(
                "SELECT COUNT(*), SUM(CASE WHEN take_profit > entry_price THEN 1 ELSE 0 END) FROM trades WHERE date(timestamp) = date('now')"
            ).fetchone()
            total = rows[0] or 0
            wins = rows[1] or 0
            win_rate = wins / total if total > 0 else 0.0
        except Exception:
            win_rate = 0.0

        notify_daily_summary(equity, pnl, self.daily_trades, win_rate, self.config)
        self.daily_summary_sent = True
        logger.info(f"📊 Daily Summary: Equity=${equity:,.2f}, P&L={'+'if pnl>=0 else ''}${pnl:,.2f}, Trades={self.daily_trades}")

    def reset_daily_counters(self):
        """Reset all daily counters for a new trading day."""
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.tier1_calls = 0
        self.tier2_calls = 0
        self.circuit_breaker_tripped = False
        self.premarket_scan_done = False
        self.eod_close_done = False
        self.daily_summary_sent = False
        logger.info("🔄 Daily counters reset for new trading day")

    def run(self):
        """Main trading loop — runs continuously with time-aware scheduling."""
        logger.info("=" * 60)
        logger.info("🤖 APEX AI TRADING BOT STARTING")
        logger.info(f"   Mode: {self.config.get('broker', {}).get('mode', 'paper').upper()}")
        logger.info(f"   Watchlist: {', '.join(self.watchlist)}")
        logger.info(f"   Tier 1 LLM: {self.config.get('llm', {}).get('tier1_provider', 'gemini')}/{self.config.get('llm', {}).get('tier1_model', 'gemini-2.0-flash')}")
        logger.info(f"   Tier 2 LLM: {self.config.get('llm', {}).get('tier2_provider', 'openai')}/{self.config.get('llm', {}).get('tier2_model', 'gpt-4o')}")
        logger.info(f"   Pre-market scan: {self.premarket_scan_time} EST")
        logger.info(f"   Trading hours: {self.trading_start} - {self.trading_end} EST")
        logger.info("=" * 60)

        cycle = 0
        last_date = None

        while self.running:
            try:
                now = self._now_est()
                today = now.date()

                # ── New day reset ──
                if last_date != today:
                    self.reset_daily_counters()
                    last_date = today

                # ── Weekend / holiday check ──
                if not self._is_trading_day():
                    logger.info(f"📅 Weekend detected ({now.strftime('%A')}). Sleeping until Monday...")
                    # Sleep until next Monday 7:30 AM EST
                    days_until_monday = (7 - now.weekday()) % 7
                    if days_until_monday == 0:
                        days_until_monday = 7
                    next_monday = now.replace(hour=7, minute=30, second=0) + timedelta(days=days_until_monday)
                    sleep_seconds = (next_monday - now).total_seconds()
                    logger.info(f"   Next wake-up: {next_monday.strftime('%A %I:%M %p EST')}")
                    self._interruptible_sleep(min(sleep_seconds, 3600))  # Check every hour
                    continue

                premarket_time = self._time_str_to_today(self.premarket_scan_time)
                trading_start = self._time_str_to_today(self.trading_start)
                trading_end = self._time_str_to_today(self.trading_end)
                summary_time = now.replace(hour=16, minute=0, second=0)

                # ── PHASE 1: Before pre-market (before 8:00 AM) ──
                if now < premarket_time:
                    wait_secs = (premarket_time - now).total_seconds()
                    logger.info(f"⏰ Waiting for pre-market scan at {self.premarket_scan_time} EST ({wait_secs/60:.0f} min)...")
                    self._interruptible_sleep(min(wait_secs, 300))
                    continue

                # ── PHASE 2: Pre-market scan (8:00 AM - 9:30 AM) ──
                if now >= premarket_time and now < trading_start:
                    if not self.premarket_scan_done:
                        self.run_premarket_scan()
                    else:
                        wait_secs = (trading_start - now).total_seconds()
                        logger.info(f"⏰ Pre-market scan done. Trading starts at {self.trading_start} EST ({wait_secs/60:.0f} min)...")
                        self._interruptible_sleep(min(wait_secs, 60))
                    continue

                # ── PHASE 3: Active trading (9:30 AM - 3:55 PM) ──
                if now >= trading_start and now < trading_end:
                    cycle += 1
                    logger.info(f"\n--- Cycle {cycle} | {now.strftime('%I:%M:%S %p')} | Trades: {self.daily_trades} | T1: {self.tier1_calls} | T2: {self.tier2_calls} ---")

                    # Check circuit breaker
                    if self.check_circuit_breaker():
                        logger.critical("Circuit breaker active — waiting for EOD")
                        self._interruptible_sleep(300)
                        continue

                    # Run cycle for each ticker
                    for ticker in self.watchlist:
                        if not self.running:
                            break
                        try:
                            self.run_cycle(ticker)
                        except Exception as e:
                            logger.error(f"[{ticker}] Cycle error: {e}")

                    # Snapshot portfolio
                    self.snapshot_portfolio()

                    # Wait for next cycle
                    logger.info(f"Sleeping {self.interval}s until next cycle...")
                    self._interruptible_sleep(self.interval)
                    continue

                # ── PHASE 4: End of day close (3:55 PM) ──
                if now >= trading_end and not self.eod_close_done:
                    self.eod_close()
                    continue

                # ── PHASE 5: Daily summary (4:00 PM) ──
                if now >= summary_time and not self.daily_summary_sent:
                    self.send_daily_summary()
                    continue

                # ── PHASE 6: After hours — sleep until next day ──
                if now >= summary_time and self.daily_summary_sent:
                    tomorrow_premarket = (now + timedelta(days=1)).replace(
                        hour=int(self.premarket_scan_time.split(":")[0]),
                        minute=int(self.premarket_scan_time.split(":")[1]),
                        second=0
                    )
                    sleep_secs = (tomorrow_premarket - now).total_seconds()
                    logger.info(f"🌙 Trading day complete. Sleeping until {tomorrow_premarket.strftime('%A %I:%M %p EST')}...")
                    self._interruptible_sleep(min(sleep_secs, 3600))  # Check every hour
                    continue

            except KeyboardInterrupt:
                logger.info("🛑 Bot stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(30)

        # ── Shutdown cleanup ──
        logger.info("Closing all positions (shutdown)...")
        self.executor.close_all_positions()
        if not self.daily_summary_sent:
            self.send_daily_summary()
        logger.info("🏁 Trading bot shut down cleanly")

    def _interruptible_sleep(self, seconds: float):
        """Sleep that can be interrupted by shutdown signal."""
        end = time.time() + seconds
        while time.time() < end and self.running:
            time.sleep(min(1.0, end - time.time()))


def main():
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
