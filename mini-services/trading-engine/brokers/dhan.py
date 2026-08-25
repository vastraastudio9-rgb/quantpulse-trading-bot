"""
Dhan Trade API Integration Module

Dhan — modern Indian broker built specifically for algo traders.
Free API, REST + WebSocket.

Setup:
1. Get API credentials from https://dhanhq.co/
2. pip install dhanhq
3. Set env vars: DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from dhanhq import dhanhq
    DHAN_AVAILABLE = True
except ImportError:
    DHAN_AVAILABLE = False
    logger.warning("dhanhq not installed. Run: pip install dhanhq")

DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN", "")

_dhan_client: Optional[Any] = None


def is_configured() -> bool:
    return bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN and DHAN_AVAILABLE)


def get_client() -> Optional[Any]:
    global _dhan_client
    if not is_configured():
        return None
    if _dhan_client is None:
        try:
            _dhan_client = dhanhq(client_id=DHAN_CLIENT_ID, access_token=DHAN_ACCESS_TOKEN)
            logger.info("Dhan client initialized")
        except Exception as e:
            logger.error(f"Dhan init failed: {e}")
            return None
    return _dhan_client


def test_connection() -> Dict:
    if not DHAN_AVAILABLE:
        return {"connected": False, "message": "dhanhq not installed. Run: pip install dhanhq"}
    if not (DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN):
        return {"connected": False, "message": "Client ID + access token required from https://dhanhq.co/"}
    try:
        client = get_client()
        if client is None:
            return {"connected": False, "message": "Client init failed"}
        funds = client.get_fund_limits()
        if funds and funds.get("status") == "success":
            return {
                "connected": True,
                "message": f"Connected (Dhan Client: {DHAN_CLIENT_ID})",
                "broker": "Dhan",
            }
        return {"connected": False, "message": "Fund limit check failed"}
    except Exception as e:
        return {"connected": False, "message": f"Connection error: {str(e)}"}


def fetch_historical(security_id: str, exchange_segment: str = "NSE_EQ",
                     instrument: str = "EQUITY", interval: str = "1D",
                     from_date: str = "", to_date: str = "") -> List[Dict]:
    client = get_client()
    if client is None:
        return []
    try:
        data = client.ohlc_history(security_id, exchange_segment, instrument, interval, from_date, to_date)
        if data.get("status") == "success":
            return data.get("data", {}).get("ohlc", [])
    except Exception as e:
        logger.error(f"Dhan historical failed: {e}")
    return []


def get_ltp(security_id: str, exchange_segment: str = "NSE_EQ") -> Optional[float]:
    client = get_client()
    if client is None:
        return None
    try:
        data = client.market_feed(security_id, exchange_segment)
        return data.get("data", {}).get("ltp")
    except Exception as e:
        logger.error(f"Dhan LTP failed: {e}")
    return None


def place_order(security_id: str, exchange_segment: str = "NSE_EQ",
                transaction_type: str = "BUY", quantity: int = 1,
                product_type: str = "MIS", order_type: str = "MARKET",
                price: float = 0, trigger_price: float = 0) -> Dict:
    client = get_client()
    if client is None:
        return {"status": "error", "message": "Not configured"}
    try:
        response = client.place_order(
            security_id=security_id,
            exchange_segment=exchange_segment,
            transaction_type=transaction_type,
            quantity=quantity,
            product_type=product_type,
            order_type=order_type,
            price=price,
            trigger_price=trigger_price,
            validity="DAY",
        )
        if response.get("status") == "success":
            return {"status": "success", "order_id": response.get("orderId")}
        return {"status": "error", "message": response.get("remarks", "")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_positions() -> List[Dict]:
    client = get_client()
    if client is None:
        return []
    try:
        positions = client.get_positions()
        return positions.get("data", [])
    except Exception as e:
        logger.error(f"Dhan positions failed: {e}")
    return []


def get_funds() -> Dict:
    client = get_client()
    if client is None:
        return {"available": 0, "used": 0}
    try:
        funds = client.get_fund_limits()
        return funds.get("data", {})
    except Exception as e:
        logger.error(f"Dhan funds failed: {e}")
    return {"available": 0, "used": 0}
