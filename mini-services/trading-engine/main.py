"""
Trading Engine API - FastAPI Service
Port: 3030

Endpoints:
- GET  /health
- GET  /api/instruments
- GET  /api/quote/{symbol}
- GET  /api/option-chain/{symbol}
- GET  /api/strategies
- GET  /api/signals                  - latest signals feed
- POST /api/signals/generate         - generate new signal {strategy, symbol}
- GET  /api/positions                - mock open positions
- POST /api/backtest                 - run backtest
- GET  /api/dashboard                - aggregate dashboard data
- GET  /api/brokers/status           - all broker connections status
- POST /api/brokers/zerodha/test     - test Zerodha connection (with optional credentials)
- POST /api/brokers/mt5/test         - test MT5 connection
- POST /api/brokers/telegram/test    - test Telegram bot
- POST /api/brokers/telegram/send    - send signal alert to Telegram
"""
import os
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from market_data import INSTRUMENTS, get_live_quote, get_option_chain, generate_history
from strategies import STRATEGIES, generate_signal, generate_signals_feed
from backtest import run_backtest, calc_costs
from brokers import zerodha as zerodha_broker
from brokers import mt5 as mt5_broker
from brokers import angel_one as angel_broker
from brokers import fyers as fyers_broker
from brokers import dhan as dhan_broker
from brokers import upstox as upstox_broker
from brokers import interactive_brokers as ibkr_broker
from brokers import oanda as oanda_broker
from brokers import telegram_bot
from observability import logger, metrics, generate_request_id, log_request_event
from risk_engine import get_portfolio_engine
from execution_engine import get_execution_engine
from auto_bot import get_auto_bot, BotConfig
from trade_journal import get_journal
from trading_mode import get_trading_mode
from live_execution import execute_live_legs
from autonomy import get_autonomy_supervisor
from research_optimizer import load_policy, run_research
from market_data_store import get_market_data_store
from orb_algorithm import ORBConfig, run_orb_backtest
from nse_data_adapter import download_nse_index
from broker_data_adapter import download_broker_candles
from futures_research import near_month_stock_futures, run_futures_orb_batch
from kite_rnd_pipeline import run_nifty_orb_pipeline


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Resume only persisted PAPER autonomy after a process restart."""
    supervisor = get_autonomy_supervisor()
    if supervisor.config.enabled:
        supervisor.start()
        get_execution_engine().start_monitoring(5)
        bot = get_auto_bot()
        bot.config.enabled = True
        bot.start()
    yield


app = FastAPI(
    title="Multi-Asset Trading Engine API",
    description="Indian F&O + MCX + Forex trading engine with options strategies, signals & backtesting",
    version="1.0.0",
    lifespan=lifespan,
)

# Browser access is same-origin in production. Development origins must be
# explicitly configured instead of allowing every website to call the engine.
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ REQUEST LOGGING MIDDLEWARE ============
@app.middleware("http")
async def log_requests_middleware(request, call_next):
    """Log every request with timing + request_id."""
    request_id = generate_request_id()
    start = time.time()
    
    # Skip health checks to reduce noise
    path = request.url.path
    if path not in ("/health", "/metrics"):
        logger.info(
            "request_start",
            request_id=request_id,
            method=request.method,
            path=path,
        )
    
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and os.getenv("REQUIRE_OPERATOR_TOKEN", "false").lower() == "true":
        expected = os.getenv("OPERATOR_TOKEN", "")
        supplied = request.headers.get("X-Operator-Token", "")
        if not expected or supplied != expected:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Operator authorization required"})

    response = await call_next(request)
    
    duration_ms = (time.time() - start) * 1000
    metrics.record_request(path, response.status_code, duration_ms)
    
    if path not in ("/health", "/metrics"):
        logger.info(
            "request_end",
            request_id=request_id,
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
    
    response.headers["X-Request-ID"] = request_id
    return response

# ============ MODELS ============
class BacktestRequest(BaseModel):
    strategy_key: str = "STRADDLE_SELL"
    symbol: str = "NIFTY"
    days: int = 180
    timeframe: str = "1d"
    initial_capital: float = 100000.0
    lot_size: int = 1
    sl_pct: float = 25.0
    tp_pct: float = 50.0
    max_positions: int = 1

class SignalRequest(BaseModel):
    strategy_key: str = "STRADDLE_SELL"
    symbol: str = "NIFTY"

# ============ MOCK POSITIONS (paper trading) ============
def _mock_positions() -> List[Dict]:
    """Generate realistic mock open positions for paper trading."""
    positions = []
    symbols = [("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("GOLD", "MCX"), ("NATURALGAS", "MCX")]
    strategies = ["STRADDLE_SELL", "STRANGLE_SELL", "IRON_CONDOR"]
    
    for i, (sym, exch) in enumerate(symbols[:3]):
        quote = get_live_quote(sym)
        cfg = INSTRUMENTS[sym]
        # Synthetic position
        side = random.choice(["LONG", "SHORT"])
        qty = cfg["lot_size"]
        avg_price = round(quote["ltp"] * random.uniform(0.005, 0.012), 2)
        ltp = round(avg_price * random.uniform(0.85, 1.15), 2)
        if side == "SHORT":
            unrealized = (avg_price - ltp) * qty
        else:
            unrealized = (ltp - avg_price) * qty
        positions.append({
            "id": f"POS-{i+1}",
            "instrument": sym,
            "exchange": exch,
            "strategy": strategies[i % len(strategies)],
            "side": side,
            "quantity": qty,
            "lot_size": cfg["lot_size"],
            "lots": 1,
            "avg_price": avg_price,
            "ltp": ltp,
            "stop_loss": round(avg_price * 1.30, 2),
            "target": round(avg_price * 0.50, 2),
            "unrealized_pnl": round(unrealized, 2),
            "unrealized_pnl_pct": round((unrealized / (avg_price * qty)) * 100, 2),
            "opened_at": (datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 5))).isoformat(),
            "status": "OPEN",
        })
    return positions


def _actual_positions() -> List[Dict]:
    """Return the authoritative paper-risk positions in dashboard shape."""
    result = []
    for pos in get_portfolio_engine().positions:
        cfg = INSTRUMENTS.get(pos.symbol, {})
        value = pos.entry_price * pos.quantity
        result.append({
            "id": pos.id, "instrument": pos.symbol, "exchange": cfg.get("exchange", ""),
            "strategy": pos.strategy, "side": pos.side, "quantity": pos.quantity,
            "lot_size": cfg.get("lot_size", pos.quantity), "lots": max(1, pos.quantity // max(1, cfg.get("lot_size", pos.quantity))),
            "avg_price": pos.entry_price, "ltp": pos.current_price, "stop_loss": pos.stop_loss,
            "target": pos.take_profit, "unrealized_pnl": pos.unrealized_pnl,
            "unrealized_pnl_pct": round(pos.unrealized_pnl / value * 100, 2) if value else 0,
            "opened_at": pos.opened_at, "status": "OPEN",
        })
    return result

# ============ ENDPOINTS ============
@app.get("/health")
def health():
    return {"status": "OK", "service": "trading-engine", "version": "1.0.0", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/instruments")
def list_instruments():
    """List all tradable instruments."""
    return [
        {
            "symbol": sym,
            "name": cfg["name"],
            "exchange": cfg["exchange"],
            "segment": cfg["segment"],
            "asset_class": cfg["asset_class"],
            "lot_size": cfg["lot_size"],
            "tick_size": cfg["tick_size"],
            "base_price": cfg["base_price"],
            "volatility": cfg["volatility"],
            "expiry_day": cfg["expiry_day"],
        }
        for sym, cfg in INSTRUMENTS.items()
    ]

@app.get("/api/quote/{symbol}")
def get_quote(symbol: str):
    try:
        return get_live_quote(symbol)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/option-chain/{symbol}")
def get_chain(symbol: str, n_strikes: int = Query(11, ge=5, le=25)):
    try:
        return get_option_chain(symbol, n_strikes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/strategies")
def list_strategies():
    """List all available strategies with their metadata."""
    return [
        {"key": k, **v}
        for k, v in STRATEGIES.items()
    ]

@app.get("/api/signals")
def get_signals(limit: int = Query(12, ge=1, le=50)):
    """Get latest signals feed across all strategies & symbols."""
    return generate_signals_feed(limit=limit)

@app.post("/api/signals/generate")
def create_signal(req: SignalRequest):
    """Generate a fresh signal for given strategy + symbol."""
    sig = generate_signal(req.strategy_key, req.symbol)
    if sig is None:
        raise HTTPException(status_code=400, detail=f"Invalid strategy/symbol: {req.strategy_key}/{req.symbol}")
    metrics.record_signal(req.strategy_key, req.symbol, sig.get("confidence", 0))
    logger.trade("signal_generated", strategy=req.strategy_key, symbol=req.symbol, confidence=sig.get("confidence"))
    return sig

@app.get("/api/positions")
def get_positions():
    """Get authoritative open paper-trading positions."""
    return _actual_positions()

@app.post("/api/backtest")
def run_bt(req: BacktestRequest):
    """Run a backtest with given parameters."""
    start_time = time.time()
    try:
        result = run_backtest(
            strategy_key=req.strategy_key,
            symbol=req.symbol,
            days=req.days,
            timeframe=req.timeframe,
            initial_capital=req.initial_capital,
            lot_size=req.lot_size,
            sl_pct=req.sl_pct,
            tp_pct=req.tp_pct,
            max_positions=req.max_positions,
        )
        # Record metrics
        duration_ms = (time.time() - start_time) * 1000
        sharpe = result.get("metrics", {}).get("sharpe", 0)
        metrics.record_backtest(req.strategy_key, req.symbol, duration_ms, sharpe)
        logger.info(
            "backtest_completed",
            strategy=req.strategy_key,
            symbol=req.symbol,
            days=req.days,
            duration_ms=round(duration_ms, 2),
            sharpe=sharpe,
            trades=result.get("metrics", {}).get("total_trades", 0),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("backtest_failed", strategy=req.strategy_key, symbol=req.symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")

@app.get("/api/dashboard")
def dashboard():
    """Aggregate dashboard data for the home page."""
    # Quotes for main instruments
    main_symbols = ["NIFTY", "BANKNIFTY", "GOLD", "NATURALGAS"]
    quotes = []
    for sym in main_symbols:
        try:
            q = get_live_quote(sym)
            quotes.append({
                "symbol": sym,
                "name": INSTRUMENTS[sym]["name"],
                "ltp": q["ltp"],
                "day_change_pct": q["day_change_pct"],
                "day_change": q["day_change"],
                "is_market_open": q["is_market_open"],
                "sparkline": q["sparkline"],
                "exchange": q["exchange"],
            })
        except Exception:
            pass
    
    # Latest signals
    signals = generate_signals_feed(limit=8)
    
    positions = _actual_positions()
    
    # Today P&L
    total_unrealized = sum(p["unrealized_pnl"] for p in positions)
    risk_status = get_portfolio_engine().status()
    total_realized = risk_status["pnl"]["realized_today"]
    today_pnl = total_unrealized + total_realized
    
    equity_curve = [{"date": datetime.now(timezone.utc).date().isoformat(), "value": risk_status["capital"]["current"]}]
    
    # Stats
    history = get_portfolio_engine().trade_history
    wins = sum(1 for trade in history if trade.get("pnl", 0) > 0)
    win_rate = (wins / len(history) * 100) if history else 0
    policy = load_policy()
    signals_are_actionable = policy.get("mode") != "RISK_OFF" and policy.get("approved_count", 0) > 0
    active_signals = len([s for s in signals if s.get("status") == "ACTIVE"]) if signals_are_actionable else 0
    
    return {
        "stats": {
            "today_pnl": round(today_pnl, 2),
            "today_pnl_pct": round((today_pnl / 100000) * 100, 2),
            "realized_pnl": round(total_realized, 2),
            "unrealized_pnl": round(total_unrealized, 2),
            "open_positions": len(positions),
            "active_signals": active_signals,
            "win_rate_30d": round(win_rate, 1),
            "total_trades_30d": len(history),
            "capital_used": risk_status["capital"]["used"],
            "capital_available": risk_status["capital"]["available"],
        },
        "quotes": quotes,
        "equity_curve": equity_curve,
        "signals": signals[:6],
        "signals_are_actionable": signals_are_actionable,
        "research_policy": {
            "mode": policy.get("mode", "RISK_OFF"),
            "paper_only": policy.get("paper_only", True),
            "data_source": policy.get("data_source", "UNKNOWN"),
            "evidence_grade": policy.get("evidence_grade", "UNKNOWN"),
            "live_eligible": policy.get("live_eligible", False),
            "live_execution_enabled": policy.get("live_execution_enabled", False),
            "research_active": policy.get("research_active", True),
            "paper_trading_active": policy.get("paper_trading_active", True),
            "approved_count": policy.get("approved_count", 0),
            "generated_at": policy.get("generated_at"),
        },
        "positions": positions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/brokers/status")
def brokers_status():
    """Get broker connection status — checks all 8 broker modules."""
    
    def _broker_status(broker_id, name, btype, broker_module, segments, default_msg):
        configured = broker_module.is_configured()
        test = broker_module.test_connection() if configured else None
        availability_names = {
            "zerodha": "KITE_AVAILABLE", "mt5": "MT5_AVAILABLE", "angel_one": "ANGEL_AVAILABLE",
            "fyers": "FYERS_AVAILABLE", "dhan": "DHAN_AVAILABLE", "upstox": "UPSTOX_AVAILABLE",
            "ibkr": "IBKR_AVAILABLE", "oanda": "OANDA_AVAILABLE",
        }
        pkg_installed = bool(getattr(broker_module, availability_names[broker_id], False))
        return {
            "id": broker_id,
            "name": name,
            "type": btype,
            "is_configured": configured,
            "is_connected": test.get("connected", False) if test else False,
            "package_installed": pkg_installed,
            "paper_mode": not configured,
            "segments": segments,
            "last_sync": datetime.now(timezone.utc).isoformat() if test and test.get("connected") else None,
            "message": test.get("message", default_msg) if test else default_msg,
            "user": test.get("user") if test else None,
            "balance": test.get("balance") if test else None,
            "currency": test.get("currency") if test else None,
        }
    
    brokers = [
        _broker_status("zerodha", "Zerodha Kite", "ZERODHA", zerodha_broker,
                       ["NSE", "FNO", "MCX", "CDS"], "API credentials required. Get from developers.kite.trade"),
        _broker_status("mt5", "MetaTrader 5", "MT5", mt5_broker,
                       ["FOREX", "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD"], "MT5 terminal required. Install MT5 + provide login credentials"),
        _broker_status("angel_one", "Angel One", "ANGEL", angel_broker,
                       ["NSE", "FNO", "MCX", "CDS"], "SmartAPI credentials required. Get from smartapi.angelbroking.com"),
        _broker_status("fyers", "Fyers", "FYERS", fyers_broker,
                       ["NSE", "FNO", "MCX"], "App ID + access token required. Get from myapi.fyers.in"),
        _broker_status("dhan", "Dhan", "DHAN", dhan_broker,
                       ["NSE", "FNO", "MCX", "CDS"], "Client ID + access token required. Get from dhanhq.co"),
        _broker_status("upstox", "Upstox", "UPSTOX", upstox_broker,
                       ["NSE", "FNO", "MCX"], "API key + access token required. Get from upstox.com/developer/api"),
        _broker_status("ibkr", "Interactive Brokers", "IBKR", ibkr_broker,
                       ["US_STOCKS", "US_OPTIONS", "FOREX", "FUTURES", "BONDS"], "TWS/IB Gateway required. Install + enable API"),
        _broker_status("oanda", "OANDA", "OANDA", oanda_broker,
                       ["FOREX", "XAUUSD", "XAGUSD", "INDICES", "COMMODITIES"], "API key + account ID required. Get from developer.oanda.com"),
    ]
    
    t_configured = telegram_bot.is_configured()
    
    return {
        "brokers": brokers,
        "telegram": {
            "is_configured": t_configured,
            "message": "Configured" if t_configured else "Bot token & chat ID required. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
        },
    }


# ============ BROKER TEST ENDPOINTS ============
class ZerodhaTestRequest(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None


class ZerodhaAuthStartRequest(BaseModel):
    api_key: str
    api_secret: str


class ZerodhaAuthCompleteRequest(BaseModel):
    request_token: str


@app.post("/api/brokers/zerodha/auth/start")
def start_zerodha_auth(req: ZerodhaAuthStartRequest):
    """Create the official Kite login URL; secrets remain in engine memory only."""
    try:
        return zerodha_broker.begin_auth(req.api_key, req.api_secret)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/brokers/zerodha/auth/complete")
def complete_zerodha_auth(req: ZerodhaAuthCompleteRequest):
    """Exchange Kite's one-time request token and verify the new session."""
    try:
        zerodha_broker.complete_auth(req.request_token)
        result = zerodha_broker.test_connection()
        return {
            "connected": result.get("connected", False),
            "message": result.get("message", ""),
            "user": result.get("user"),
            "storage": "PROCESS_MEMORY_ONLY",
        }
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Kite authentication failed: {exc}")


@app.post("/api/brokers/zerodha/test")
def test_zerodha(req: ZerodhaTestRequest):
    """Test Zerodha Kite connection with provided credentials."""
    # If credentials provided, set them temporarily
    if req.api_key:
        os.environ["KITE_API_KEY"] = req.api_key
    if req.api_secret:
        os.environ["KITE_API_SECRET"] = req.api_secret
    if req.access_token:
        os.environ["KITE_ACCESS_TOKEN"] = req.access_token
    
    # Reimport to pick up env vars
    import importlib
    importlib.reload(zerodha_broker)
    
    result = zerodha_broker.test_connection()
    return {
        "connected": result.get("connected", False),
        "message": result.get("message", ""),
        "user": result.get("user"),
        "email": result.get("email"),
        "broker": result.get("broker"),
        "exchanges": result.get("exchanges", []),
    }


class MT5TestRequest(BaseModel):
    login: Optional[str] = None
    password: Optional[str] = None
    server: Optional[str] = None


@app.post("/api/brokers/mt5/test")
def test_mt5(req: MT5TestRequest):
    """Test MetaTrader 5 connection with provided credentials."""
    if req.login:
        os.environ["MT5_LOGIN"] = req.login
    if req.password:
        os.environ["MT5_PASSWORD"] = req.password
    if req.server:
        os.environ["MT5_SERVER"] = req.server
    
    import importlib
    importlib.reload(mt5_broker)
    
    result = mt5_broker.test_connection()
    return {
        "connected": result.get("connected", False),
        "message": result.get("message", ""),
        "account": result.get("account"),
        "balance": result.get("balance"),
        "currency": result.get("currency"),
        "leverage": result.get("leverage"),
        "server": result.get("server"),
    }


# === New broker test endpoints ===
class GenericBrokerTestRequest(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    client_id: Optional[str] = None
    password: Optional[str] = None
    account_id: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None


@app.post("/api/brokers/angel_one/test")
def test_angel_one(req: GenericBrokerTestRequest):
    """Test Angel One SmartAPI connection."""
    if req.api_key: os.environ["ANGEL_API_KEY"] = req.api_key
    if req.client_id: os.environ["ANGEL_CLIENT_CODE"] = req.client_id
    if req.password: os.environ["ANGEL_PASSWORD"] = req.password
    if req.access_token: os.environ["ANGEL_ACCESS_TOKEN"] = req.access_token
    import importlib; importlib.reload(angel_broker)
    result = angel_broker.test_connection()
    return {"connected": result.get("connected", False), "message": result.get("message", "")}


@app.post("/api/brokers/fyers/test")
def test_fyers(req: GenericBrokerTestRequest):
    """Test Fyers API connection."""
    if req.api_key: os.environ["FYERS_APP_ID"] = req.api_key
    if req.api_secret: os.environ["FYERS_SECRET_ID"] = req.api_secret
    if req.access_token: os.environ["FYERS_ACCESS_TOKEN"] = req.access_token
    import importlib; importlib.reload(fyers_broker)
    result = fyers_broker.test_connection()
    return {"connected": result.get("connected", False), "message": result.get("message", "")}


@app.post("/api/brokers/dhan/test")
def test_dhan(req: GenericBrokerTestRequest):
    """Test Dhan API connection."""
    if req.client_id: os.environ["DHAN_CLIENT_ID"] = req.client_id
    if req.access_token: os.environ["DHAN_ACCESS_TOKEN"] = req.access_token
    import importlib; importlib.reload(dhan_broker)
    result = dhan_broker.test_connection()
    return {"connected": result.get("connected", False), "message": result.get("message", "")}


@app.post("/api/brokers/upstox/test")
def test_upstox(req: GenericBrokerTestRequest):
    """Test Upstox API connection."""
    if req.api_key: os.environ["UPSTOX_API_KEY"] = req.api_key
    if req.api_secret: os.environ["UPSTOX_API_SECRET"] = req.api_secret
    if req.access_token: os.environ["UPSTOX_ACCESS_TOKEN"] = req.access_token
    import importlib; importlib.reload(upstox_broker)
    result = upstox_broker.test_connection()
    return {"connected": result.get("connected", False), "message": result.get("message", "")}


@app.post("/api/brokers/ibkr/test")
def test_ibkr(req: GenericBrokerTestRequest):
    """Test Interactive Brokers connection."""
    if req.host: os.environ["IBKR_HOST"] = req.host
    if req.port: os.environ["IBKR_PORT"] = str(req.port)
    import importlib; importlib.reload(ibkr_broker)
    result = ibkr_broker.test_connection()
    return {"connected": result.get("connected", False), "message": result.get("message", "")}


@app.post("/api/brokers/oanda/test")
def test_oanda(req: GenericBrokerTestRequest):
    """Test OANDA REST API connection."""
    if req.api_key: os.environ["OANDA_API_KEY"] = req.api_key
    if req.account_id: os.environ["OANDA_ACCOUNT_ID"] = req.account_id
    import importlib; importlib.reload(oanda_broker)
    result = oanda_broker.test_connection()
    return {"connected": result.get("connected", False), "message": result.get("message", "")}


class TelegramTestRequest(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


@app.post("/api/brokers/telegram/test")
def test_telegram(req: TelegramTestRequest):
    """Test Telegram bot by sending a test message."""
    result = telegram_bot.test_connection(
        token=req.bot_token or None,
        chat_id=req.chat_id or None,
    )
    return {
        "ok": result.get("ok", False),
        "message": result.get("message", result.get("error", "")),
        "chat_id": result.get("chat_id"),
    }


class TelegramSendRequest(BaseModel):
    signal: Optional[Dict] = None
    message: Optional[str] = None
    alert_type: Optional[str] = None
    title: Optional[str] = None


@app.post("/api/brokers/telegram/send")
def send_telegram(req: TelegramSendRequest):
    """Send a signal alert or generic message to Telegram."""
    if req.signal:
        if req.signal.get("execution_eligible") is not True:
            raise HTTPException(status_code=409, detail="Only validated REAL_MARKET signals can be sent as trade alerts")
        result = telegram_bot.send_signal_alert(req.signal)
    elif req.message:
        result = telegram_bot.send_alert(
            title=req.title or "QuantPulse Alert",
            message=req.message,
            alert_type=req.alert_type or "INFO",
        )
    else:
        raise HTTPException(status_code=400, detail="Provide 'signal' or 'message'")
    return {
        "ok": result.get("ok", False),
        "message_id": result.get("result", {}).get("message_id") if result.get("ok") else None,
        "error": result.get("description", result.get("error")) if not result.get("ok") else None,
    }

# ============ RESEARCH DATA ============
RESEARCH_REPOS = [
    {"name": "jugaad-data", "url": "https://github.com/jugaad-py/jugaad-data", "stars": "500+", "lang": "Python", "license": "MIT", "description": "Community NSE/RBI historical downloader with caching and derivatives support. Useful as a free ingestion adapter, with monitoring for NSE website changes.", "best_for": "Free NSE archive ingestion", "rating": 4},
    {"name": "DuckDB", "url": "https://github.com/duckdb/duckdb", "stars": "Open source", "lang": "C++/Python", "license": "MIT", "description": "Embedded analytical database with native Parquet support. JARVIS uses it for normalized local candles and provenance.", "best_for": "Local market-data lake", "rating": 5},
    {"name": "OpenAlgo", "url": "https://github.com/marketcalls/openalgo", "stars": "3.5k", "lang": "Python", "license": "AGPL-3.0", "description": "Self-hosted unified API across 35+ Indian brokers. THE top pick for Indian algo trading.", "best_for": "Indian broker abstraction layer", "rating": 5},
    {"name": "zerodha/pykiteconnect", "url": "https://github.com/zerodha/pykiteconnect", "stars": "1.1k", "lang": "Python", "license": "MIT", "description": "Official Zerodha Kite Connect Python client. Foundational library for Kite API.", "best_for": "Zerodha API integration", "rating": 5},
    {"name": "NautilusTrader", "url": "https://github.com/nautechsystems/nautilustrader", "stars": "3.5k", "lang": "Rust/Python", "license": "LGPL-3.0", "description": "Rust-native multi-asset trading engine. Deterministic backtest→live parity. Supports options.", "best_for": "Production-grade multi-asset engine", "rating": 5},
    {"name": "Backtrader", "url": "https://github.com/mementum/backtrader", "stars": "22.9k", "lang": "Python", "license": "GPL", "description": "Most readable backtesting framework. Feature-rich, pure Python. Has Zerodha store adapter.", "best_for": "Backtesting with custom strategies", "rating": 5},
    {"name": "VectorBT", "url": "https://github.com/polakowo/vectorbt", "stars": "4.5k", "lang": "Python", "license": "Apache-2.0", "description": "Ultra-fast vectorized backtesting using NumPy. Test 1000s of parameter combos in seconds.", "best_for": "Parameter optimization", "rating": 4},
    {"name": "Freqtrade", "url": "https://github.com/freqtrade/freqtrade", "stars": "40k", "lang": "Python", "license": "GPL-3.0", "description": "Most popular open-source bot. Crypto only — NOT for Indian markets. Worth studying architecture.", "best_for": "Crypto only (architecture reference)", "rating": 4},
    {"name": "Jesse", "url": "https://github.com/jesse-ai/jesse", "stars": "8.4k", "lang": "Python", "license": "MIT", "description": "Fast backtesting framework with clean API. Focus on crypto/forex.", "best_for": "Forex/crypto backtesting", "rating": 4},
    {"name": "QuantConnect LEAN", "url": "https://github.com/QuantConnect/Lean", "stars": "9.5k", "lang": "C#", "license": "Apache-2.0", "description": "Institutional-grade engine. Excellent options support. Cloud or self-hosted.", "best_for": "Institutional options strategies", "rating": 5},
    {"name": "MetaTrader5 Python", "url": "https://pypi.org/project/MetaTrader5/", "stars": "Official", "lang": "Python", "license": "Free", "description": "Official MetaQuotes Python package. Windows-native. Required for MT5 forex integration.", "best_for": "MT5 forex integration", "rating": 5},
    {"name": "mibian", "url": "https://github.com/yassinemaaroufi/Mibian", "stars": "300+", "lang": "Python", "license": "MIT", "description": "De-facto Indian standard for Black-Scholes options Greeks calculation.", "best_for": "Options Greeks", "rating": 4},
    {"name": "buzzsubash/algo_trading_strategies_india", "url": "https://github.com/buzzsubash/algo_trading_strategies_india", "stars": "300-500", "lang": "Python", "license": "MIT", "description": "Ready-made NIFTY/BANKNIFTY option-selling strategies (straddle/strangle).", "best_for": "Pre-built options strategies", "rating": 4},
    {"name": "VarunS2002/NSE-Option-Chain-Analyzer", "url": "https://github.com/VarunS2002/NSE-Option-Chain-Analyzer", "stars": "400+", "lang": "Python", "license": "MIT", "description": "Real-time NSE option chain analysis with OI tracking.", "best_for": "OI analysis", "rating": 4},
]

@app.get("/api/research")
def research():
    """Get GitHub repos research summary."""
    return {
        "repos": RESEARCH_REPOS,
        "recommended_stack": {
            "execution": "OpenAlgo + pykiteconnect (Indian F&O + MCX)",
            "forex": "MetaTrader5 Python package (XAUUSD, EURUSD, GBPUSD)",
            "backtesting": "VectorBT for research + event-driven replay for final validation",
            "greeks": "mibian or custom Black-Scholes implementation",
            "ta_indicators": "TA-Lib + pandas-ta-classic (200+ indicators)",
            "data_feed": "NSE archives / Upstox or Kite candles -> normalized DuckDB + Parquet",
            "event_engine": "JARVIS ORB replay now; NautilusTrader as the scale-up path",
            "framework": "Next.js + FastAPI (this dashboard)",
        },
        "key_insights": [
            "No single GitHub repo covers all user needs (Zerodha + MT5 + options + backtest). Use a composable stack.",
            "SEBI's Aug 2025 + April 2026 retail algo framework requires static IPs, unique algo IDs, broker-approved APIs, kill switches, order rate limits.",
            "Realistic edge targets: 55-65% win rate with 1:1.5+ risk-reward. Anyone claiming 80%+ is curve-fitted or scam.",
            "Synthetic candles validate engineering only. Real normalized data plus forward paper fills are required for performance evidence.",
            "Theta decay strategies (straddle/strangle sell) win 60-70% but have tail risk. Always define max loss.",
            "Brokerage + STT + taxes in India: ~0.05-0.1% per options round-trip. Account for this in backtests.",
        ],
    }


# ============ JARVIS VALIDATION + REGIME ENDPOINTS ============
from validation import (
    run_full_validation, monte_carlo_trade_shuffle, red_team_audit,
    regime_performance_breakdown, classify_regime as classify_regime_simple,
)
from regime import classify_full_regime, route_strategies
from market_data import generate_history


class ValidationRequest(BaseModel):
    strategy_key: str = "STRADDLE_SELL"
    symbol: str = "NIFTY"
    days: int = 180
    timeframe: str = "1d"
    initial_capital: float = 100000.0
    lot_size: int = 1
    sl_pct: float = 25.0
    tp_pct: float = 50.0
    monte_carlo_runs: int = 500


@app.post("/api/validate")
def validate_strategy(req: ValidationRequest):
    """Run full JARVIS validation pipeline on a strategy.
    
    Pipeline: backtest → OOS split → walk-forward → Monte Carlo →
              regime breakdown → red-team audit → parameter sensitivity.
    
    Returns final verdict: PASSED / WARNING / REJECTED.
    """
    from backtest import run_backtest as bt_fn
    
    base_params = {
        "strategy_key": req.strategy_key,
        "symbol": req.symbol,
        "days": req.days,
        "timeframe": req.timeframe,
        "initial_capital": req.initial_capital,
        "lot_size": req.lot_size,
        "sl_pct": req.sl_pct,
        "tp_pct": req.tp_pct,
    }
    
    # Get historical bars for regime analysis
    bars = generate_history(req.symbol, days=req.days, timeframe=req.timeframe)
    
    result = run_full_validation(
        backtest_fn=bt_fn,
        base_params=base_params,
        bars=bars,
        monte_carlo_runs=req.monte_carlo_runs,
    )
    return result


@app.get("/api/regime/{symbol}")
def get_regime(symbol: str, lookback_days: int = Query(60, ge=30, le=365)):
    """Get current market regime classification for a symbol.
    
    Returns multi-dimensional regime state + strategy routing recommendation.
    """
    try:
        bars = generate_history(symbol, days=lookback_days, timeframe="1d")
        if not bars or len(bars) < 30:
            raise HTTPException(status_code=400, detail=f"Insufficient data for {symbol}")
        
        regime_state = classify_full_regime(bars)
        routing = route_strategies(regime_state)
        
        return {
            "symbol": symbol,
            "regime": regime_state.to_dict(),
            "routing": routing.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/regime")
def get_all_regimes():
    """Get regime classification for all main instruments."""
    symbols = ["NIFTY", "BANKNIFTY", "GOLD", "NATURALGAS", "EURUSD"]
    results = []
    for sym in symbols:
        try:
            bars = generate_history(sym, days=60, timeframe="1d")
            if bars and len(bars) >= 30:
                regime_state = classify_full_regime(bars)
                routing = route_strategies(regime_state)
                results.append({
                    "symbol": sym,
                    "regime": regime_state.to_dict(),
                    "routing": routing.to_dict(),
                })
        except Exception:
            pass
    return {"regimes": results}


@app.post("/api/red-team")
def red_team_check(req: BacktestRequest):
    """Run red-team bias detection on a backtest.
    
    Checks for: look-ahead bias, OOS degradation, win rate sanity,
    profit factor sanity, trade count adequacy, slippage modeling,
    Sharpe sanity, return/DD ratio.
    """
    result = run_backtest(
        strategy_key=req.strategy_key,
        symbol=req.symbol,
        days=req.days,
        timeframe=req.timeframe,
        initial_capital=req.initial_capital,
        lot_size=req.lot_size,
        sl_pct=req.sl_pct,
        tp_pct=req.tp_pct,
    )
    audit = red_team_audit(result)
    return {
        "strategy_key": req.strategy_key,
        "symbol": req.symbol,
        "backtest_metrics": result.get("metrics", {}),
        "red_team_audit": audit,
    }


@app.post("/api/monte-carlo")
def monte_carlo_test(req: BacktestRequest, n_runs: int = Query(500, ge=100, le=5000)):
    """Run Monte Carlo trade-shuffle analysis on a backtest.
    
    Reshuffles trade order n_runs times, returns percentile distribution
    of final capital, max drawdown, and Sharpe.
    """
    result = run_backtest(
        strategy_key=req.strategy_key,
        symbol=req.symbol,
        days=req.days,
        timeframe=req.timeframe,
        initial_capital=req.initial_capital,
        lot_size=req.lot_size,
        sl_pct=req.sl_pct,
        tp_pct=req.tp_pct,
    )
    trades = result.get("all_trades", result.get("trades", []))
    mc = monte_carlo_trade_shuffle(
        trades,
        initial_capital=req.initial_capital,
        n_runs=n_runs,
        seed=42,
    )
    return {
        "strategy_key": req.strategy_key,
        "symbol": req.symbol,
        "original_metrics": result.get("metrics", {}),
        "monte_carlo": mc,
    }


class WalkForwardRequest(BaseModel):
    strategy_key: str = "VRP_HARVEST"
    symbol: str = "NIFTY"
    days: int = 180
    param_name: str = "sl_pct"
    param_values: List[float] = [15, 20, 25, 30, 35]
    train_window: int = 90
    test_window: int = 30
    step: int = 30


@app.post("/api/walk-forward")
def walk_forward_test(req: WalkForwardRequest):
    """Run walk-forward optimization with parameter sweep.
    
    For each window: optimize param on train, test on OOS.
    Detects overfitting via OOS degradation.
    """
    from validation import walk_forward_optimize
    from backtest import run_backtest as bt_fn
    
    base_params = {
        "strategy_key": req.strategy_key,
        "symbol": req.symbol,
        "days": req.days,
        "initial_capital": 100000,
    }
    
    bars = generate_history(req.symbol, days=req.days, timeframe="1d")
    
    result = walk_forward_optimize(
        backtest_fn=bt_fn,
        base_params=base_params,
        bars=bars,
        param_name=req.param_name,
        param_values=req.param_values,
        train_window=req.train_window,
        test_window=req.test_window,
        step=req.step,
    )
    return result


class PortfolioBacktestRequest(BaseModel):
    strategies: List[Dict]
    days: int = 180
    initial_capital: float = 100000.0


@app.post("/api/portfolio-backtest")
def portfolio_backtest_endpoint(req: PortfolioBacktestRequest):
    """Run multi-asset portfolio backtest with correlation analysis.
    
    Tests multiple strategies across multiple assets, computes correlation matrix,
    and diversification ratio.
    """
    from validation import portfolio_backtest
    from backtest import run_backtest as bt_fn
    
    result = portfolio_backtest(
        backtest_fn=bt_fn,
        strategies=req.strategies,
        days=req.days,
        initial_capital=req.initial_capital,
    )
    return result


# ============ JARVIS OBSERVABILITY ============
@app.get("/api/jarvis/health")
def jarvis_health():
    """JARVIS deep health check — system, brokers, data freshness, risk state."""
    import os, time, psutil
    
    # System
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
    except Exception:
        cpu = mem = disk = 0
    
    # Process info
    try:
        proc = psutil.Process()
        uptime_sec = time.time() - proc.create_time()
        threads = proc.num_threads()
    except Exception:
        uptime_sec = 0
        threads = 0
    
    # Brokers
    from brokers import zerodha as z, mt5 as m, telegram_bot as t
    broker_health = {
        "zerodha": {
            "package_installed": z.KITE_AVAILABLE,
            "configured": z.is_configured(),
        },
        "mt5": {
            "package_installed": m.MT5_AVAILABLE,
            "configured": m.is_configured(),
        },
        "telegram": {
            "configured": t.is_configured(),
        },
    }
    
    # Engine version
    engine_version = "JARVIS-v2"
    
    # Test inventory is discovered from source; passing count comes only from a
    # verified local test-run artifact and is never hard-coded.
    tests_root = Path(__file__).parent / "tests"
    tests_total = sum(
        1 for path in tests_root.glob("test_*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("def test_")
    )
    test_info = {"tests_passing": 0, "tests_total": tests_total, "last_run": None}
    try:
        verified = __import__("json").loads((Path(__file__).parent / "data" / "test-status.json").read_text(encoding="utf-8"))
        if int(verified.get("tests_total", -1)) == tests_total:
            test_info = {"tests_passing": int(verified.get("tests_passing", 0)),
                         "tests_total": tests_total, "last_run": verified.get("last_run")}
    except (FileNotFoundError, OSError, ValueError, TypeError):
        pass
    
    return {
        "status": "OK" if cpu < 90 and mem < 90 else "DEGRADED",
        "engine_version": engine_version,
        "uptime_seconds": round(uptime_sec, 0),
        "system": {
            "cpu_pct": round(cpu, 1),
            "memory_pct": round(mem, 1),
            "disk_pct": round(disk, 1),
            "threads": threads,
        },
        "brokers": broker_health,
        "tests": test_info,
        "features": {
            "look_ahead_bias_fixed": True,
            "slippage_modeled": True,
            "black_scholes_revaluation": True,
            "mark_to_market": True,
            "monte_carlo": True,
            "walk_forward": True,
            "regime_classification": True,
            "red_team_audit": True,
            "strategy_routing": True,
            "kill_switch": True,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/jarvis/observability")
def jarvis_observability():
    """JARVIS unified observability dashboard data.
    
    Combines: system health, market regime, portfolio, strategies, risk.
    """
    # System
    health = jarvis_health()
    
    # Market regimes for all instruments
    regimes_resp = get_all_regimes()
    
    actual_risk = get_portfolio_engine().status()
    portfolio = {
        "total_capital": actual_risk["capital"]["current"],
        "available_capital": actual_risk["capital"]["available"],
        "used_capital": actual_risk["capital"]["used"],
        "open_positions": actual_risk["exposure"]["positions"],
        "today_pnl": actual_risk["pnl"]["total"],
        "today_pnl_pct": round(actual_risk["pnl"]["total"] / actual_risk["capital"]["initial"] * 100, 2),
        "unrealized_pnl": actual_risk["pnl"]["unrealized"],
        "net_delta": actual_risk["greeks"]["net_delta"],
        "net_theta": actual_risk["greeks"]["net_theta"],
        "gross_exposure": actual_risk["exposure"]["gross"],
        "net_exposure": actual_risk["exposure"]["net"],
    }
    
    # Strategies status
    strategies_status = []
    for key, strat in STRATEGIES.items():
        strategies_status.append({
            "key": key,
            "name": strat["name"],
            "type": strat["type"],
            "status": "ACTIVE" if key in ("STRADDLE_SELL", "STRANGLE_SELL") else "PAUSED",
            "mode": "PAPER",
            "last_signal": None,
            "win_rate_30d": None,
            "sharpe_30d": None,
        })
    
    # Risk state
    risk = {
        "kill_switch_active": actual_risk["limits"]["kill_switch"],
        "max_daily_loss_pct": 3.0,
        "max_daily_loss_amount": 3000,
        "today_loss_so_far": abs(min(portfolio["today_pnl"], 0)),
        "distance_to_kill_switch": max(0, 3000 - abs(min(portfolio["today_pnl"], 0))),
        "max_open_positions": actual_risk["limits"]["max_positions"],
        "current_open_positions": portfolio["open_positions"],
        "position_sizing_pct": 2.0,
        "alerts": [],
    }
    if risk["today_loss_so_far"] > risk["max_daily_loss_amount"] * 0.7:
        risk["alerts"].append({
            "level": "WARNING",
            "message": f"Approaching daily loss limit: ₹{risk['today_loss_so_far']:.0f} / ₹{risk['max_daily_loss_amount']}",
        })
    
    return {
        "system": health,
        "market": regimes_resp,
        "portfolio": portfolio,
        "strategies": strategies_status,
        "risk": risk,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============ PROMETHEUS METRICS ============
@app.get("/metrics")
def prometheus_metrics():
    """Prometheus-compatible metrics endpoint.
    
    Exposes: http_requests_total, http_request_duration_ms,
             signals_generated_total, trades_total, backtests_total, etc.
    """
    return PlainTextResponse(metrics.to_prometheus(), media_type="text/plain")


@app.get("/api/jarvis/metrics")
def jarvis_metrics_json():
    """JSON-formatted metrics (for dashboard consumption)."""
    return metrics.to_dict()


# ============ PORTFOLIO RISK ENDPOINTS ============
@app.get("/api/jarvis/risk")
def jarvis_risk_status():
    """Get full portfolio risk status — positions, Greeks, exposure, alerts, limits.
    
    This is the primary risk monitoring endpoint. Check this before any live trade.
    """
    engine = get_portfolio_engine()
    return engine.status()


@app.get("/api/jarvis/risk/positions")
def jarvis_risk_positions():
    """Get just the open positions with their Greeks."""
    engine = get_portfolio_engine()
    return {"positions": [p.to_dict() for p in engine.positions], "count": len(engine.positions)}


@app.get("/api/jarvis/risk/liquidation-distance/{symbol}")
def jarvis_liquidation_distance(symbol: str):
    """Compute how far spot can move before each position's SL is hit.
    
    Returns per-position: stop_loss, current_spot, distance, distance_pct, alert.
    """
    engine = get_portfolio_engine()
    try:
        quote = get_live_quote(symbol)
        return engine.liquidation_distance(symbol, quote["ltp"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class KillSwitchRequest(BaseModel):
    reason: str
    confirm: bool = False


@app.post("/api/jarvis/kill-switch")
def jarvis_activate_kill_switch(req: KillSwitchRequest):
    """Activate kill switch — blocks ALL new trades immediately.
    
    ⚠️  This is a CIRCUIT BREAKER. Use only when:
    - System malfunction suspected
    - Unexpected large loss
    - Market crash / black swan event
    - Manual intervention required
    
    Requires confirmation flag to prevent accidental activation.
    """
    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Kill switch requires confirm=true to prevent accidental activation."
        )
    engine = get_portfolio_engine()
    result = engine.activate_kill_switch(req.reason)
    logger.critical("KILL_SWITCH_ACTIVATED", reason=req.reason)
    metrics.inc_counter("kill_switch_activations_total", reason=req.reason)
    return result


@app.delete("/api/jarvis/kill-switch")
def jarvis_deactivate_kill_switch():
    """Deactivate kill switch.
    
    ⚠️  Requires human approval in production. This endpoint should be
    protected by additional authentication in a real deployment.
    """
    engine = get_portfolio_engine()
    result = engine.deactivate_kill_switch()
    logger.warning("KILL_SWITCH_DEACTIVATED")
    return result


@app.post("/api/jarvis/risk/check-trade")
def jarvis_check_trade_eligibility(req: Dict):
    """Pre-trade risk check. Returns whether a proposed trade would pass all risk gates.
    
    Does NOT place the trade — just validates it would be allowed.
    Use this before placing live orders.
    """
    from risk_engine import Position
    engine = get_portfolio_engine()
    try:
        pos = Position(
            id="CHECK",
            symbol=req.get("symbol", ""),
            strategy=req.get("strategy", ""),
            side=req.get("side", "LONG"),
            quantity=req.get("quantity", 1),
            entry_price=req.get("entry_price", 0),
            current_price=req.get("entry_price", 0),
            spot=req.get("spot", 0),
            strike=req.get("strike", 0),
            option_type=req.get("option_type", "CE"),
            delta=req.get("delta", 0),
            gamma=req.get("gamma", 0),
            theta=req.get("theta", 0),
            vega=req.get("vega", 0),
            stop_loss=req.get("stop_loss", 0),
            take_profit=req.get("take_profit", 0),
        )
        checks = engine._pre_trade_checks(pos)
        return {
            "would_pass": all(passed for passed, _ in checks.values()),
            "checks": {name: {"passed": passed, "reason": reason} for name, (passed, reason) in checks.items()},
        }
    except Exception as e:
        return {"would_pass": False, "error": str(e)}


# ============ PAPER TRADING EXECUTION ENDPOINTS ============
class ExecuteSignalRequest(BaseModel):
    strategy_key: str
    symbol: str


class TradingModeRequest(BaseModel):
    mode: str
    broker: str = ""
    confirmation: str = ""


class LiveOrderRequest(BaseModel):
    confirmation: str
    legs: List[Dict]
    risk: Dict


@app.get("/api/trading/mode")
def trading_mode_status():
    return get_trading_mode().status()


@app.post("/api/trading/mode")
def set_trading_mode(req: TradingModeRequest):
    manager = get_trading_mode()
    if req.mode.upper() == "PAPER":
        return manager.set_paper()
    if req.mode.upper() != "LIVE":
        raise HTTPException(status_code=400, detail="Mode must be PAPER or LIVE")
    broker = req.broker.upper()
    module = {"ZERODHA": zerodha_broker, "FYERS": fyers_broker}.get(broker)
    if module is None:
        raise HTTPException(status_code=400, detail="Unsupported live broker")
    connection = module.test_connection()
    try:
        return manager.set_live(broker, req.confirmation, bool(connection.get("connected")))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except (ValueError, ConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/trading/live/orders")
def place_guarded_live_orders(req: LiveOrderRequest):
    if req.confirmation != "PLACE LIVE ORDERS":
        raise HTTPException(status_code=400, detail="Live order confirmation must exactly match: PLACE LIVE ORDERS")
    result = execute_live_legs(req.legs, req.risk)
    if not result.get("accepted"):
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/jarvis/execute-signal")
def execute_signal(req: ExecuteSignalRequest):
    """Generate a signal AND execute it as a paper trade.
    
    Full flow: signal → risk check → position open (if approved).
    Returns position_id if accepted, reason if rejected.
    """
    # Generate signal
    signal = generate_signal(req.strategy_key, req.symbol)
    if signal is None:
        raise HTTPException(status_code=400, detail=f"Invalid strategy/symbol: {req.strategy_key}/{req.symbol}")
    
    # Execute via paper trading engine
    engine = get_execution_engine()
    result = engine.process_signal(signal)
    
    return {
        "signal": {
            "strategy": signal["strategy_name"],
            "symbol": signal["symbol"],
            "confidence": signal["confidence"],
            "entry_price": signal["entry_price"],
            "stop_loss": signal["stop_loss"],
            "target": signal["target"],
        },
        "execution": result,
    }


@app.post("/api/jarvis/execute-raw-signal")
def execute_raw_signal(signal: Dict):
    """Execute a pre-built signal dict as a paper trade.
    
    Use this when you have a signal from external source (e.g., /api/signals/generate).
    """
    engine = get_execution_engine()
    result = engine.process_signal(signal)
    return result


class ClosePositionRequest(BaseModel):
    position_id: str
    exit_price: Optional[float] = None
    reason: str = "MANUAL"


@app.post("/api/jarvis/close-position")
def close_position(req: ClosePositionRequest):
    """Close a paper trading position manually."""
    engine = get_execution_engine()
    result = engine.close_position(req.position_id, req.exit_price, req.reason)
    return result


@app.post("/api/jarvis/monitor-positions")
def monitor_positions_now():
    """Run SL/TP monitor check immediately (don't wait for background loop)."""
    engine = get_execution_engine()
    closed = engine.monitor_positions()
    return {
        "checked": len(engine.risk_engine.positions),
        "closed": len(closed),
        "closed_positions": closed,
    }


@app.post("/api/jarvis/monitoring/start")
def start_monitoring(interval_seconds: int = Query(5, ge=1, le=60)):
    """Start background SL/TP monitoring thread."""
    engine = get_execution_engine()
    started = engine.start_monitoring(interval_seconds)
    return {"started": started, "interval_seconds": interval_seconds}


@app.post("/api/jarvis/monitoring/stop")
def stop_monitoring():
    """Stop background monitoring."""
    engine = get_execution_engine()
    stopped = engine.stop_monitoring()
    return {"stopped": stopped}


@app.get("/api/jarvis/execution-status")
def execution_status():
    """Get execution engine status."""
    engine = get_execution_engine()
    return engine.status()


# ============ AUTO-TRADING BOT ENDPOINTS ============
@app.get("/api/jarvis/auto-bot/status")
def auto_bot_status():
    """Get auto-trading bot status."""
    bot = get_auto_bot()
    return bot.status()


class AutoBotConfigRequest(BaseModel):
    symbols: Optional[List[str]] = None
    min_confidence: Optional[float] = None
    max_trades_per_day: Optional[int] = None
    scan_interval_seconds: Optional[int] = None
    send_telegram_alerts: Optional[bool] = None
    strategy_blacklist: Optional[List[str]] = None


@app.post("/api/jarvis/auto-bot/configure")
def auto_bot_configure(req: AutoBotConfigRequest):
    """Configure auto-trading bot parameters (doesn't start it)."""
    bot = get_auto_bot()
    if req.symbols is not None:
        bot.config.symbols = req.symbols
    if req.min_confidence is not None:
        bot.config.min_confidence = req.min_confidence
    if req.max_trades_per_day is not None:
        bot.config.max_trades_per_day = req.max_trades_per_day
    if req.scan_interval_seconds is not None:
        bot.config.scan_interval_seconds = req.scan_interval_seconds
    if req.send_telegram_alerts is not None:
        bot.config.send_telegram_alerts = req.send_telegram_alerts
    if req.strategy_blacklist is not None:
        bot.config.strategy_blacklist = set(req.strategy_blacklist)
    return {"success": True, "config": bot.status()}


@app.post("/api/jarvis/auto-bot/start")
def auto_bot_start():
    """Start auto-trading bot.
    
    ⚠️ This enables autonomous trading. Bot will:
    - Scan every 30s for signals
    - Execute paper trades when regime is favorable + confidence > 65
    - Respect kill switch + daily loss limit + max positions
    - Send Telegram alerts on each execution
    
    Bot runs in PAPER mode only. Live mode requires human approval.
    """
    bot = get_auto_bot()
    result = bot.enable()
    logger.critical("AUTO_BOT_ENABLED", started=result.get("started"))
    metrics.inc_counter("auto_bot_enable_requests_total")
    return result


@app.post("/api/jarvis/auto-bot/stop")
def auto_bot_stop():
    """Stop auto-trading bot."""
    bot = get_auto_bot()
    result = bot.disable()
    logger.warning("AUTO_BOT_DISABLED")
    return result


# ============ AUTONOMY SUPERVISOR ENDPOINTS ============
class AutonomyConfigRequest(BaseModel):
    heartbeat_seconds: Optional[int] = None
    max_quote_age_seconds: Optional[int] = None
    max_spread_pct: Optional[float] = None
    risk_per_trade_pct: Optional[float] = None
    max_hold_minutes: Optional[int] = None
    trailing_trigger_pct: Optional[float] = None
    trailing_lock_pct: Optional[float] = None
    min_promotion_trades: Optional[int] = None
    min_win_rate: Optional[float] = None
    min_profit_factor: Optional[float] = None
    max_promotion_drawdown_pct: Optional[float] = None
    auto_recover: Optional[bool] = None
    reconcile_enabled: Optional[bool] = None
    daily_workflow_enabled: Optional[bool] = None


class PaperResetRequest(BaseModel):
    confirmation: str
    initial_capital: float = 100000


class ResearchRunRequest(BaseModel):
    symbols: Optional[List[str]] = None
    strategies: Optional[List[str]] = None
    days: int = 730


class MarketDataImportRequest(BaseModel):
    path: str
    source: str = "NSE_ARCHIVE"
    symbol: str
    exchange: str = "NSE"
    timeframe: str = "1d"
    instrument_token: str = ""


def resolve_market_import_path(raw_path: str) -> Path:
    """Resolve CSV imports only inside the operator-controlled import directory."""
    market_root = Path(os.getenv("MARKET_DATA_DIR") or Path(__file__).parent / "data" / "market")
    configured_root = os.getenv("MARKET_DATA_IMPORT_DIR") or str(market_root / "imports")
    root = Path(configured_root).expanduser().resolve()
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(f"CSV must be inside the configured import directory: {root}")
    return candidate


class ORBBacktestRequest(BaseModel):
    symbol: str
    source: Optional[str] = None
    initial_capital: float = 100000
    config: Optional[Dict] = None


class NSEIndexDownloadRequest(BaseModel):
    symbol: str = "NIFTY"
    from_date: str = "2021-01-01"
    to_date: Optional[str] = None


class BrokerCandleDownloadRequest(BaseModel):
    broker: str
    symbol: str
    broker_instrument: str
    from_date: str
    to_date: Optional[str] = None
    timeframe: str = "5m"
    exchange: str = "NSE"


class FuturesResearchRequest(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    min_volume: int = 10000
    min_open_interest: int = 5000
    max_symbols: int = 50


class KiteORBRnDRequest(BaseModel):
    days: int = 120
    initial_capital: float = 100000


@app.get("/api/jarvis/autonomy/status")
def autonomy_status():
    return get_autonomy_supervisor().status()


@app.post("/api/jarvis/autonomy/configure")
def autonomy_configure(req: AutonomyConfigRequest):
    return get_autonomy_supervisor().configure(req.model_dump(exclude_none=True))


@app.post("/api/jarvis/autonomy/start")
def autonomy_start():
    """Start full unattended PAPER operations; never activates LIVE mode."""
    mode = get_trading_mode().status()
    if mode["mode"] != "PAPER":
        raise HTTPException(status_code=409, detail="Autonomy is PAPER-only; switch to PAPER first")
    supervisor = get_autonomy_supervisor()
    result = supervisor.start()
    get_execution_engine().start_monitoring(5)
    bot = get_auto_bot()
    bot.config.enabled = True
    bot.start()
    return {**result, "bot": bot.status(), "execution": get_execution_engine().status()}


@app.post("/api/jarvis/autonomy/stop")
def autonomy_stop():
    get_auto_bot().disable()
    return get_autonomy_supervisor().stop()


@app.post("/api/jarvis/autonomy/cycle")
def autonomy_cycle():
    return get_autonomy_supervisor().run_cycle()


@app.get("/api/jarvis/autonomy/decisions")
def autonomy_decisions(limit: int = Query(100, ge=1, le=1000)):
    return {"items": get_autonomy_supervisor().decisions(limit), "limit": limit}


@app.get("/api/jarvis/autonomy/promotion")
def autonomy_promotion():
    return get_autonomy_supervisor().promotion_status()


@app.post("/api/jarvis/autonomy/reconcile")
def autonomy_reconcile():
    return get_autonomy_supervisor().reconcile()


@app.post("/api/jarvis/autonomy/daily-report")
def autonomy_daily_report():
    return get_autonomy_supervisor().generate_daily_report()


@app.post("/api/jarvis/paper/reset")
def reset_paper_trading(req: PaperResetRequest):
    """Destructively reset simulated positions, P&L, counters, and journal."""
    if req.confirmation != "RESET PAPER ACCOUNT":
        raise HTTPException(status_code=400, detail="Exact confirmation phrase required")
    if get_trading_mode().status()["mode"] != "PAPER":
        raise HTTPException(status_code=409, detail="Paper reset is unavailable in LIVE mode")
    get_auto_bot().disable()
    result = get_portfolio_engine().reset_paper_account(req.initial_capital)
    cleared = get_journal().clear()
    get_auto_bot().reset_session_stats()
    get_autonomy_supervisor().record_decision("PAPER_ACCOUNT_RESET", "PORTFOLIO",
                                              "User-authorized research reset",
                                              {"capital": req.initial_capital, "journal_trades_cleared": cleared})
    return {**result, "journal_trades_cleared": cleared}


@app.get("/api/jarvis/research-policy")
def research_policy_status():
    return load_policy()


@app.post("/api/jarvis/research-policy/run")
def research_policy_run(req: ResearchRunRequest):
    unknown_symbols = set(req.symbols or []) - set(INSTRUMENTS)
    unknown_strategies = set(req.strategies or []) - set(STRATEGIES)
    if unknown_symbols or unknown_strategies:
        raise HTTPException(status_code=400, detail={"unknown_symbols": sorted(unknown_symbols),
                                                     "unknown_strategies": sorted(unknown_strategies)})
    if not 365 <= req.days <= 1825:
        raise HTTPException(status_code=400, detail="Research window must be 365-1825 days")
    output = Path(__file__).parent / "data" / "research-policy.json"
    return run_research(req.symbols, req.strategies, req.days, output)


def _kite_client_or_409():
    if not zerodha_broker.is_configured():
        raise HTTPException(
            status_code=409,
            detail="Kite Connect is not configured in the engine. Set API key, secret, and today's access token.",
        )
    client = zerodha_broker.get_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Kite Connect client could not be initialized")
    return client


@app.get("/api/jarvis/futures/universe")
def futures_universe():
    """Current nearest-expiry NSE single-stock futures from Kite's instrument master."""
    client = _kite_client_or_409()
    try:
        contracts = near_month_stock_futures(client.instruments("NFO"))
        return {"source": "KITE", "paper_only": True, "count": len(contracts), "contracts": contracts}
    except Exception as exc:
        logger.error("futures_universe_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Kite instrument download failed: {exc}")


@app.get("/api/jarvis/futures/research/latest")
def futures_research_latest():
    target = Path(__file__).parent / "data" / "futures-research.json"
    if not target.is_file():
        return {"status": "NOT_RUN", "paper_only": True, "live_eligible": False}
    return __import__("json").loads(target.read_text(encoding="utf-8"))


@app.post("/api/jarvis/futures/research/run")
def futures_research_run(req: FuturesResearchRequest):
    """Run liquidity-gated ORB research across current NSE stock futures."""
    from datetime import date as date_type
    client = _kite_client_or_409()
    try:
        end = date_type.fromisoformat(req.to_date) if req.to_date else datetime.now(ZoneInfo("Asia/Kolkata")).date()
        start = date_type.fromisoformat(req.from_date) if req.from_date else end - timedelta(days=120)
        if start > end or (end - start).days > 180:
            raise ValueError("Futures intraday research window must be 1-180 days")
        if not 1 <= req.max_symbols <= 200:
            raise ValueError("max_symbols must be 1-200")
        if req.min_volume < 0 or req.min_open_interest < 0:
            raise ValueError("Liquidity thresholds cannot be negative")
        instruments = client.instruments("NFO")
        output = Path(__file__).parent / "data" / "futures-research.json"
        return run_futures_orb_batch(
            client, instruments, start, end, req.min_volume,
            req.min_open_interest, req.max_symbols, output,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("futures_research_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Futures research failed: {exc}")


# ============ NORMALIZED MARKET DATA + EVENT BACKTEST ============
@app.get("/api/jarvis/data/catalog")
def market_data_catalog():
    store = get_market_data_store()
    return {"items": store.catalog(), "database": str(store.path)}


@app.get("/api/jarvis/data/quality/{symbol}")
def market_data_quality(symbol: str, timeframe: str = Query("1d"), source: Optional[str] = Query(None)):
    return get_market_data_store().quality(symbol, timeframe, source)


@app.post("/api/jarvis/data/import-csv")
def market_data_import_csv(req: MarketDataImportRequest):
    try:
        path = resolve_market_import_path(req.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not path.is_file() or path.suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="A readable local CSV file is required")
    return get_market_data_store().import_csv(path, req.source, req.symbol, req.exchange,
                                              req.timeframe, req.instrument_token)


@app.post("/api/jarvis/data/export-parquet")
def market_data_export_parquet():
    return get_market_data_store().export_parquet()


@app.post("/api/jarvis/data/download-nse-index")
def market_data_download_nse_index(req: NSEIndexDownloadRequest):
    from datetime import date as date_type
    try:
        start = date_type.fromisoformat(req.from_date)
        end = date_type.fromisoformat(req.to_date) if req.to_date else datetime.now(ZoneInfo("Asia/Kolkata")).date()
        return download_nse_index(req.symbol, start, end)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/jarvis/data/download-broker-candles")
def market_data_download_broker_candles(req: BrokerCandleDownloadRequest):
    """Import authenticated candles; credentials are read only from server env."""
    from datetime import date as date_type
    try:
        start = date_type.fromisoformat(req.from_date)
        end = date_type.fromisoformat(req.to_date) if req.to_date else datetime.now(ZoneInfo("Asia/Kolkata")).date()
        return download_broker_candles(req.broker, req.symbol, req.broker_instrument,
                                       start, end, req.timeframe, req.exchange)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/jarvis/backtest/orb")
def orb_backtest_endpoint(req: ORBBacktestRequest):
    if req.symbol not in INSTRUMENTS:
        raise HTTPException(status_code=400, detail="Unknown instrument")
    store = get_market_data_store()
    quality = store.quality(req.symbol, "5m", req.source)
    if quality["status"] != "PASS":
        raise HTTPException(status_code=422, detail={"message": "Five-minute data failed quality gate", "quality": quality})
    bars = store.bars(req.symbol, "5m", req.source)
    try:
        config = ORBConfig(**(req.config or {}))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid ORB configuration: {exc}")
    cfg = INSTRUMENTS[req.symbol]
    return run_orb_backtest(bars, req.symbol, cfg["lot_size"], cfg["tick_size"], req.initial_capital, config)


@app.post("/api/jarvis/rnd/kite-nifty-orb")
def kite_nifty_orb_rnd(req: KiteORBRnDRequest):
    """One-click authenticated NIFTY 5m ingestion, quality gate, and paper ORB backtest."""
    if not zerodha_broker.is_configured():
        raise HTTPException(status_code=409, detail="Connect today's Kite session in Brokers first")
    try:
        return run_nifty_orb_pipeline(req.days, req.initial_capital)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.error("kite_nifty_orb_pipeline_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Kite R&D pipeline failed: {exc}")


# ============ TRADE JOURNAL ENDPOINTS ============
@app.get("/api/jarvis/journal")
def journal_analyze():
    """Get full trade journal analysis (post-trade learning loop)."""
    journal = get_journal()
    return journal.analyze()


@app.get("/api/jarvis/journal/trades")
def journal_trades(limit: int = Query(50, ge=1, le=500)):
    """Get recent trades from journal."""
    journal = get_journal()
    return {"trades": journal.get_recent_trades(limit), "count": len(journal.get_all_trades())}


@app.delete("/api/jarvis/journal")
def journal_clear():
    """Clear all trades from journal."""
    journal = get_journal()
    count = journal.clear()
    return {"cleared": count}


# ============ STRATEGY LEADERBOARD ============
@app.get("/api/jarvis/leaderboard")
def strategy_leaderboard(symbol: str = Query("NIFTY"), days: int = Query(180, ge=30, le=365)):
    """Rank all strategies by performance metrics.
    
    Runs a quick backtest for each strategy and ranks by Sharpe, return, win rate.
    """
    results = []
    for key, strat in STRATEGIES.items():
        try:
            r = run_backtest(strategy_key=key, symbol=symbol, days=days)
            m = r.get("metrics", {})
            results.append({
                "strategy_key": key,
                "strategy_name": strat["name"],
                "type": strat["type"],
                "sharpe": m.get("sharpe", 0),
                "total_return_pct": m.get("total_return_pct", 0),
                "win_rate": m.get("win_rate", 0),
                "profit_factor": m.get("profit_factor", 0),
                "max_drawdown_pct": m.get("max_drawdown_pct", 0),
                "total_trades": m.get("total_trades", 0),
                "expectancy": m.get("expectancy", 0),
                "typical_win_rate": strat["typical_win_rate"],
            })
        except Exception as e:
            results.append({
                "strategy_key": key,
                "strategy_name": strat["name"],
                "error": str(e),
            })

    # Sort by Sharpe descending
    valid = [r for r in results if "error" not in r]
    errored = [r for r in results if "error" in r]
    valid.sort(key=lambda x: x.get("sharpe", 0), reverse=True)

    # Assign ranks
    for i, r in enumerate(valid, 1):
        r["rank"] = i

    return {
        "symbol": symbol,
        "days": days,
        "rankings": valid,
        "errors": errored,
        "best_strategy": valid[0] if valid else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ============ BACKTEST COMPARISON ============
class CompareRequest(BaseModel):
    strategies: List[Dict]  # [{strategy_key, symbol, label}]
    days: int = 180


@app.post("/api/jarvis/compare")
def compare_strategies(req: CompareRequest):
    """Compare multiple strategies side by side.
    
    Runs backtest for each and returns comparison table.
    """
    results = []
    for s in req.strategies:
        strat_key = s.get("strategy_key", "STRADDLE_SELL")
        symbol = s.get("symbol", "NIFTY")
        label = s.get("label", f"{strat_key}_{symbol}")
        try:
            r = run_backtest(strategy_key=strat_key, symbol=symbol, days=req.days)
            m = r.get("metrics", {})
            results.append({
                "label": label,
                "strategy_key": strat_key,
                "symbol": symbol,
                "metrics": m,
                "equity_curve": r.get("equity_curve", [])[-20:],  # last 20 points for chart
            })
        except Exception as e:
            results.append({"label": label, "error": str(e)})

    # Find best by each metric
    valid = [r for r in results if "metrics" in r]
    best = {}
    if valid:
        best["by_sharpe"] = max(valid, key=lambda x: x["metrics"].get("sharpe", 0))["label"]
        best["by_return"] = max(valid, key=lambda x: x["metrics"].get("total_return_pct", 0))["label"]
        best["by_win_rate"] = max(valid, key=lambda x: x["metrics"].get("win_rate", 0))["label"]
        best["by_lowest_dd"] = min(valid, key=lambda x: x["metrics"].get("max_drawdown_pct", 999))["label"]

    return {
        "days": req.days,
        "comparisons": results,
        "best": best,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ============ CSV EXPORT ============
@app.get("/api/jarvis/export/trades")
def export_trades_csv():
    """Export all trades as CSV."""
    from fastapi.responses import PlainTextResponse
    journal = get_journal()
    trades = journal.get_all_trades()
    
    if not trades:
        return PlainTextResponse("No trades to export", media_type="text/plain")
    
    headers = ["position_id", "symbol", "strategy", "side", "entry_price", "exit_price",
               "quantity", "pnl", "pnl_pct", "exit_reason", "entry_time", "exit_time",
               "hold_minutes", "is_win"]
    lines = [",".join(headers)]
    for t in trades:
        row = []
        for h in headers:
            val = t.get(h, "")
            if isinstance(val, bool):
                val = "true" if val else "false"
            row.append(str(val))
        lines.append(",".join(row))
    
    return PlainTextResponse("\n".join(lines), media_type="text/csv",
                            headers={"Content-Disposition": "attachment; filename=trades.csv"})


@app.post("/api/jarvis/export/backtest")
def export_backtest_csv(req: BacktestRequest):
    """Export backtest trades + equity curve as CSV."""
    from fastapi.responses import PlainTextResponse
    result = run_backtest(
        strategy_key=req.strategy_key,
        symbol=req.symbol,
        days=req.days,
        timeframe=req.timeframe,
        initial_capital=req.initial_capital,
        lot_size=req.lot_size,
        sl_pct=req.sl_pct,
        tp_pct=req.tp_pct,
    )
    
    lines = []
    # Trades section
    lines.append("# TRADES")
    lines.append("entry_time,exit_time,side,entry_price,exit_price,qty,pnl,pnl_pct,exit_reason,duration_bars")
    for t in result.get("trades", []):
        lines.append(f"{t.get('entry_time','')},{t.get('exit_time','')},{t.get('side','')},"
                    f"{t.get('entry_price',0)},{t.get('exit_price',0)},{t.get('qty',0)},"
                    f"{t.get('pnl',0)},{t.get('pnl_pct',0)},{t.get('exit_reason','')},{t.get('duration_bars',0)}")
    
    lines.append("")
    # Equity curve section
    lines.append("# EQUITY CURVE")
    lines.append("date,value")
    for point in result.get("equity_curve", []):
        lines.append(f"{point.get('date','')},{point.get('value',0)}")
    
    lines.append("")
    # Metrics section
    lines.append("# METRICS")
    m = result.get("metrics", {})
    for k, v in m.items():
        lines.append(f"{k},{v}")
    
    filename = f"backtest_{req.strategy_key}_{req.symbol}_{req.days}d.csv"
    return PlainTextResponse("\n".join(lines), media_type="text/csv",
                            headers={"Content-Disposition": f"attachment; filename={filename}"})


# ============ JARVIS FULL AUTONOMOUS ANALYSIS ============
@app.post("/api/jarvis/full-analysis")
def jarvis_full_analysis():
    """JARVIS runs the COMPLETE analysis pipeline autonomously.
    
    This is the one-click "do everything" endpoint:
      1. Classify market regime for all instruments
      2. Run strategy leaderboard (all 10 strategies ranked)
      3. Run validation pipeline on top 3 strategies
      4. Run Monte Carlo on top strategy
      5. Determine which strategies are safe to trade per regime
      6. Generate final recommendation: TRADE / NO TRADE / WAIT
    
    Returns a single unified results object for the JARVIS Results dashboard.
    """
    from validation import run_full_validation, monte_carlo_trade_shuffle, red_team_audit
    from regime import classify_full_regime, route_strategies
    from backtest import run_backtest as bt_fn
    import time as _time
    
    start = _time.time()
    results = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": "JARVIS-v2.3",
        "phases": {},
    }
    
    # === PHASE 1: Market Regime Classification (all instruments) ===
    regimes = []
    for sym in ["NIFTY", "BANKNIFTY", "GOLD", "NATURALGAS", "EURUSD"]:
        try:
            bars = generate_history(sym, days=60, timeframe="1d")
            if bars and len(bars) >= 30:
                rs = classify_full_regime(bars)
                routing = route_strategies(rs)
                regimes.append({
                    "symbol": sym,
                    "composite_regime": rs.composite_regime,
                    "confidence": rs.confidence,
                    "trend": rs.trend_regime,
                    "volatility": rs.volatility_regime,
                    "risk": rs.risk_regime,
                    "should_trade": routing.should_trade,
                    "recommended": routing.recommended_strategies,
                    "avoid": routing.avoid_strategies,
                    "reason": routing.reason,
                })
        except Exception:
            pass
    results["phases"]["regime"] = {"instruments": regimes, "count": len(regimes)}
    
    # === PHASE 2: Strategy Leaderboard (rank all 10 strategies) ===
    leaderboard = []
    for key, strat in STRATEGIES.items():
        try:
            r = bt_fn(strategy_key=key, symbol="NIFTY", days=90)
            m = r.get("metrics", {})
            leaderboard.append({
                "rank": 0,
                "strategy_key": key,
                "strategy_name": strat["name"],
                "type": strat["type"],
                "sharpe": m.get("sharpe", 0),
                "return_pct": m.get("total_return_pct", 0),
                "win_rate": m.get("win_rate", 0),
                "profit_factor": m.get("profit_factor", 0),
                "max_dd_pct": m.get("max_drawdown_pct", 0),
                "trades": m.get("total_trades", 0),
                "expectancy": m.get("expectancy", 0),
            })
        except Exception:
            pass
    leaderboard.sort(key=lambda x: x.get("sharpe", 0), reverse=True)
    for i, entry in enumerate(leaderboard, 1):
        entry["rank"] = i
    results["phases"]["leaderboard"] = {"strategies": leaderboard, "count": len(leaderboard)}
    
    # === PHASE 3: Validation Pipeline on top 3 strategies ===
    top_3 = leaderboard[:3]
    validations = []
    for entry in top_3:
        try:
            r = bt_fn(strategy_key=entry["strategy_key"], symbol="NIFTY", days=180)
            trades = r.get("all_trades", r.get("trades", []))
            mc = monte_carlo_trade_shuffle(trades, 100000, n_runs=200, seed=42)
            rt = red_team_audit(r)
            validations.append({
                "strategy_key": entry["strategy_key"],
                "strategy_name": entry["strategy_name"],
                "rank": entry["rank"],
                "in_sample": {
                    "return_pct": r.get("metrics", {}).get("total_return_pct", 0),
                    "sharpe": r.get("metrics", {}).get("sharpe", 0),
                    "win_rate": r.get("metrics", {}).get("win_rate", 0),
                    "max_dd_pct": r.get("metrics", {}).get("max_drawdown_pct", 0),
                    "trades": r.get("metrics", {}).get("total_trades", 0),
                },
                "monte_carlo": {
                    "prob_profit": mc.get("probability_of_profit", 0) if mc.get("status") == "COMPLETED" else 0,
                    "prob_ruin": mc.get("probability_of_ruin_20pct", 0) if mc.get("status") == "COMPLETED" else 0,
                    "sharpe_p5": mc.get("sharpe", {}).get("p5", 0) if mc.get("status") == "COMPLETED" else 0,
                    "sharpe_p50": mc.get("sharpe", {}).get("p50", 0) if mc.get("status") == "COMPLETED" else 0,
                },
                "red_team": {
                    "verdict": rt.get("verdict", "UNKNOWN"),
                    "critical_failures": rt.get("critical_failures", 0),
                    "warnings": rt.get("warnings", 0),
                    "checks": [{"name": c["name"], "passed": c["passed"], "severity": c["severity"]} for c in rt.get("checks", [])],
                },
                "final_verdict": _compute_final_verdict(rt, mc),
            })
        except Exception as e:
            validations.append({"strategy_key": entry["strategy_key"], "error": str(e)})
    results["phases"]["validation"] = {"results": validations, "count": len(validations)}
    
    # === PHASE 4: Trade Recommendations ===
    recommendations = []
    for regime in regimes:
        if not regime["should_trade"]:
            recommendations.append({
                "symbol": regime["symbol"],
                "action": "NO_TRADE",
                "reason": f"Regime: {regime['composite_regime']} — {regime['reason']}",
            })
            continue
        # Find best strategy for this symbol's regime
        best_for_regime = None
        for rec_strat in regime["recommended"]:
            # Find in leaderboard
            lb_entry = next((l for l in leaderboard if l["strategy_key"] == rec_strat), None)
            if lb_entry and lb_entry["sharpe"] > 0:
                best_for_regime = lb_entry
                break
        if best_for_regime:
            recommendations.append({
                "symbol": regime["symbol"],
                "action": "TRADE",
                "strategy": best_for_regime["strategy_key"],
                "strategy_name": best_for_regime["strategy_name"],
                "sharpe": best_for_regime["sharpe"],
                "win_rate": best_for_regime["win_rate"],
                "regime": regime["composite_regime"],
                "confidence": regime["confidence"],
                "reason": f"Regime {regime['composite_regime']} favors {best_for_regime['strategy_name']} (Sharpe {best_for_regime['sharpe']})",
            })
        else:
            recommendations.append({
                "symbol": regime["symbol"],
                "action": "WAIT",
                "reason": f"Regime OK but no recommended strategy has positive Sharpe",
            })
    results["phases"]["recommendations"] = {"items": recommendations, "count": len(recommendations)}
    
    # === PHASE 5: Summary ===
    trade_count = sum(1 for r in recommendations if r["action"] == "TRADE")
    no_trade_count = sum(1 for r in recommendations if r["action"] == "NO_TRADE")
    wait_count = sum(1 for r in recommendations if r["action"] == "WAIT")
    
    best_strategy = leaderboard[0] if leaderboard else None
    best_validation = validations[0] if validations else None
    
    results["summary"] = {
        "total_duration_seconds": round(_time.time() - start, 2),
        "regimes_analyzed": len(regimes),
        "strategies_tested": len(leaderboard),
        "strategies_validated": len(validations),
        "trade_recommendations": trade_count,
        "no_trade_recommendations": no_trade_count,
        "wait_recommendations": wait_count,
        "best_strategy": {
            "name": best_strategy["strategy_name"] if best_strategy else "N/A",
            "sharpe": best_strategy["sharpe"] if best_strategy else 0,
            "rank": 1,
        } if best_strategy else None,
        "best_validation_verdict": best_validation.get("final_verdict", "N/A") if best_validation else "N/A",
        "overall_recommendation": _overall_recommendation(trade_count, no_trade_count, wait_count),
        "jarvis_status": "ANALYSIS COMPLETE",
    }
    
    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    return results


def _compute_final_verdict(red_team: Dict, monte_carlo: Dict) -> str:
    """Compute final verdict from red-team + Monte Carlo results."""
    rt_verdict = red_team.get("verdict", "UNKNOWN")
    mc_status = monte_carlo.get("status", "")
    mc_p5_sharpe = monte_carlo.get("sharpe", {}).get("p5", 0) if isinstance(monte_carlo.get("sharpe"), dict) else 0
    prob_ruin = monte_carlo.get("probability_of_ruin_20pct", 100) if mc_status == "COMPLETED" else 100
    
    if rt_verdict == "REJECTED":
        return "REJECTED — Red-team fail"
    if mc_status != "COMPLETED":
        return "REJECTED — Insufficient data"
    if mc_p5_sharpe <= 0:
        return "REJECTED — MC p5 Sharpe ≤ 0"
    if prob_ruin > 20:
        return "WARNING — High ruin probability"
    return "PASSED — Eligible for paper trading"


def _overall_recommendation(trade: int, no_trade: int, wait: int) -> str:
    """JARVIS's overall recommendation based on all analyses."""
    total = trade + no_trade + wait
    if total == 0:
        return "NO_DATA"
    if no_trade >= total * 0.6:
        return "RISK_OFF — Live execution disabled. Strategy R&D and paper testing remain active."
    if trade >= total * 0.5:
        return "TRADE — Favorable conditions. Execute recommended strategies with paper mode."
    if wait >= total * 0.4:
        return "WAIT — Mixed signals. Wait for clearer regime."
    return "CAUTION — Limited edge. Small positions only if any."


# ============ STARTUP ============
if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  JARVIS Trading Engine API (v2)")
    print("  Port: 3030")
    print("  Endpoints:")
    print("    /health, /api/instruments, /api/quote/{symbol}")
    print("    /api/option-chain/{symbol}, /api/strategies")
    print("    /api/signals, /api/signals/generate")
    print("    /api/positions, /api/backtest, /api/dashboard")
    print("    /api/brokers/status, /api/brokers/{zerodha,mt5,telegram}/test")
    print("    /api/validate, /api/red-team, /api/monte-carlo  [JARVIS]")
    print("    /api/regime, /api/regime/{symbol}                [JARVIS]")
    print("    /api/jarvis/health, /api/jarvis/observability    [JARVIS]")
    print("    /api/jarvis/risk, /api/jarvis/kill-switch        [JARVIS]")
    print("    /metrics                                          [Prometheus]")
    print("=" * 60)
    uvicorn.run(
        app,
        host=os.getenv("ENGINE_HOST", "127.0.0.1"),
        port=int(os.getenv("ENGINE_PORT", "3030")),
        log_level=os.getenv("LOG_LEVEL", "info"),
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )
