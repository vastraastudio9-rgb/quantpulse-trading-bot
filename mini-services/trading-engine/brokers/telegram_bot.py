"""
Telegram Bot Alert Module

Sends trading signals, alerts, and notifications to a Telegram chat.

Setup:
1. Create a bot via @BotFather on Telegram → get bot token
2. Get your chat ID: send a message to your bot, then visit:
   https://api.telegram.org/bot<TOKEN>/getUpdates
   Look for "chat":{"id":XXXXXXX in the response
3. Set environment variables:
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID
4. OR pass credentials directly to send_message()

Usage:
    from brokers.telegram_bot import send_signal_alert, send_message
    send_message("Hello from QuantPulse!")
    send_signal_alert(signal_dict)
"""
import os
import logging
import json
from typing import Dict, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Try to import requests (for Telegram REST API)
try:
    import urllib.request
    import urllib.parse
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Read credentials
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def is_configured() -> bool:
    """Check if Telegram credentials are configured."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def _api_call(method: str, payload: Dict) -> Dict:
    """Call Telegram Bot API endpoint."""
    if not is_configured():
        return {"ok": False, "error": "Telegram not configured"}
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Telegram API call failed ({method}): {e}")
        return {"ok": False, "error": str(e)}


def send_message(
    text: str,
    parse_mode: str = "Markdown",
    chat_id: Optional[str] = None,
    disable_notification: bool = False,
) -> Dict:
    """Send a text message to Telegram chat.
    
    Args:
        text: message text (Markdown supported)
        parse_mode: 'Markdown' or 'HTML'
        chat_id: override default chat ID
        disable_notification: send silently (no sound)
    
    Returns Telegram API response.
    """
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid:
        return {"ok": False, "error": "Chat ID not set"}
    payload = {
        "chat_id": cid,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
    }
    return _api_call("sendMessage", payload)


def send_signal_alert(signal: Dict, chat_id: Optional[str] = None) -> Dict:
    """Send a formatted signal alert to Telegram.
    
    Args:
        signal: trading signal dict (from strategies.generate_signal)
        chat_id: override default chat ID
    
    Returns Telegram API response.
    """
    # Determine direction emoji
    is_buy = "BUY" in [l.get("action", "") for l in signal.get("legs", [])]
    is_sell = "SELL" in [l.get("action", "") for l in signal.get("legs", [])]
    if is_buy and not is_sell:
        direction_emoji = "🟢 BUY"
    elif is_sell and not is_buy:
        direction_emoji = "🔴 SELL"
    else:
        direction_emoji = "🟡 NEUTRAL"
    
    # Format legs
    legs_text = ""
    for i, leg in enumerate(signal.get("legs", []), 1):
        action_icon = "🟢" if leg.get("action") == "BUY" else "🔴"
        expiry_str = f" ({leg.get('expiry', '')})" if leg.get("expiry") else ""
        legs_text += f"\n  {i}. {action_icon} {leg['action']} {leg.get('strike', '')} {leg.get('type', '')}{expiry_str} @ ₹{leg.get('premium', 0)}"
    
    # Format breakevens if present
    be_text = ""
    if signal.get("breakeven_upper") and signal.get("breakeven_lower"):
        be_text = f"\n📍 *Breakevens:* {signal['breakeven_lower']} / {signal['breakeven_upper']}"
    
    # Format max profit/loss
    pnl_text = ""
    if signal.get("max_profit") is not None:
        mp = signal["max_profit"]
        mp_str = f"₹{mp}" if isinstance(mp, (int, float)) else str(mp)
        pnl_text += f"\n📈 *Max Profit:* {mp_str}"
    if signal.get("max_loss") is not None:
        ml = signal["max_loss"]
        ml_str = f"₹{ml}" if isinstance(ml, (int, float)) else str(ml)
        pnl_text += f"\n📉 *Max Loss:* {ml_str}"
    
    # Confidence bar
    conf = signal.get("confidence", 0)
    conf_bar = "█" * int(conf / 10) + "░" * (10 - int(conf / 10))
    
    text = f"""{direction_emoji} *SIGNAL ALERT*

🎯 *Strategy:* {signal.get('strategy_name', '')}
📊 *Instrument:* {signal.get('symbol', '')} ({signal.get('exchange', '')})
💰 *Spot:* ₹{signal.get('spot_price', 0):.2f}
🎚 *Direction:* {signal.get('direction', '')}

⚡ *Confidence:* {conf}% `[{conf_bar}]`

*Legs:*{legs_text}

🎯 *Entry:* ₹{signal.get('entry_price', 0)}
🛑 *Stop Loss:* ₹{signal.get('stop_loss', 0)}
✅ *Target:* ₹{signal.get('target', 0)}{pnl_text}{be_text}

📝 *Rationale:*
_{signal.get('rationale', '')}_

⏰ {datetime.fromisoformat(signal.get('timestamp', datetime.now(timezone.utc).isoformat())).strftime('%Y-%m-%d %H:%M:%S UTC')}
🤖 _QuantPulse Trading Bot_"""
    
    return send_message(text, chat_id=chat_id)


def send_pnl_alert(pnl_data: Dict, chat_id: Optional[str] = None) -> Dict:
    """Send a daily P&L summary alert."""
    today_pnl = pnl_data.get("today_pnl", 0)
    pnl_pct = pnl_data.get("today_pnl_pct", 0)
    is_profit = today_pnl >= 0
    emoji = "📈" if is_profit else "📉"
    
    text = f"""{emoji} *DAILY P&L SUMMARY*

💰 *Today's P&L:* ₹{today_pnl:,.2f} ({pnl_pct:+.2f}%)
📊 *Open Positions:* {pnl_data.get('open_positions', 0)}
🎯 *Win Rate (30d):* {pnl_data.get('win_rate_30d', 0):.1f}%
🔄 *Total Trades:* {pnl_data.get('total_trades_30d', 0)}

💵 *Capital Available:* ₹{pnl_data.get('capital_available', 0):,.2f}
🔒 *Capital Used:* ₹{pnl_data.get('capital_used', 0):,.2f}

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
🤖 _QuantPulse Trading Bot_"""
    
    return send_message(text, chat_id=chat_id)


def send_alert(
    title: str,
    message: str,
    alert_type: str = "INFO",
    chat_id: Optional[str] = None,
) -> Dict:
    """Send a generic alert message.
    
    Args:
        title: alert title
        message: alert body
        alert_type: INFO / WARNING / ERROR / SUCCESS
    """
    emoji_map = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "🚨", "SUCCESS": "✅"}
    emoji = emoji_map.get(alert_type, "ℹ️")
    text = f"""{emoji} *{alert_type}: {title}*

{message}

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
🤖 _QuantPulse Trading Bot_"""
    return send_message(text, chat_id=chat_id)


def test_connection(token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict:
    """Test Telegram bot connection by sending a test message.
    
    Args:
        token: override bot token
        chat_id: override chat ID
    
    Returns dict with status.
    """
    old_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    old_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    # Temporarily override
    if token:
        os.environ["TELEGRAM_BOT_TOKEN"] = token
    if chat_id:
        os.environ["TELEGRAM_CHAT_ID"] = chat_id
    
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    if not is_configured():
        # Restore
        os.environ["TELEGRAM_BOT_TOKEN"] = old_token
        os.environ["TELEGRAM_CHAT_ID"] = old_chat_id
        TELEGRAM_BOT_TOKEN = old_token
        TELEGRAM_CHAT_ID = old_chat_id
        return {"ok": False, "error": "Bot token or chat ID missing"}
    
    result = send_alert(
        title="QuantPulse Connection Test",
        message="✅ Telegram alerts are now active. You will receive signal alerts here.",
        alert_type="SUCCESS",
    )
    
    # Restore env
    os.environ["TELEGRAM_BOT_TOKEN"] = old_token
    os.environ["TELEGRAM_CHAT_ID"] = old_chat_id
    TELEGRAM_BOT_TOKEN = old_token
    TELEGRAM_CHAT_ID = old_chat_id
    
    if result.get("ok"):
        return {
            "ok": True,
            "message": "Test message sent successfully. Check your Telegram chat.",
            "chat_id": TELEGRAM_CHAT_ID or chat_id,
        }
    else:
        return {
            "ok": False,
            "error": result.get("description", result.get("error", "Unknown error")),
        }
