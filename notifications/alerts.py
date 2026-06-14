"""
Notification system — Telegram and Email alerts for trade events.
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger("notifications")


def send_telegram(message: str) -> bool:
    """Send a Telegram notification."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


def send_email(subject: str, body: str) -> bool:
    """Send an email notification."""
    email_addr = os.getenv("EMAIL_ADDRESS", "")
    email_pass = os.getenv("EMAIL_APP_PASSWORD", "")
    smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    if not email_addr or not email_pass:
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = email_addr
        msg["To"] = email_addr
        msg["Subject"] = f"[APEX AI Bot] {subject}"
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(email_addr, email_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False


def notify_trade(ticker: str, action: str, qty: int, price: float, reasoning: str, config: dict = None):
    """Notify about a trade execution."""
    msg = f"🤖 <b>APEX Trade Alert</b>\n\n<b>{action}</b> {qty}x {ticker} @ ${price:.2f}\n\n💬 {reasoning}"

    if config and config.get("notifications", {}).get("telegram_enabled"):
        send_telegram(msg)
    if config and config.get("notifications", {}).get("email_enabled"):
        send_email(f"{action} {ticker}", msg.replace("\n", "<br>"))


def notify_circuit_breaker(daily_pnl: float, config: dict = None):
    """Alert when circuit breaker is tripped."""
    msg = f"🚨 <b>CIRCUIT BREAKER TRIPPED</b>\n\nDaily P&L: ${daily_pnl:.2f}\nTrading halted until next session."
    if config and config.get("notifications", {}).get("telegram_enabled"):
        send_telegram(msg)
    if config and config.get("notifications", {}).get("email_enabled"):
        send_email("⚠️ Circuit Breaker Tripped", msg.replace("\n", "<br>"))


def notify_daily_summary(equity: float, pnl: float, trades: int, win_rate: float, config: dict = None):
    """Send end-of-day summary."""
    msg = (f"📊 <b>Daily Summary</b>\n\n"
           f"Portfolio: ${equity:,.2f}\n"
           f"Today's P&L: {'+'if pnl>=0 else ''}${pnl:,.2f}\n"
           f"Trades: {trades}\n"
           f"Win Rate: {win_rate:.0%}")
    if config and config.get("notifications", {}).get("telegram_enabled"):
        send_telegram(msg)
    if config and config.get("notifications", {}).get("email_enabled"):
        send_email(f"Daily P&L: {'+'if pnl>=0 else ''}${pnl:,.2f}", msg.replace("\n", "<br>"))
