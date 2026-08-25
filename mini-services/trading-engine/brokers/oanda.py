"""
OANDA REST API Integration Module

OANDA — global forex/CFD broker with REST API.
Supports: 70+ forex pairs, gold (XAU), silver (XAG), indices, commodities.

Setup:
1. Create account at https://www.oanda.com/
2. Get API key from https://developer.oanda.com/
3. Set env vars: OANDA_API_KEY, OANDA_ACCOUNT_ID
4. Choose environment: OANDA_ENVIRONMENT (practice/live)
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    import requests
    OANDA_AVAILABLE = True
except ImportError:
    OANDA_AVAILABLE = False

OANDA_API_KEY = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")
OANDA_ENVIRONMENT = os.environ.get("OANDA_ENVIRONMENT", "practice")  # practice or live

OANDA_BASE_URL = (
    "https://api-fxtrade.oanda.com" if OANDA_ENVIRONMENT == "live"
    else "https://api-fxpractice.oanda.com"
)


def is_configured() -> bool:
    return bool(OANDA_API_KEY and OANDA_ACCOUNT_ID and OANDA_AVAILABLE)


def _get_headers() -> Dict:
    return {
        "Authorization": f"Bearer {OANDA_API_KEY}",
        "Content-Type": "application/json",
        "Accept-Datetime-Format": "RFC3339",
    }


def test_connection() -> Dict:
    if not OANDA_AVAILABLE:
        return {"connected": False, "message": "requests not installed"}
    if not (OANDA_API_KEY and OANDA_ACCOUNT_ID):
        return {"connected": False, "message": "API key + account ID required from https://developer.oanda.com/"}
    try:
        response = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/summary",
            headers=_get_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json().get("account", {})
            return {
                "connected": True,
                "message": f"Connected: {data.get('alias', OANDA_ACCOUNT_ID)}, balance {data.get('currency')} {data.get('balance')}",
                "account": data.get("alias"),
                "balance": float(data.get("balance", 0)),
                "currency": data.get("currency"),
                "broker": "OANDA",
                "environment": OANDA_ENVIRONMENT,
            }
        return {"connected": False, "message": f"HTTP {response.status_code}: {response.text[:100]}"}
    except Exception as e:
        return {"connected": False, "message": f"Connection error: {str(e)}"}


def fetch_historical(instrument: str, granularity: str = "D",
                     from_time: str = "", to_time: str = "",
                     count: int = 500) -> List[Dict]:
    if not is_configured():
        return []
    try:
        params = {"price": "M", "granularity": granularity}
        if count and not from_time:
            params["count"] = count
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time

        response = requests.get(
            f"{OANDA_BASE_URL}/v3/instruments/{instrument}/candles",
            headers=_get_headers(),
            params=params,
            timeout=10,
        )
        if response.status_code == 200:
            candles = response.json().get("candles", [])
            result = []
            for c in candles:
                if c.get("complete"):
                    m = c.get("mid", {})
                    result.append({
                        "timestamp": c.get("time", ""),
                        "open": float(m.get("o", 0)),
                        "high": float(m.get("h", 0)),
                        "low": float(m.get("l", 0)),
                        "close": float(m.get("c", 0)),
                        "volume": c.get("volume", 0),
                    })
            return result
    except Exception as e:
        logger.error(f"OANDA historical failed: {e}")
    return []


def get_quote(instrument: str) -> Optional[Dict]:
    if not is_configured():
        return None
    try:
        response = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/pricing",
            headers=_get_headers(),
            params={"instruments": instrument},
            timeout=10,
        )
        if response.status_code == 200:
            prices = response.json().get("prices", [])
            if prices:
                p = prices[0]
                return {
                    "instrument": p.get("instrument"),
                    "bid": float(p.get("bids", [{}])[0].get("price", 0)),
                    "ask": float(p.get("asks", [{}])[0].get("price", 0)),
                    "spread": float(p.get("quotes", [{}])[0].get("spread", 0)) if p.get("quotes") else 0,
                    "time": p.get("time"),
                }
    except Exception as e:
        logger.error(f"OANDA quote failed: {e}")
    return None


def place_order(instrument: str, units: int, side: str = "BUY",
                order_type: str = "MARKET", price: float = 0,
                stop_loss: float = 0, take_profit: float = 0) -> Dict:
    if not is_configured():
        return {"status": "error", "message": "Not configured"}
    try:
        units_signed = units if side == "BUY" else -units
        order_data = {
            "order": {
                "type": order_type,
                "instrument": instrument,
                "units": str(units_signed),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        if order_type == "LIMIT":
            order_data["order"]["price"] = str(price)
        if stop_loss:
            order_data["order"]["stopLossOnFill"] = {"price": str(stop_loss)}
        if take_profit:
            order_data["order"]["takeProfitOnFill"] = {"price": str(take_profit)}

        response = requests.post(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/orders",
            headers=_get_headers(),
            json=order_data,
            timeout=10,
        )
        if response.status_code == 201:
            data = response.json().get("orderCreateTransaction", {})
            return {"status": "success", "order_id": data.get("id")}
        return {"status": "error", "message": response.text[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_positions() -> List[Dict]:
    if not is_configured():
        return []
    try:
        response = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/openPositions",
            headers=_get_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            positions = response.json().get("positions", [])
            result = []
            for p in positions:
                long_units = int(p.get("long", {}).get("units", 0))
                short_units = int(p.get("short", {}).get("units", 0))
                result.append({
                    "instrument": p.get("instrument"),
                    "units": long_units + short_units,
                    "side": "LONG" if long_units > 0 else "SHORT" if short_units > 0 else "FLAT",
                    "unrealized_pnl": float(p.get("unrealizedP", 0)),
                    "entry_price": float(p.get("long", {}).get("averagePrice", 0) or p.get("short", {}).get("averagePrice", 0)),
                })
            return result
    except Exception as e:
        logger.error(f"OANDA positions failed: {e}")
    return []


def get_account_summary() -> Dict:
    if not is_configured():
        return {}
    try:
        response = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/summary",
            headers=_get_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            return response.json().get("account", {})
    except Exception as e:
        logger.error(f"OANDA account summary failed: {e}")
    return {}


def get_available_instruments() -> List[str]:
    if not is_configured():
        return []
    try:
        response = requests.get(
            f"{OANDA_BASE_URL}/v3/accounts/{OANDA_ACCOUNT_ID}/instruments",
            headers=_get_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            instruments = response.json().get("instruments", [])
            return [i.get("name") for i in instruments]
    except Exception as e:
        logger.error(f"OANDA instruments failed: {e}")
    return []
