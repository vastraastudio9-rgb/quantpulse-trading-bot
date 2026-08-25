"""
Interactive Brokers (IBKR) Integration Module

IBKR — global broker for multi-asset, multi-exchange trading.
Supports: US stocks, options, futures, forex, bonds, CFDs.

Setup (Windows):
1. Install TWS (Trader Workstation) or IB Gateway
2. Enable API: Configure > Settings > API > Enable ActiveX and Socket Clients
3. Set port: 7496 (TWS paper) or 7497 (TWS live) or 4002 (IB Gateway paper)
4. pip install ib_insync
5. Set env vars: IBKR_HOST (default: 127.0.0.1), IBKR_PORT (default: 7496), IBKR_CLIENT_ID (default: 1)
6. TWS/IB Gateway MUST be running
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from ib_insync import IB, Stock, Option, Forex, Future, Order, util
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    logger.warning("ib_insync not installed. Run: pip install ib_insync")

IBKR_HOST = os.environ.get("IBKR_HOST", "127.0.0.1")
IBKR_PORT = int(os.environ.get("IBKR_PORT", "7496"))
IBKR_CLIENT_ID = int(os.environ.get("IBKR_CLIENT_ID", "1"))

_ibkr_client: Optional[Any] = None


def is_configured() -> bool:
    return bool(IBKR_AVAILABLE and IBKR_PORT)


def get_client() -> Optional[Any]:
    global _ibkr_client
    if not is_configured():
        return None
    if _ibkr_client is None:
        try:
            _ibkr_client = IB()
            _ibkr_client.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID)
            logger.info(f"IBKR connected: {IBKR_HOST}:{IBKR_PORT} client={IBKR_CLIENT_ID}")
        except Exception as e:
            logger.error(f"IBKR connect failed: {e}")
            _ibkr_client = None
            return None
    return _ibkr_client


def test_connection() -> Dict:
    if not IBKR_AVAILABLE:
        return {"connected": False, "message": "ib_insync not installed. Run: pip install ib_insync"}
    try:
        ib = get_client()
        if ib is None:
            return {"connected": False, "message": f"Failed to connect. Ensure TWS/IB Gateway running on {IBKR_HOST}:{IBKR_PORT}"}
        account = ib.managedAccounts()
        if account:
            account_id = account[0]
            summary = ib.accountSummary(account_id)
            balance = next((s.value for s in summary if s.tag == "TotalCashValue"), "N/A")
            return {
                "connected": True,
                "message": f"Connected: account {account_id}, balance ${balance}",
                "account": account_id,
                "balance": balance,
                "broker": "Interactive Brokers",
            }
        return {"connected": False, "message": "No managed accounts found"}
    except Exception as e:
        return {"connected": False, "message": f"Connection error: {str(e)}"}


def fetch_historical(symbol: str, exchange: str = "SMART", currency: str = "USD",
                     duration: str = "180 D", bar_size: str = "1 day") -> List[Dict]:
    ib = get_client()
    if ib is None:
        return []
    try:
        contract = Stock(symbol, exchange, currency)
        ib.qualifyContracts(contract)
        bars = ib.reqHistoricalData(
            contract, endDateTime="", durationStr=duration,
            barSizeSetting=bar_size, whatToShow='TRADES', useRTH=True
        )
        return [{
            "timestamp": b.date.isoformat(),
            "open": b.open, "high": b.high, "low": b.low,
            "close": b.close, "volume": b.volume
        } for b in bars]
    except Exception as e:
        logger.error(f"IBKR historical failed: {e}")
        return []


def get_quote(symbol: str, exchange: str = "SMART", currency: str = "USD") -> Optional[Dict]:
    ib = get_client()
    if ib is None:
        return None
    try:
        contract = Stock(symbol, exchange, currency)
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract, '', False, False)
        ib.sleep(1)
        return {
            "symbol": symbol,
            "ltp": ticker.last,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "volume": ticker.volume,
        }
    except Exception as e:
        logger.error(f"IBKR quote failed: {e}")
    return None


def place_order(symbol: str, exchange: str, action: str, quantity: int,
                order_type: str = "MKT", limit_price: float = 0,
                currency: str = "USD") -> Dict:
    ib = get_client()
    if ib is None:
        return {"status": "error", "message": "Not connected"}
    try:
        contract = Stock(symbol, exchange, currency)
        ib.qualifyContracts(contract)
        order = Order(
            action=action,
            totalQuantity=quantity,
            orderType=order_type,
            lmtPrice=limit_price if order_type == "LMT" else 0,
        )
        trade = ib.placeOrder(contract, order)
        ib.sleep(1)
        if trade.orderStatus.status in ("Filled", "Submitted", "ApiPending"):
            return {"status": "success", "order_id": trade.order.orderId, "status_detail": trade.orderStatus.status}
        return {"status": "error", "message": f"Order status: {trade.orderStatus.status}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_positions() -> List[Dict]:
    ib = get_client()
    if ib is None:
        return []
    try:
        positions = ib.positions()
        return [{
            "symbol": p.contract.symbol,
            "position": p.position,
            "avg_cost": p.avgCost,
            "account": p.account,
        } for p in positions]
    except Exception as e:
        logger.error(f"IBKR positions failed: {e}")
    return []


def get_account_summary() -> Dict:
    ib = get_client()
    if ib is None:
        return {}
    try:
        account = ib.managedAccounts()
        if account:
            summary = ib.accountSummary(account[0])
            return {s.tag: s.value for s in summary}
    except Exception as e:
        logger.error(f"IBKR account summary failed: {e}")
    return {}


def disconnect():
    global _ibkr_client
    if _ibkr_client:
        _ibkr_client.disconnect()
        _ibkr_client = None
