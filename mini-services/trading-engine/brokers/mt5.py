"""
MetaTrader 5 Integration Module

PRODUCTION-ready integration with MetaTrader 5 terminal.
Auto-falls back to mock data when credentials are not configured.

Setup (Windows only - MT5 terminal required):
1. Install MT5 from your forex broker (IC Markets, FXTM, Exness, etc.)
2. Open a demo or live account, note login + password + server
3. pip install MetaTrader5
4. Set environment variables:
   - MT5_LOGIN (account number, e.g., 12345678)
   - MT5_PASSWORD (account password)
   - MT5_SERVER (e.g., ICMarketsSC-Demo)
5. MT5 terminal MUST be running in background (Python API connects via local socket)
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Try to import MetaTrader5 (Windows-only)
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 not installed. Run: pip install MetaTrader5. Using mock data.")

# Read credentials
MT5_LOGIN = os.environ.get("MT5_LOGIN", "")
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER = os.environ.get("MT5_SERVER", "")

_mt5_initialized = False


def is_configured() -> bool:
    """Check if MT5 credentials are configured."""
    return bool(MT5_LOGIN and MT5_PASSWORD and MT5_SERVER and MT5_AVAILABLE)


def initialize() -> bool:
    """Initialize MT5 connection. Returns True on success."""
    global _mt5_initialized
    if not is_configured():
        return False
    if _mt5_initialized:
        return True
    try:
        if not mt5.initialize():
            logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
            return False
        if not mt5.login(int(MT5_LOGIN), MT5_PASSWORD, MT5_SERVER):
            logger.error(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
        _mt5_initialized = True
        logger.info(f"MT5 connected: {MT5_LOGIN}@{MT5_SERVER}")
        return True
    except Exception as e:
        logger.error(f"MT5 init exception: {e}")
        return False


def shutdown() -> None:
    """Shutdown MT5 connection."""
    global _mt5_initialized
    if _mt5_initialized and MT5_AVAILABLE:
        try:
            mt5.shutdown()
        except Exception:
            pass
    _mt5_initialized = False


def test_connection() -> Dict:
    """Test connection to MT5 terminal."""
    if not MT5_AVAILABLE:
        return {
            "connected": False,
            "message": "MetaTrader5 package not installed. Run: pip install MetaTrader5",
        }
    if not (MT5_LOGIN and MT5_PASSWORD and MT5_SERVER):
        return {
            "connected": False,
            "message": "MT5 credentials not set. Set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER env vars.",
        }
    if not initialize():
        return {
            "connected": False,
            "message": "MT5 init failed. Ensure MT5 terminal is running with the same account logged in.",
        }
    try:
        info = mt5.account_info()
        if info is None:
            return {"connected": False, "message": "Failed to get account info"}
        return {
            "connected": True,
            "message": f"Connected: {info.name} | Balance: {info.currency} {info.balance}",
            "account": info.name,
            "login": info.login,
            "server": info.server,
            "balance": info.balance,
            "currency": info.currency,
            "equity": info.equity,
            "leverage": f"1:{info.leverage}",
            "company": info.company,
        }
    except Exception as e:
        return {"connected": False, "message": f"MT5 error: {str(e)}"}


# ============ HISTORICAL DATA ============
# MT5 timeframe constants
TIMEFRAMES = {
    "1m": mt5.TIMEFRAME_M1 if MT5_AVAILABLE else 1,
    "5m": mt5.TIMEFRAME_M5 if MT5_AVAILABLE else 5,
    "15m": mt5.TIMEFRAME_M15 if MT5_AVAILABLE else 15,
    "30m": mt5.TIMEFRAME_M30 if MT5_AVAILABLE else 30,
    "1h": mt5.TIMEFRAME_H1 if MT5_AVAILABLE else 60,
    "4h": mt5.TIMEFRAME_H4 if MT5_AVAILABLE else 240,
    "1d": mt5.TIMEFRAME_D1 if MT5_AVAILABLE else 1440,
}


def fetch_historical(
    symbol: str,
    timeframe: str = "1h",
    count: int = 1000,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> List[Dict]:
    """Fetch historical OHLC bars from MT5.
    
    Args:
        symbol: e.g., 'EURUSD', 'GBPUSD', 'XAUUSD'
        timeframe: '1m', '5m', '15m', '30m', '1h', '4h', '1d'
        count: number of bars to fetch (if from/to not specified)
        from_date, to_date: optional date range
    
    Returns list of {timestamp, open, high, low, close, volume}
    """
    if not initialize():
        return []
    tf = TIMEFRAMES.get(timeframe, mt5.TIMEFRAME_H1)
    try:
        if from_date and to_date:
            rates = mt5.copy_rates_range(symbol, tf, from_date, to_date)
        else:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            logger.error(f"MT5: no data for {symbol} {timeframe}")
            return []
        return [
            {
                "timestamp": datetime.fromtimestamp(r["time"], tz=timezone.utc).isoformat(),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": int(r.get("tick_volume", r.get("real_volume", 0))),
            }
            for r in rates
        ]
    except Exception as e:
        logger.error(f"MT5 historical fetch failed: {e}")
        return []


def get_last_tick(symbol: str) -> Optional[Dict]:
    """Get the latest tick (bid/ask) for a symbol."""
    if not initialize():
        return None
    try:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return {
            "symbol": symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "time": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
            "spread": (tick.ask - tick.bid) * 10000,  # in pips
        }
    except Exception as e:
        logger.error(f"MT5 tick fetch failed: {e}")
        return None


def get_symbol_info(symbol: str) -> Optional[Dict]:
    """Get symbol info (point, digits, contract size, etc.)."""
    if not initialize():
        return None
    try:
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return {
            "symbol": info.name,
            "digits": info.digits,
            "point": info.point,
            "contract_size": info.trade_contract_size,
            "min_lot": info.volume_min,
            "max_lot": info.volume_max,
            "step_lot": info.volume_step,
            "spread": info.spread,
            "currency_base": info.currency_base,
            "currency_profit": info.currency_profit,
            "description": info.description,
        }
    except Exception as e:
        logger.error(f"MT5 symbol_info failed: {e}")
        return None


# ============ ORDER PLACEMENT ============
def place_order(
    symbol: str,
    order_type: str = "BUY",  # BUY / SELL
    volume: float = 0.01,
    price: Optional[float] = None,
    sl: float = 0.0,
    tp: float = 0.0,
    deviation: int = 20,
    magic: int = 234000,
    comment: str = "QuantPulse",
) -> Dict:
    """Place a market or pending order on MT5.
    
    ⚠️  USE WITH CAUTION - places real orders with real money.
    """
    if not initialize():
        return {"status": "error", "message": "MT5 not initialized"}
    try:
        # Ensure symbol is visible
        info = mt5.symbol_info(symbol)
        if info is None:
            return {"status": "error", "message": f"Symbol {symbol} not found"}
        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                return {"status": "error", "message": f"Failed to select symbol {symbol}"}
        
        # Determine trade action
        if order_type.upper() == "BUY":
            action = mt5.TRADE_ACTION_DEAL
            ttype = mt5.ORDER_TYPE_BUY
            if price is None:
                price = info.ask
        else:
            action = mt5.TRADE_ACTION_DEAL
            ttype = mt5.ORDER_TYPE_SELL
            if price is None:
                price = info.bid
        
        request = {
            "action": action,
            "symbol": symbol,
            "volume": float(volume),
            "type": ttype,
            "price": float(price),
            "sl": float(sl),
            "tp": float(tp),
            "deviation": deviation,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            return {"status": "error", "message": "order_send returned None"}
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "status": "error",
                "retcode": result.retcode,
                "message": result.comment,
            }
        return {
            "status": "success",
            "order": result.order,
            "deal": result.deal,
            "price": result.price,
            "volume": result.volume,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def close_position(ticket: int) -> Dict:
    """Close an open position by ticket."""
    if not initialize():
        return {"status": "error", "message": "MT5 not initialized"}
    try:
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            return {"status": "error", "message": "Position not found"}
        pos = positions[0]
        # Reverse order to close
        order_type = "SELL" if pos.type == mt5.POSITION_TYPE_BUY else "BUY"
        result = place_order(
            symbol=pos.symbol,
            order_type=order_type,
            volume=pos.volume,
        )
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============ POSITIONS & ACCOUNT ============
def get_positions() -> List[Dict]:
    """Get all open positions."""
    if not initialize():
        return []
    try:
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "swap": p.swap,
                "time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
                "comment": p.comment,
            }
            for p in positions
        ]
    except Exception as e:
        logger.error(f"MT5 get_positions failed: {e}")
        return []


def get_account_info() -> Dict:
    """Get account info (balance, equity, margin, etc.)."""
    if not initialize():
        return {}
    try:
        info = mt5.account_info()
        if info is None:
            return {}
        return {
            "login": info.login,
            "name": info.name,
            "server": info.server,
            "currency": info.currency,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "margin_free": info.margin_free,
            "margin_level": info.margin_level,
            "profit": info.profit,
            "leverage": f"1:{info.leverage}",
            "company": info.company,
        }
    except Exception as e:
        logger.error(f"MT5 account_info failed: {e}")
        return {}


# ============ SYMBOL SELECTION HELPER ============
def get_available_symbols(pattern: str = "") -> List[str]:
    """Get list of available symbols (optionally filtered by pattern)."""
    if not initialize():
        return []
    try:
        if pattern:
            symbols = mt5.symbols_get(f"*{pattern}*")
        else:
            symbols = mt5.symbols_get()
        if symbols is None:
            return []
        return [s.name for s in symbols]
    except Exception as e:
        logger.error(f"MT5 symbols_get failed: {e}")
        return []
