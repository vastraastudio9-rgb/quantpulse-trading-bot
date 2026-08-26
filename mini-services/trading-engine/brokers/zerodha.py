"""
Zerodha Kite Connect Integration Module

PRODUCTION-ready integration with Zerodha Kite Connect API.
Auto-falls back to mock data when credentials are not configured.

Setup:
1. pip install kiteconnect
2. Get API key from https://developers.kite.trade/
3. Set environment variables OR pass credentials:
   - KITE_API_KEY
   - KITE_API_SECRET
   - KITE_ACCESS_TOKEN (refreshed daily via auth flow)

Auth Flow (run daily):
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=API_KEY)
    print(kite.login_url())  # Open in browser, get request_token from redirect
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    access_token = data["access_token"]
    kite.set_access_token(access_token)
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Try to import kiteconnect
try:
    from kiteconnect import KiteConnect, KiteTicker
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    logger.warning("kiteconnect not installed. Run: pip install kiteconnect. Using mock data.")

# Read credentials from env
KITE_API_KEY = os.environ.get("KITE_API_KEY", "")
KITE_API_SECRET = os.environ.get("KITE_API_SECRET", "")
KITE_ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN", "")

_kite_client: Optional[Any] = None
_kite_ticker: Optional[Any] = None


def is_configured() -> bool:
    """Check if Zerodha credentials are configured."""
    return bool(KITE_API_KEY and KITE_API_SECRET and KITE_ACCESS_TOKEN and KITE_AVAILABLE)


def configure_credentials(api_key: str, api_secret: str, access_token: str = "") -> None:
    """Keep Kite credentials in process memory only and reset cached clients."""
    global KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN, _kite_client, _kite_ticker
    KITE_API_KEY = (api_key or "").strip()
    KITE_API_SECRET = (api_secret or "").strip()
    KITE_ACCESS_TOKEN = (access_token or "").strip()
    os.environ["KITE_API_KEY"] = KITE_API_KEY
    os.environ["KITE_API_SECRET"] = KITE_API_SECRET
    if KITE_ACCESS_TOKEN:
        os.environ["KITE_ACCESS_TOKEN"] = KITE_ACCESS_TOKEN
    else:
        os.environ.pop("KITE_ACCESS_TOKEN", None)
    _kite_client = None
    _kite_ticker = None
    _instrument_tokens.clear()


def begin_auth(api_key: str, api_secret: str) -> Dict:
    """Prepare the daily Kite browser login without writing credentials to disk."""
    if not KITE_AVAILABLE:
        raise RuntimeError("kiteconnect package is not installed")
    if not api_key or not api_secret:
        raise ValueError("API key and API secret are required")
    configure_credentials(api_key, api_secret)
    client = KiteConnect(api_key=KITE_API_KEY)
    return {
        "login_url": client.login_url(),
        "storage": "PROCESS_MEMORY_ONLY",
        "next_step": "Login to Kite, then paste the request_token from the redirect URL.",
    }


def complete_auth(request_token: str) -> Dict:
    """Exchange a single-use request token for today's in-memory access token."""
    if not KITE_AVAILABLE:
        raise RuntimeError("kiteconnect package is not installed")
    if not KITE_API_KEY or not KITE_API_SECRET:
        raise ValueError("Start Kite login with API key and API secret first")
    if not request_token:
        raise ValueError("request_token is required")
    client = KiteConnect(api_key=KITE_API_KEY)
    session = client.generate_session(request_token.strip(), api_secret=KITE_API_SECRET)
    access_token = str(session.get("access_token", ""))
    if not access_token:
        raise RuntimeError("Kite did not return an access token")
    configure_credentials(KITE_API_KEY, KITE_API_SECRET, access_token)
    return {"authenticated": True, "storage": "PROCESS_MEMORY_ONLY"}


def get_client() -> Optional[Any]:
    """Get or create KiteConnect client. Returns None if not configured."""
    global _kite_client
    if not is_configured():
        return None
    if _kite_client is None:
        try:
            _kite_client = KiteConnect(api_key=KITE_API_KEY)
            _kite_client.set_access_token(KITE_ACCESS_TOKEN)
            logger.info("Zerodha Kite client initialized")
        except Exception as e:
            logger.error(f"Failed to init Kite client: {e}")
            return None
    return _kite_client


def test_connection() -> Dict:
    """Test connection to Zerodha Kite. Returns status dict."""
    if not KITE_AVAILABLE:
        return {
            "connected": False,
            "message": "kiteconnect package not installed. Run: pip install kiteconnect",
        }
    if not (KITE_API_KEY and KITE_API_SECRET):
        return {
            "connected": False,
            "message": "API key/secret not set. Get from https://developers.kite.trade/",
        }
    if not KITE_ACCESS_TOKEN:
        return {
            "connected": False,
            "message": "Access token missing. Run daily auth flow to generate.",
        }
    try:
        client = get_client()
        if client is None:
            return {"connected": False, "message": "Failed to create client"}
        profile = client.profile()
        return {
            "connected": True,
            "message": f"Connected as {profile.get('user_name', 'Unknown')} ({profile.get('email', '')})",
            "user": profile.get("user_name"),
            "email": profile.get("email"),
            "broker": profile.get("broker"),
            "exchanges": profile.get("exchanges", []),
            "products": profile.get("products", []),
        }
    except Exception as e:
        return {"connected": False, "message": f"Connection error: {str(e)}"}


# ============ INSTRUMENT TOKEN MAPPING ============
# Cache for symbol -> instrument_token mapping
_instrument_tokens: Dict[str, int] = {}


def _load_instruments() -> None:
    """Load all instruments from Kite and cache tokens."""
    if not is_configured():
        return
    client = get_client()
    if client is None:
        return
    try:
        instruments = client.instruments()
        for inst in instruments:
            key = f"{inst.get('tradingsymbol', '')}"
            _instrument_tokens[key] = inst.get("instrument_token", 0)
        logger.info(f"Loaded {len(_instrument_tokens)} instruments from Kite")
    except Exception as e:
        logger.error(f"Failed to load instruments: {e}")


def get_instrument_token(tradingsymbol: str) -> Optional[int]:
    """Get Kite instrument_token for a tradingsymbol (e.g., 'NIFTY 24800 CE')."""
    if not _instrument_tokens:
        _load_instruments()
    return _instrument_tokens.get(tradingsymbol.upper())


# ============ HISTORICAL DATA ============
def fetch_historical(
    tradingsymbol: str,
    from_date: datetime,
    to_date: datetime,
    interval: str = "day",
) -> List[Dict]:
    """Fetch historical OHLC data from Zerodha.
    
    Args:
        tradingsymbol: e.g., 'NIFTY 50' for index, or 'NIFTY2480020500CE' for options
        from_date, to_date: datetime range
        interval: 'minute', '3minute', '5minute', '10minute', '15minute', '30minute', '60minute', 'day'
    
    Returns list of {timestamp, open, high, low, close, volume}
    """
    client = get_client()
    if client is None:
        return []
    token = get_instrument_token(tradingsymbol)
    if not token:
        logger.error(f"Instrument token not found for {tradingsymbol}")
        return []
    try:
        data = client.historical_data(token, from_date, to_date, interval)
        return [
            {
                "timestamp": d["date"].isoformat() if hasattr(d["date"], "isoformat") else str(d["date"]),
                "open": float(d["open"]),
                "high": float(d["high"]),
                "low": float(d["low"]),
                "close": float(d["close"]),
                "volume": int(d.get("volume", 0)),
            }
            for d in data
        ]
    except Exception as e:
        logger.error(f"Historical data fetch failed for {tradingsymbol}: {e}")
        return []


# ============ LIVE QUOTES ============
def get_live_ltp(tradingsymbol: str) -> Optional[float]:
    """Get last traded price for an instrument."""
    client = get_client()
    if client is None:
        return None
    token = get_instrument_token(tradingsymbol)
    if not token:
        return None
    try:
        quote = client.ltp([f"NSE:{tradingsymbol}"])
        return quote.get(f"NSE:{tradingsymbol}", {}).get("last_price")
    except Exception as e:
        logger.error(f"LTP fetch failed: {e}")
        return None


def get_full_quote(tradingsymbol: str, exchange: str = "NSE") -> Optional[Dict]:
    """Get full quote (OHLC, OI, volume, etc.) for an instrument."""
    client = get_client()
    if client is None:
        return None
    try:
        quote = client.quote([f"{exchange}:{tradingsymbol}"])
        key = f"{exchange}:{tradingsymbol}"
        if key not in quote:
            return None
        q = quote[key]
        return {
            "symbol": tradingsymbol,
            "ltp": q.get("last_price", 0),
            "day_open": q.get("ohlc", {}).get("open", 0),
            "day_high": q.get("ohlc", {}).get("high", 0),
            "day_low": q.get("ohlc", {}).get("low", 0),
            "day_close": q.get("ohlc", {}).get("close", 0),
            "volume": q.get("volume", 0),
            "oi": q.get("oi", 0),
            "oi_day_high": q.get("oi_day_high", 0),
            "oi_day_low": q.get("oi_day_low", 0),
            "timestamp": q.get("last_trade_time", datetime.now(timezone.utc)).isoformat() if hasattr(q.get("last_trade_time"), "isoformat") else str(q.get("last_trade_time", "")),
        }
    except Exception as e:
        logger.error(f"Quote fetch failed: {e}")
        return None


# ============ OPTION CHAIN ============
def get_option_chain(tradingsymbol: str, expiry: Optional[str] = None) -> Optional[Dict]:
    """Fetch option chain for an underlying (NIFTY, BANKNIFTY, etc.).
    
    Args:
        tradingsymbol: 'NIFTY', 'BANKNIFTY', etc.
        expiry: 'YYYY-MM-DD' format. If None, picks nearest expiry.
    """
    client = get_client()
    if client is None:
        return None
    try:
        # Get all FNO instruments for the underlying
        instruments = client.instruments("FNO")
        underlying_insts = [i for i in instruments if i.get("name") == tradingsymbol]
        if not underlying_insts:
            return None
        # Pick expiry
        expiries = sorted(set(i["expiry"] for i in underlying_insts))
        if expiry:
            target_expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
            chosen = next((e for e in expiries if e == target_expiry), expiries[0])
        else:
            today = datetime.now(timezone.utc).date()
            chosen = next((e for e in expiries if e >= today), expiries[0])
        
        # Filter to chosen expiry
        chain_insts = [i for i in underlying_insts if i["expiry"] == chosen]
        # Get spot
        spot_quote = client.ltp([f"NSE:{tradingsymbol}"])
        spot = spot_quote.get(f"NSE:{tradingsymbol}", {}).get("last_price", 0)
        
        # Build chain
        chain = []
        for inst in chain_insts:
            q = client.quote([f"NFO:{inst['tradingsymbol']}"]).get(f"NFO:{inst['tradingsymbol']}", {})
            chain.append({
                "strike": inst["strike"],
                "option_type": inst["instrument_type"],  # CE / PE
                "tradingsymbol": inst["tradingsymbol"],
                "ltp": q.get("last_price", 0),
                "oi": q.get("oi", 0),
                "volume": q.get("volume", 0),
                "iv": q.get("iv", 0) if "iv" in q else None,
                "delta": None,  # Kite doesn't provide Greeks directly
                "theta": None,
                "gamma": None,
                "vega": None,
            })
        return {
            "symbol": tradingsymbol,
            "spot": spot,
            "expiry": chosen.isoformat(),
            "chain": chain,
            "source": "zerodha_live",
        }
    except Exception as e:
        logger.error(f"Option chain fetch failed: {e}")
        return None


# ============ ORDER PLACEMENT ============
def place_order(
    tradingsymbol: str,
    exchange: str = "NFO",
    transaction_type: str = "BUY",  # BUY / SELL
    quantity: int = 0,
    product: str = "MIS",  # MIS / CNC / NRML
    order_type: str = "MARKET",  # MARKET / LIMIT / SL / SL-M
    price: float = 0,
    trigger_price: float = 0,
    validity: str = "DAY",
) -> Dict:
    """Place an order on Zerodha.
    
    ⚠️  USE WITH CAUTION - places real orders with real money.
    """
    client = get_client()
    if client is None:
        return {"status": "error", "message": "Kite not configured"}
    try:
        order_id = client.place_order(
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            product=product,
            order_type=order_type,
            price=price,
            trigger_price=trigger_price,
            validity=validity,
        )
        return {"status": "success", "order_id": order_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def cancel_order(order_id: str) -> Dict:
    """Cancel an open order."""
    client = get_client()
    if client is None:
        return {"status": "error", "message": "Kite not configured"}
    try:
        client.cancel_order(order_id)
        return {"status": "success", "order_id": order_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============ POSITIONS & MARGINS ============
def get_positions() -> Dict:
    """Get current open positions."""
    client = get_client()
    if client is None:
        return {"net": [], "day": []}
    try:
        return client.positions()
    except Exception as e:
        logger.error(f"Positions fetch failed: {e}")
        return {"net": [], "day": []}


def get_margins() -> Dict:
    """Get available margin / funds."""
    client = get_client()
    if client is None:
        return {"available": 0, "used": 0, "total": 0}
    try:
        margins = client.margins()
        equity = margins.get("equity", {})
        return {
            "available": equity.get("available", {}).get("live_balance", 0),
            "used": equity.get("utilised", {}).get("debits", 0),
            "total": equity.get("net", 0),
        }
    except Exception as e:
        logger.error(f"Margins fetch failed: {e}")
        return {"available": 0, "used": 0, "total": 0}


# ============ WEBSOCKET (live ticks) ============
def start_websocket(symbols: List[str], on_tick: Any = None) -> bool:
    """Start KiteTicker WebSocket for live ticks.
    
    Args:
        symbols: List of tradingsymbols to subscribe
        on_tick: callback function (tick_data) -> None
    
    Returns True if started, False if not configured.
    """
    if not is_configured():
        return False
    global _kite_ticker
    try:
        tokens = [get_instrument_token(s) for s in symbols if get_instrument_token(s)]
        _kite_ticker = KiteTicker(KITE_API_KEY, KITE_ACCESS_TOKEN)
        
        def on_ticks(ws, ticks):
            if on_tick:
                for tick in ticks:
                    on_tick(tick)
        
        def on_connect(ws, response):
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)
            logger.info(f"KiteTicker subscribed to {len(tokens)} tokens")
        
        def on_close(ws, code, reason):
            logger.warning(f"KiteTicker closed: {code} - {reason}")
        
        _kite_ticker.on_ticks = on_ticks
        _kite_ticker.on_connect = on_connect
        _kite_ticker.on_close = on_close
        _kite_ticker.connect(threaded=True)
        return True
    except Exception as e:
        logger.error(f"WebSocket start failed: {e}")
        return False


def stop_websocket() -> None:
    """Stop the WebSocket connection."""
    global _kite_ticker
    if _kite_ticker:
        try:
            _kite_ticker.close()
        except Exception:
            pass
        _kite_ticker = None
