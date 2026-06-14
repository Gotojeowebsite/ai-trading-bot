"""
Tiered LLM Decision Engine
- Tier 1 (Gemini Flash): fast screening, runs every cycle
- Tier 2 (GPT-4o / Claude): premium decision, only on high-opportunity signals
- Fallback: if Tier 2 fails, uses Gemini 1.5 Pro
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger("llm_brain")


def _call_gemini(prompt: str, model: str = "gemini-2.0-flash", max_tokens: int = 200) -> Optional[str]:
    """Call Google Gemini API."""
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        logger.warning("Gemini API key not configured, returning None")
        return None
    genai.configure(api_key=api_key)
    try:
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content(prompt, generation_config={"max_output_tokens": max_tokens, "temperature": 0.1})
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return None


def _call_openai(prompt: str, system_prompt: str = "", model: str = "gpt-4o", max_tokens: int = 800) -> Optional[str]:
    """Call OpenAI API."""
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        logger.warning("OpenAI API key not configured, returning None")
        return None
    try:
        client = OpenAI(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, temperature=0.2)
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return None


def _call_anthropic(prompt: str, system_prompt: str = "", model: str = "claude-3-5-sonnet-20241022", max_tokens: int = 800) -> Optional[str]:
    """Call Anthropic Claude API."""
    from anthropic import Anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        logger.warning("Anthropic API key not configured, returning None")
        return None
    try:
        client = Anthropic(api_key=api_key)
        kwargs = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
        if system_prompt:
            kwargs["system"] = system_prompt
        response = client.messages.create(**kwargs)
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return None


def _call_llm(provider: str, prompt: str, system_prompt: str = "", model: str = "", max_tokens: int = 800) -> Optional[str]:
    """Route to the correct LLM provider."""
    if provider == "gemini":
        return _call_gemini(prompt, model=model or "gemini-2.0-flash", max_tokens=max_tokens)
    elif provider == "openai":
        return _call_openai(prompt, system_prompt=system_prompt, model=model or "gpt-4o", max_tokens=max_tokens)
    elif provider == "anthropic":
        return _call_anthropic(prompt, system_prompt=system_prompt, model=model or "claude-3-5-sonnet-20241022", max_tokens=max_tokens)
    else:
        logger.error(f"Unknown LLM provider: {provider}")
        return None


# ── Bot personality system prompt ──
SYSTEM_PROMPT = """You are APEX, an elite AI day trader specializing in momentum stocks.
You make precise, data-driven buy/sell/hold decisions based on technical signals, news sentiment, and congressional trading intelligence.
You are disciplined, unemotional, and always protect capital first.
Rules:
- Day trading only: all positions close before market end
- Risk/reward minimum 1:2
- Never risk more than 1% of portfolio on a single trade
- If signals conflict, default to HOLD
- Always provide clear reasoning for every decision"""


def tier1_screen(ticker: str, signals: dict, config: dict) -> float:
    """
    Tier 1: Fast cheap screening call.
    Returns opportunity score 0-10.
    """
    provider = config.get("llm", {}).get("tier1_provider", "gemini")
    model = config.get("llm", {}).get("tier1_model", "gemini-2.0-flash")

    prompt = f"""Rate this stock's day-trading opportunity from 0 to 10 (10 = strongest).
Return ONLY a single number, nothing else.

Ticker: {ticker}
RSI: {signals.get('rsi', 'N/A')}
MACD: {signals.get('macd', 'N/A')}
VWAP position: {'above' if signals.get('price', 0) > signals.get('vwap', 0) else 'below'}
RVOL: {signals.get('rvol', 'N/A')}x
News sentiment: {signals.get('sentiment', 'N/A')}
Politician signal: {signals.get('politician_score', 'N/A')}"""

    result = _call_llm(provider, prompt, model=model, max_tokens=10)
    if result:
        try:
            # Extract number from response
            import re
            nums = re.findall(r'[\d.]+', result)
            if nums:
                score = float(nums[0])
                return min(max(score, 0.0), 10.0)
        except (ValueError, IndexError):
            pass
    return 0.0


def build_market_briefing(ticker: str, signals: dict, portfolio: dict) -> str:
    """Build the full structured market briefing prompt for Tier 2."""
    import datetime
    now = datetime.datetime.now().strftime("%I:%M %p EST, %B %d %Y")

    price = signals.get("price", 0)
    briefing = f"""MARKET BRIEFING — {now}

STOCK: {ticker}
Current Price: ${price:.2f}

TECHNICAL SIGNALS:
  • VWAP: ${signals.get('vwap', 0):.2f} → Price is {'ABOVE' if price > signals.get('vwap', 0) else 'BELOW'} VWAP ({'bullish' if price > signals.get('vwap', 0) else 'bearish'})
  • MACD (5-min): {signals.get('macd', 0):.4f} ({'bullish' if signals.get('macd', 0) > 0 else 'bearish'})
  • RSI(14): {signals.get('rsi', 50):.1f} — {'overbought' if signals.get('rsi', 50) > 70 else 'oversold' if signals.get('rsi', 50) < 30 else 'neutral'}
  • RVOL: {signals.get('rvol', 1.0):.1f}x average volume
  • Bollinger: Price near {'upper' if signals.get('bb_position', '') == 'upper' else 'lower' if signals.get('bb_position', '') == 'lower' else 'middle'} band
  • EMA trend: {signals.get('ema_trend', 'neutral')}

NEWS SENTIMENT (last 4 hours):
  • Score: {signals.get('sentiment', 0):.2f} / 1.0 ({'BULLISH' if signals.get('sentiment', 0) > 0.3 else 'BEARISH' if signals.get('sentiment', 0) < -0.3 else 'NEUTRAL'})
  • Headlines: {signals.get('headlines', 'No recent headlines')}

POLITICIAN TRADE INTELLIGENCE:
  • Composite score: {signals.get('politician_score', 0):.2f} ({'BULLISH' if signals.get('politician_score', 0) > 0.3 else 'BEARISH' if signals.get('politician_score', 0) < -0.3 else 'NEUTRAL'})
  • Recent trades: {signals.get('politician_details', 'No recent congressional trades for this ticker')}

PORTFOLIO STATE:
  • Cash available: ${portfolio.get('cash', 0):.2f}
  • Current {ticker} position: {portfolio.get('current_position', 'None')}
  • Today P&L: ${portfolio.get('daily_pnl', 0):.2f}
  • Open positions: {portfolio.get('open_positions', 0)}/{portfolio.get('max_positions', 3)}

TASK:
Analyze ALL data above. Return ONLY valid JSON (no markdown, no backticks):
{{"action": "BUY|SELL|HOLD", "confidence": 0.0-1.0, "entry": price, "stop_loss": price, "take_profit": price, "position_pct": 0.0-0.5, "reasoning": "2-3 sentence explanation"}}"""
    return briefing


def tier2_decide(ticker: str, signals: dict, portfolio: dict, config: dict) -> dict:
    """
    Tier 2: Premium decision call with full market briefing.
    Returns structured trade decision.
    """
    provider = config.get("llm", {}).get("tier2_provider", "openai")
    model = config.get("llm", {}).get("tier2_model", "gpt-4o")
    fallback_provider = config.get("llm", {}).get("fallback_provider", "gemini")
    fallback_model = config.get("llm", {}).get("fallback_model", "gemini-1.5-pro")

    briefing = build_market_briefing(ticker, signals, portfolio)

    # Try Tier 2
    result = _call_llm(provider, briefing, system_prompt=SYSTEM_PROMPT, model=model, max_tokens=500)

    # Fallback if Tier 2 fails
    if not result:
        logger.warning(f"Tier 2 ({provider}/{model}) failed, falling back to {fallback_provider}/{fallback_model}")
        result = _call_llm(fallback_provider, briefing, system_prompt=SYSTEM_PROMPT, model=fallback_model, max_tokens=500)

    if result:
        try:
            # Clean JSON from potential markdown wrapping
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0] if "```" in cleaned else cleaned
                cleaned = cleaned.strip()
            decision = json.loads(cleaned)

            # Validate required fields
            action = decision.get("action", "HOLD").upper()
            if action not in ("BUY", "SELL", "HOLD"):
                action = "HOLD"
            decision["action"] = action

            # Validate stop-loss / take-profit boundaries
            entry = float(decision.get("entry", signals.get("price", 0)))
            sl = float(decision.get("stop_loss", 0))
            tp = float(decision.get("take_profit", 0))
            if action == "BUY" and (sl >= entry or tp <= entry):
                decision["action"] = "HOLD"
                decision["reasoning"] = f"Overruled: invalid stop/tp for BUY (entry={entry}, sl={sl}, tp={tp})"

            if not decision.get("reasoning"):
                decision["action"] = "HOLD"
                decision["reasoning"] = "Overruled: no reasoning provided"

            return decision
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM JSON: {result[:200]}")

    return {
        "action": "HOLD",
        "confidence": 0.0,
        "entry": signals.get("price", 0),
        "stop_loss": 0,
        "take_profit": 0,
        "position_pct": 0,
        "reasoning": "All LLM providers unavailable — defaulting to HOLD for safety"
    }
