"""
Master Trading Loop - Fully automated day trading bot.
Runs the complete cycle: premarket scan → signal collection → LLM decisions → order execution → EOD close.
Zero human intervention required once started.
"""
import os
import sys
import time
import json
import yaml
import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from automation.indicators import calculate_indicators
from engine.llm_brain import tier1_screen, tier2_decide
from sentiment.finbert_client import get_sentiment
from politician.copy_mode import get_politician_signals, get_all_recent_trades
from execution.order_manager import AlpacaExecutor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("trading_bot.log")]
)
logger = logging.getLogger("trading_loop")


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


class TradingBot:
    def __init__(self):
        self.config = load_config()
        db_path = self.config.get("database", {}).get("path", "trading.db")
        self.db = init_db(db_path)
        self.executor = AlpacaExecutor(self.config)
        self.watchlist = self.config.get("watchlist", [])
        self.running = True
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.tier1_calls = 0
        self.tier2_calls = 0
        self.circuit_breaker_tripped = False

        # Limits from config
        self.max_positions = self.config.get("max_concurrent_positions", 3)
        self.max_tier1 = self.config.get("llm", {}).get("max_tier1_calls_per_day", 2000)
        self.max_tier2 = self.config.get("llm", {}).get("max_tier2_calls_per_day", 300)
        self.tier1_threshold = self.config.get("tier1_opportunity_threshold", 7.0)
        self.interval = self.config.get("llm", {}).get("decision_interval_seconds", 60)

    def check_circuit_breaker(self) -> bool:
        """Check if daily loss limit hit."""
        pnl = self.executor.get_daily_pnl()
        equity = self.executor.get_portfolio_value()
        if equity > 0 and pnl < 0 and abs(pnl / equity) > 0.02:  # 2% daily loss limit
            logger.critical("⚠️ CIRCUIT BREAKER: Daily loss limit (-2%) reached! Stopping trading.")
            self.circuit_breaker_tripped = True
            self.executor.close_all_positions()
            return True
        return False

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

        # 4. Tier 1 screening
        if self.tier1_calls >= self.max_tier1:
            logger.warning("Tier 1 daily call limit reached")
            return

        t1_score = tier1_screen(ticker, signals, self.config)
        self.tier1_calls += 1
        logger.info(f"[{ticker}] Tier 1 score: {t1_score:.1f}/10")

        # Save signals to DB
        self.db.execute("""INSERT OR REPLACE INTO signals VALUES (?,?,?,?,?,?,?,?,?)""",
            (ticker, signals["rsi"], signals["macd"], signals["vwap"], signals["rvol"],
             signals["sentiment"], signals["politician_score"], t1_score, datetime.now().isoformat()))
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

        elif decision["action"] == "SELL":
            current = next((p for p in positions if p.get("symbol") == ticker), None)
            if current:
                self.executor.close_position(ticker)
                logger.info(f"[{ticker}] ✅ POSITION CLOSED")

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

    def run(self):
        """Main trading loop - runs all day."""
        logger.info("=" * 60)
        logger.info("🤖 AI TRADING BOT STARTING")
        logger.info(f"   Mode: {self.config.get('broker', {}).get('mode', 'paper').upper()}")
        logger.info(f"   Watchlist: {', '.join(self.watchlist)}")
        logger.info(f"   Tier 1 LLM: {self.config.get('llm', {}).get('tier1_provider', 'gemini')}/{self.config.get('llm', {}).get('tier1_model', 'gemini-2.0-flash')}")
        logger.info(f"   Tier 2 LLM: {self.config.get('llm', {}).get('tier2_provider', 'openai')}/{self.config.get('llm', {}).get('tier2_model', 'gpt-4o')}")
        logger.info("=" * 60)

        cycle = 0
        while self.running:
            try:
                cycle += 1
                now = datetime.now()
                logger.info(f"\n--- Cycle {cycle} | {now.strftime('%I:%M:%S %p')} | Trades today: {self.daily_trades} | T1 calls: {self.tier1_calls} | T2 calls: {self.tier2_calls} ---")

                # Check circuit breaker
                if self.check_circuit_breaker():
                    logger.critical("Circuit breaker active — waiting for next trading day")
                    time.sleep(300)
                    continue

                # Run cycle for each ticker
                for ticker in self.watchlist:
                    try:
                        self.run_cycle(ticker)
                    except Exception as e:
                        logger.error(f"[{ticker}] Cycle error: {e}")

                # Snapshot portfolio
                self.snapshot_portfolio()

                # Wait for next cycle
                logger.info(f"Sleeping {self.interval}s until next cycle...")
                time.sleep(self.interval)

            except KeyboardInterrupt:
                logger.info("🛑 Bot stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(30)

        # EOD cleanup
        logger.info("Closing all positions (EOD)...")
        self.executor.close_all_positions()
        logger.info("🏁 Trading bot shut down cleanly")


def main():
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
