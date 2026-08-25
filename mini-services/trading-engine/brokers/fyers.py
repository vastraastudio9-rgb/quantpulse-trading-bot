"""
Fyers API Integration Module

Fyers — popular Indian discount broker with good API for algo trading.
Free API, fast execution.

Setup:
1. Get API credentials from https://myapi.fyers.in/
2. pip install fyers-apiv3
3. Set env vars: FYERS_APP_ID, FYERS_SECRET_ID, FYERS_ACCESS_TOKEN
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from fyers_apiv3 import fyersModel
    FYERS_AVAILABLE = True
except ImportError:
    FYERS_AVAILABLE = False
    logger.warning("fyers-apiv3 not installed. Run: pip install fyers-apiv3")

FYERS_APP_ID = os.environ.get("FYERS_APP_ID", "")
FYERS_SECRET_ID = os.environ.get("FYERS_SECRET_ID", "")
FYERS_ACCESS_TOKEN = os.environ.get("FYERS_ACCESS_TOKEN", "")

_fyers_client: Optional[Any] = None


def is_configured() -> bool:
    return bool(FYERS_APP_ID and FYERS_ACCESS_TOKEN and FYERS_AVAILABLE)


def get_client() -> Optional[Any]:
    global _fyers_client
    if not is_configured():
        return None
    if _fyers_client is None:
        try:
            _fyers_client = fyersModel.FyersModel(
                token=FYERS_ACCESS_TOKEN,
                is_async=False,
                client_id=FYERS_APP_ID,
            )
            logger.info("Fyers client initialized")
        except Exception as e:
            logger.error(f"Fyers init failed: {e}")
            return None
    return _fyers_client


def test_connection() -> Dict:
    if not FYERS_AVAILABLE:
        return {"connected": False, "message": "fyers-apiv3 not installed. Run: pip install fyers-apiv3"}
    if not (FYERS_APP_ID and FYERS_ACCESS_TOKEN):
        return {"connected": False, "message": "App ID + access token required from https://myapi.fyers.in/"}
    try:
        client = get_client()
        if client is None:
            return {"connected": False, "message": "Client init failed"}
        profile = client.get_profile()
        if profile.get("s") == "ok":
            data = profile.get("data", {})
            return {
                "connected": True,
                "message": f"Connected as {data.get('name', 'Unknown')}",
                "user": data.get("name"),
                "email": data.get("email_id"),
                "broker": "Fyers",
            }
        return {"connected": False, "message": f"Profile failed: {profile.get('message', '')}"}
    except Exception as e:
        return {"connected": False, "message": f"Connection error: {str(e)}"}


def fetch_historical(symbol: str, resolution: str = "1D", date_format: int = 1,
                     range_from: str = "", range_to: str = "") -> List[Dict]:
    client = get_client()
    if client is None:
        return []
    try:
        data = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": date_format,
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "1",
        }
        history = client.history(data)
        candles = history.get("candles", [])
        return [{"timestamp": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]} for c in candles]
    except Exception as e:
        logger.error(f"Fyers historical failed: {e}")
        return []


def get_quote(symbol: str) -> Optional[Dict]:
    client = get_client()
    if client is None:
        return None
    try:
        quotes = client.quotes({"symbols": symbol})
        if quotes.get("s") == "ok":
            d = quotes.get("d", [{}])[0].get("v", {})
            return {
                "symbol": symbol,
                "ltp": d.get("lp", 0),
                "day_high": d.get("high_price", 0),
                "day_low": d.get("low_price", 0),
                "volume": d.get("volume", 0),
            }
    except Exception as e:
        logger.error(f"Fyers quote failed: {e}")
    return None


def place_order(symbol: str, qty: int, side: str, product: str = "INTRADAY",
                order_type: str = "MARKET", limit_price: float = 0,
                stop_price: float = 0, validity: str = "DAY") -> Dict:
    client = get_client()
    if client is None:
        return {"status": "error", "message": "Not configured"}
    try:
        data = {
            "symbol": symbol,
            "qty": qty,
            "type": 2 if order_type == "MARKET" else 1,
            "side": 1 if side == "BUY" else -1,
            "productType": product,
            "limitPrice": limit_price,
            "stopPrice": stop_price,
            "validity": validity,
            "offlineOrder": "False",
        }
        response = client.place_order(data=data)
        if response.get("s") == "ok":
            return {"status": "success", "order_id": response.get("id")}
        return {"status": "error", "message": response.get("message", "")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_positions() -> Dict:
    client = get_client()
    if client is None:
        return {"netPositions": []}
    try:
        return client.positions()
    except Exception as e:
        logger.error(f"Fyers positions failed: {e}")
        return {"netPositions": []}


def get_funds() -> Dict:
    client = get_client()
    if client is None:
        return {"available": 0, "used": 0}
    try:
        funds = client.funds()
        if funds.get("s") == "ok":
            return funds.get("fund_limit", [])
    except Exception as e:
        logger.error(f"Fyers funds failed: {e}")
    return {"available": 0, "used": 0}
