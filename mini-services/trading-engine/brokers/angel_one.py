"""
Angel One SmartAPI Integration Module

Angel One (formerly Angel Broking) — one of India's largest retail brokers.
Free API access, good for algo trading.

Setup:
1. Get API credentials from https://smartapi.angelbroking.com/
2. pip install smartapi-python (or use requests directly)
3. Set env vars: ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PASSWORD, ANGEL_TOTP_SECRET
4. TOTP required for daily login (use pyotp to generate)
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Try to import SmartAPI
try:
    from SmartApi import SmartConnect
    ANGEL_AVAILABLE = True
except ImportError:
    ANGEL_AVAILABLE = False
    logger.warning("SmartApi not installed. Run: pip install smartapi-python")

# Credentials
ANGEL_API_KEY = os.environ.get("ANGEL_API_KEY", "")
ANGEL_CLIENT_CODE = os.environ.get("ANGEL_CLIENT_CODE", "")
ANGEL_PASSWORD = os.environ.get("ANGEL_PASSWORD", "")
ANGEL_TOTP_SECRET = os.environ.get("ANGGEL_TOTP_SECRET", "")
ANGEL_ACCESS_TOKEN = os.environ.get("ANGEL_ACCESS_TOKEN", "")

_angel_client: Optional[Any] = None


def is_configured() -> bool:
    return bool(ANGEL_API_KEY and ANGEL_CLIENT_CODE and ANGEL_AVAILABLE)


def get_client() -> Optional[Any]:
    global _angel_client
    if not is_configured():
        return None
    if _angel_client is None:
        try:
            _angel_client = SmartConnect(api_key=ANGEL_API_KEY)
            if ANGEL_ACCESS_TOKEN:
                _angel_client.setAccessToken(ANGEL_ACCESS_TOKEN)
            logger.info("Angel One client initialized")
        except Exception as e:
            logger.error(f"Angel One init failed: {e}")
            return None
    return _angel_client


def test_connection() -> Dict:
    if not ANGEL_AVAILABLE:
        return {"connected": False, "message": "smartapi-python not installed. Run: pip install smartapi-python"}
    if not (ANGEL_API_KEY and ANGEL_CLIENT_CODE):
        return {"connected": False, "message": "API key + client code required from https://smartapi.angelbroking.com/"}
    try:
        client = get_client()
        if client is None:
            return {"connected": False, "message": "Client init failed"}
        # Try to get user profile
        profile = client.getProfile(refresh=False)
        if profile and profile.get("status"):
            data = profile.get("data", {})
            return {
                "connected": True,
                "message": f"Connected as {data.get('name', 'Unknown')}",
                "user": data.get("name"),
                "email": data.get("email"),
                "broker": "Angel One",
            }
        return {"connected": False, "message": f"Profile fetch failed: {profile.get('message', '')}"}
    except Exception as e:
        return {"connected": False, "message": f"Connection error: {str(e)}"}


def fetch_historical(tradingsymbol: str, exchange: str, from_date: datetime, to_date: datetime, interval: str = "ONE_DAY") -> List[Dict]:
    client = get_client()
    if client is None:
        return []
    try:
        # Need instrument token — would need to look up
        historicParams = {
            "exchange": exchange,
            "symboltoken": "0",  # placeholder — need lookup
            "interval": interval,
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M"),
        }
        data = client.candleData(historicParams)
        return [{"timestamp": d[0], "open": d[1], "high": d[2], "low": d[3], "close": d[4], "volume": d[5]} for d in data]
    except Exception as e:
        logger.error(f"Angel historical failed: {e}")
        return []


def get_ltp(tradingsymbol: str, exchange: str = "NSE") -> Optional[float]:
    client = get_client()
    if client is None:
        return None
    try:
        params = {"exchange": exchange, "tradingsymbol": tradingsymbol, "symboltoken": "0"}
        ltp_data = client.ltpData(params)
        return ltp_data.get("data", {}).get("ltp")
    except Exception as e:
        logger.error(f"Angel LTP failed: {e}")
        return None


def place_order(tradingsymbol: str, exchange: str, transaction_type: str, quantity: int,
                product: str = "MIS", order_type: str = "MARKET", price: float = 0) -> Dict:
    client = get_client()
    if client is None:
        return {"status": "error", "message": "Not configured"}
    try:
        order = {
            "variety": "NORMAL",
            "tradingsymbol": tradingsymbol,
            "symboltoken": "0",
            "transactiontype": transaction_type,
            "exchange": exchange,
            "ordertype": order_type,
            "producttype": product,
            "duration": "DAY",
            "quantity": str(quantity),
            "price": str(price),
        }
        order_id = client.placeOrder(order)
        return {"status": "success", "order_id": order_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_positions() -> List[Dict]:
    client = get_client()
    if client is None:
        return []
    try:
        positions = client.position()
        return positions.get("data", [])
    except Exception as e:
        logger.error(f"Angel positions failed: {e}")
        return []


def get_holdings() -> List[Dict]:
    client = get_client()
    if client is None:
        return []
    try:
        holdings = client.holding()
        return holdings.get("data", [])
    except Exception as e:
        logger.error(f"Angel holdings failed: {e}")
        return []


def get_funds() -> Dict:
    client = get_client()
    if client is None:
        return {"available": 0, "used": 0}
    try:
        funds = client.rmsLimit()
        return funds.get("data", {})
    except Exception as e:
        logger.error(f"Angel funds failed: {e}")
        return {"available": 0, "used": 0}
