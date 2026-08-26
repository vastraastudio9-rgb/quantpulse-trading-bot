"""
Upstox API Integration Module

Upstox — popular Indian discount broker with REST API.
Free API access, good documentation.

Setup:
1. Get API credentials from https://upstox.com/developer/api/
2. pip install upstox-python-sdk
3. Set env vars: UPSTOX_API_KEY, UPSTOX_API_SECRET, UPSTOX_ACCESS_TOKEN
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    # Upstox SDK might have different import paths
    import requests
    UPSTOX_AVAILABLE = True
except ImportError:
    UPSTOX_AVAILABLE = False

UPSTOX_API_KEY = os.environ.get("UPSTOX_API_KEY", "")
UPSTOX_API_SECRET = os.environ.get("UPSTOX_API_SECRET", "")
UPSTOX_ACCESS_TOKEN = os.environ.get("UPSTOX_ACCESS_TOKEN", "")
UPSTOX_BASE_URL = "https://api.upstox.com/v2"


def is_configured() -> bool:
    return bool(UPSTOX_API_KEY and UPSTOX_ACCESS_TOKEN and UPSTOX_AVAILABLE)


def _get_headers() -> Dict:
    return {
        "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def test_connection() -> Dict:
    if not UPSTOX_AVAILABLE:
        return {"connected": False, "message": "requests not installed"}
    if not (UPSTOX_API_KEY and UPSTOX_ACCESS_TOKEN):
        return {"connected": False, "message": "API key + access token required from https://upstox.com/developer/api/"}
    try:
        import requests
        response = requests.get(
            f"{UPSTOX_BASE_URL}/user/get-profile",
            headers=_get_headers(),
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json().get("data", {})
            return {
                "connected": True,
                "message": f"Connected as {data.get('user_name', 'Unknown')}",
                "user": data.get("user_name"),
                "email": data.get("email"),
                "broker": "Upstox",
            }
        return {"connected": False, "message": f"HTTP {response.status_code}: {response.text[:100]}"}
    except Exception as e:
        return {"connected": False, "message": f"Connection error: {str(e)}"}


def fetch_historical(instrument_key: str, interval: str = "1d",
                     from_date: str = "", to_date: str = "") -> List[Dict]:
    if not is_configured():
        return []
    try:
        import requests
        from urllib.parse import quote
        intervals = {
            "minute": ("minutes", "1"), "5minute": ("minutes", "5"),
            "15minute": ("minutes", "15"), "60minute": ("hours", "1"),
            "day": ("days", "1"), "1d": ("days", "1"),
        }
        if interval not in intervals:
            logger.error(f"Unsupported Upstox historical interval: {interval}")
            return []
        unit, amount = intervals[interval]
        encoded_key = quote(instrument_key, safe="")
        # V3 path order is explicitly to_date followed by from_date.
        url = f"https://api.upstox.com/v3/historical-candle/{encoded_key}/{unit}/{amount}/{to_date}/{from_date}"
        response = requests.get(url, headers=_get_headers(), timeout=10)
        if response.status_code == 200:
            candles = response.json().get("data", {}).get("candles", [])
            return [{"timestamp": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4],
                     "volume": c[5], "open_interest": c[6] if len(c) > 6 else 0} for c in candles]
    except Exception as e:
        logger.error(f"Upstox historical failed: {e}")
    return []


def get_ltp(instrument_key: str) -> Optional[float]:
    if not is_configured():
        return None
    try:
        import requests
        url = f"{UPSTOX_BASE_URL}/market-quote/ltp?instrument_key={instrument_key}"
        response = requests.get(url, headers=_get_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", {})
            return list(data.values())[0].get("last_price") if data else None
    except Exception as e:
        logger.error(f"Upstox LTP failed: {e}")
    return None


def place_order(instrument_token: str, transaction_type: str, quantity: int,
                product: str = "I", order_type: str = "MARKET",
                price: float = 0, validity: str = "DAY") -> Dict:
    if not is_configured():
        return {"status": "error", "message": "Not configured"}
    try:
        import requests
        payload = {
            "quantity": quantity,
            "product": product,
            "validity": validity,
            "price": price,
            "tag": "string",
            "instrument_token": instrument_token,
            "order_type": order_type,
            "transaction_type": transaction_type,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False,
        }
        response = requests.post(
            f"{UPSTOX_BASE_URL}/order/place",
            headers=_get_headers(),
            json=payload,
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json().get("data", {})
            return {"status": "success", "order_id": data.get("order_id")}
        return {"status": "error", "message": response.text[:100]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_positions() -> List[Dict]:
    if not is_configured():
        return []
    try:
        import requests
        response = requests.get(f"{UPSTOX_BASE_URL}/portfolio/short-term-positions", headers=_get_headers(), timeout=10)
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        logger.error(f"Upstox positions failed: {e}")
    return []


def get_funds() -> Dict:
    if not is_configured():
        return {"available": 0, "used": 0}
    try:
        import requests
        response = requests.get(f"{UPSTOX_BASE_URL}/user/get-funds-and-margin", headers=_get_headers(), timeout=10)
        if response.status_code == 200:
            return response.json().get("data", {})
    except Exception as e:
        logger.error(f"Upstox funds failed: {e}")
    return {"available": 0, "used": 0}
