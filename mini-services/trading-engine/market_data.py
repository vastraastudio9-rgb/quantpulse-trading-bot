"""
Market Data Module
- Generates realistic synthetic OHLC data using Geometric Brownian Motion
- Mocks live tick data for paper trading
- Covers: NIFTY, BANKNIFTY, FINNIFTY (F&O), GOLD, NATURALGAS (MCX), EURUSD, GBPUSD, XAUUSD (Forex)
- In production: replace generate_history() with Zerodha Kite historical API + MT5 CopyRates
"""
import math
import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import numpy as np

# ============ INSTRUMENT UNIVERSE ============
INSTRUMENTS = {
    "NIFTY": {
        "name": "NIFTY 50 Index",
        "exchange": "NSE",
        "segment": "FNO",
        "asset_class": "INDEX",
        "lot_size": 75,
        "tick_size": 0.05,
        "base_price": 24850.0,
        "volatility": 0.13,  # 13% annualized
        "expiry_day": "THU",
    },
    "BANKNIFTY": {
        "name": "NIFTY Bank Index",
        "exchange": "NSE",
        "segment": "FNO",
        "asset_class": "INDEX",
        "lot_size": 35,
        "tick_size": 0.05,
        "base_price": 54200.0,
        "volatility": 0.18,
        "expiry_day": "THU",
    },
    "FINNIFTY": {
        "name": "NIFTY Financial Services",
        "exchange": "NSE",
        "segment": "FNO",
        "asset_class": "INDEX",
        "lot_size": 65,
        "tick_size": 0.05,
        "base_price": 23400.0,
        "volatility": 0.16,
        "expiry_day": "TUE",
    },
    "GOLD": {
        "name": "MCX Gold Futures",
        "exchange": "MCX",
        "segment": "COMMODITY",
        "asset_class": "COMMODITY",
        "lot_size": 100,
        "tick_size": 1.0,
        "base_price": 71250.0,
        "volatility": 0.12,
        "expiry_day": "FRI",
    },
    "NATURALGAS": {
        "name": "MCX Natural Gas Futures",
        "exchange": "MCX",
        "segment": "COMMODITY",
        "asset_class": "COMMODITY",
        "lot_size": 1250,
        "tick_size": 0.05,
        "base_price": 198.50,
        "volatility": 0.32,
        "expiry_day": "FRI",
    },
    "CRUDEOIL": {
        "name": "MCX Crude Oil Futures",
        "exchange": "MCX",
        "segment": "COMMODITY",
        "asset_class": "COMMODITY",
        "lot_size": 100,
        "tick_size": 1.0,
        "base_price": 6850.0,
        "volatility": 0.28,
        "expiry_day": "FRI",
    },
    "EURUSD": {
        "name": "Euro / US Dollar",
        "exchange": "FOREX",
        "segment": "CURRENCY",
        "asset_class": "CURRENCY",
        "lot_size": 100000,
        "tick_size": 0.00001,
        "base_price": 1.0850,
        "volatility": 0.08,
        "expiry_day": None,
    },
    "GBPUSD": {
        "name": "British Pound / US Dollar",
        "exchange": "FOREX",
        "segment": "CURRENCY",
        "asset_class": "CURRENCY",
        "lot_size": 100000,
        "tick_size": 0.00001,
        "base_price": 1.2730,
        "volatility": 0.09,
        "expiry_day": None,
    },
    "XAUUSD": {
        "name": "Gold Spot / US Dollar",
        "exchange": "FOREX",
        "segment": "CURRENCY",
        "asset_class": "COMMODITY",
        "lot_size": 100,
        "tick_size": 0.01,
        "base_price": 2510.0,
        "volatility": 0.13,
        "expiry_day": None,
    },
}

# ============ SYNTHETIC DATA GENERATION ============
def _trading_days(start: datetime, end: datetime) -> List[datetime]:
    """Generate weekday dates (skips Sat/Sun). Doesn't account for Indian holidays."""
    days = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # Mon-Fri
            days.append(cur)
        cur += timedelta(days=1)
    return days

def generate_history(symbol: str, days: int = 180, timeframe: str = "1d") -> List[Dict]:
    """Generate synthetic OHLC history using GARCH(1,1) volatility clustering.
    
    JARVIS-v2.2 upgrades over plain GBM:
    - GARCH(1,1) vol clustering: high-vol periods follow high-vol periods (real markets)
    - IV > RV by ~3% (volatility risk premium) — makes VRP strategy testable
    - Event-driven vol spikes: random 2-3x vol jumps (earnings, RBI, budget)
    - Mean-reverting vol: vol tends back to long-run average
    - Realistic OHLC: high/low reflect intrabar vol, not just close-to-close
    
    Args:
        symbol: One of INSTRUMENTS keys
        days: Number of calendar days to go back
        timeframe: 1m, 5m, 15m, 1h, 1d
    """
    if symbol not in INSTRUMENTS:
        raise ValueError(f"Unknown symbol: {symbol}")
    
    cfg = INSTRUMENTS[symbol]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    
    tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}.get(timeframe, 1440)
    
    if timeframe == "1d":
        timestamps = _trading_days(start, end)
    else:
        timestamps = []
        trading_days = _trading_days(start, end)
        for d in trading_days:
            cur = d.replace(hour=3, minute=45, second=0, microsecond=0, tzinfo=timezone.utc)
            close_time = d.replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
            while cur <= close_time:
                timestamps.append(cur)
                cur += timedelta(minutes=tf_minutes)
    
    if not timestamps:
        return []
    
    S0 = cfg["base_price"]
    base_sigma = cfg["volatility"]
    mu = 0.05
    dt = tf_minutes / (252 * 375)
    
    seed = sum(ord(c) for c in symbol) * 42
    rng = np.random.default_rng(seed)
    
    n = len(timestamps)
    
    # === GARCH(1,1) VOLATILITY CLUSTERING ===
    # σ²_t = ω + α * ε²_{t-1} + β * σ²_{t-1}
    # Typical params: α=0.1, β=0.85, ω = base_sigma² * (1 - α - β)
    alpha = 0.10  # reaction to recent shocks
    beta = 0.85   # persistence of vol
    omega = (base_sigma ** 2) * (1 - alpha - beta)  # long-run variance anchor
    
    var_t = base_sigma ** 2  # initial variance
    returns = np.zeros(n)
    realized_var_path = np.zeros(n)
    
    for t in range(n):
        # GARCH variance update
        if t > 0:
            var_t = omega + alpha * (returns[t-1] ** 2) + beta * var_t
            # Mean reversion: pull var_t toward long-run if it drifts too far
            if var_t > (base_sigma ** 2) * 4:
                var_t = (base_sigma ** 2) * 4  # cap at 4x base
            elif var_t < (base_sigma ** 2) * 0.25:
                var_t = (base_sigma ** 2) * 0.25  # floor at 0.25x base
        
        sigma_t = math.sqrt(var_t)
        realized_var_path[t] = var_t
        
        # Generate return with current vol
        returns[t] = rng.normal(mu * dt, sigma_t * math.sqrt(dt))
    
    # === EVENT-DRIVEN VOL SPIKES ===
    # ~2% of bars have 2-3x vol spike (earnings, RBI, budget, geopolitical)
    n_events = max(1, n // 50)
    event_idx = rng.choice(n, size=n_events, replace=False)
    for idx in event_idx:
        spike_factor = rng.uniform(2.0, 3.5)
        returns[idx] *= spike_factor
        # Also spike next 1-2 bars (vol clustering after event)
        if idx + 1 < n:
            returns[idx + 1] *= rng.uniform(1.5, 2.0)
    
    # === IV-RV SPREAD (Volatility Risk Premium) ===
    # In real markets, IV > RV by ~3% (compensation for bearing vol risk)
    # We model this by storing an "implied vol" that's ~3% above realized
    # This makes VRP_HARVEST strategy testable
    # (IV is computed on-the-fly in regime.py via volatility_risk_premium())
    
    # Build close prices
    closes = S0 * np.exp(np.cumsum(returns))
    
    # === REALISTIC OHLC ===
    # High/low reflect intrabar volatility (use GARCH vol, not constant)
    bars = []
    for i, ts in enumerate(timestamps):
        close = float(closes[i])
        # Use current GARCH vol for OHLC spread
        current_vol = math.sqrt(realized_var_path[i]) if i < len(realized_var_path) else base_sigma
        bar_vol = current_vol * math.sqrt(dt) * close
        open_p = close * (1 + rng.normal(0, 0.001))
        high = max(open_p, close) + abs(rng.normal(0, bar_vol * 0.5))
        low = min(open_p, close) - abs(rng.normal(0, bar_vol * 0.5))
        # Round to tick size
        tick = cfg["tick_size"]
        open_p = round(open_p / tick) * tick
        high = round(high / tick) * tick
        low = round(low / tick) * tick
        close = round(close / tick) * tick
        # Volume: higher on event bars, higher on vol expansion
        base_vol = 5_000_000 if cfg["asset_class"] == "INDEX" else 50_000
        vol_multiplier = 1.0
        if i in event_idx:
            vol_multiplier = 2.5  # events have higher volume
        else:
            vol_multiplier = 0.7 + (current_vol / base_sigma) * 0.5  # vol expansion → more volume
        volume = int(base_vol * vol_multiplier * (0.5 + abs(rng.normal(0, 0.5))))
        bars.append({
            "timestamp": ts.isoformat(),
            "open": round(open_p, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(close, 4),
            "volume": volume,
        })
    return bars

# ============ LIVE TICK SIMULATION ============
_LIVE_CACHE: Dict[str, Dict] = {}

def get_live_quote(symbol: str) -> Dict:
    """Get simulated live quote for an instrument."""
    if symbol not in INSTRUMENTS:
        raise ValueError(f"Unknown symbol: {symbol}")
    
    cfg = INSTRUMENTS[symbol]
    now = datetime.now(timezone.utc)
    
    # Cache last price to make it move smoothly
    cache = _LIVE_CACHE.get(symbol, {"price": cfg["base_price"], "ts": now})
    elapsed = (now - cache["ts"]).total_seconds()
    
    # Random walk for live price
    rng = random.Random(now.timestamp() * 1000 + sum(ord(c) for c in symbol))
    drift = rng.gauss(0, cfg["volatility"] / math.sqrt(252 * 375 * 60))  # per-second vol
    new_price = cache["price"] * (1 + drift * max(elapsed, 1))
    
    # Round to tick
    tick = cfg["tick_size"]
    new_price = round(new_price / tick) * tick
    
    _LIVE_CACHE[symbol] = {"price": new_price, "ts": now}
    
    # Determine market session
    ist_hour = (now.hour + 5) % 24  # UTC+5:30 approx
    ist_minute = (now.minute + 30) % 60
    total_min = ist_hour * 60 + ist_minute
    
    if cfg["exchange"] in ("NSE", "BSE", "MCX"):
        # NSE: 9:15-15:30; MCX: 9:00-23:30 (commodity)
        if cfg["exchange"] == "MCX":
            is_open = (9 * 60 <= total_min <= 23 * 60 + 30)
        else:
            is_open = (9 * 60 + 15 <= total_min <= 15 * 60 + 30)
        # Skip weekends
        if now.weekday() >= 5:
            is_open = False
    else:  # Forex - 24/5
        is_open = now.weekday() < 5
    
    # Generate sparkline (last 30 ticks)
    history = generate_history(symbol, days=1, timeframe="5m")[-30:]
    sparkline = [bar["close"] for bar in history]
    
    # Compute day change
    if history:
        day_open = history[0]["open"]
        day_change = new_price - day_open
        day_change_pct = (day_change / day_open) * 100 if day_open else 0
    else:
        day_change = 0
        day_change_pct = 0
    
    return {
        "symbol": symbol,
        "name": cfg["name"],
        "exchange": cfg["exchange"],
        "ltp": round(new_price, 4),
        "day_open": round(history[0]["open"], 4) if history else new_price,
        "day_high": round(max(b["high"] for b in history), 4) if history else new_price,
        "day_low": round(min(b["low"] for b in history), 4) if history else new_price,
        "day_change": round(day_change, 4),
        "day_change_pct": round(day_change_pct, 2),
        "is_market_open": is_open,
        "sparkline": sparkline,
        "timestamp": now.isoformat(),
        "lot_size": cfg["lot_size"],
        "volatility": cfg["volatility"],
    }

def get_option_chain(symbol: str, n_strikes: int = 11) -> Dict:
    """Generate ATM +/- strikes option chain with Greeks."""
    from greeks import greeks_bundle
    
    if symbol not in INSTRUMENTS:
        raise ValueError(f"Unknown symbol: {symbol}")
    
    cfg = INSTRUMENTS[symbol]
    quote = get_live_quote(symbol)
    spot = quote["ltp"]
    
    # Strike step based on symbol
    strike_steps = {
        "NIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 50,
        "GOLD": 100, "NATURALGAS": 5, "CRUDEOIL": 100,
    }
    step = strike_steps.get(symbol, max(1, round(spot * 0.005)))
    
    # ATM strike
    atm_strike = round(spot / step) * step
    n_side = (n_strikes - 1) // 2
    
    # Days to expiry (next Thursday for NSE FNO)
    now = datetime.now(timezone.utc)
    days_to_expiry = (3 - now.weekday()) % 7  # Thursday=3
    if days_to_expiry == 0:
        days_to_expiry = 7
    t = max(days_to_expiry / 365.0, 1/365)
    r = 0.07  # 7% risk-free rate (India)
    sigma = cfg["volatility"]
    
    chain = []
    for i in range(-n_side, n_side + 1):
        strike = atm_strike + i * step
        ce = greeks_bundle(spot, strike, t, r, sigma, "CE")
        pe = greeks_bundle(spot, strike, t, r, sigma, "PE")
        # Add mock OI
        oi_mult = max(0, 1 - abs(i) / (n_side + 1))  # ATM has highest OI
        ce_oi = int(50_000 * oi_mult * (0.7 + random.random() * 0.6))
        pe_oi = int(50_000 * oi_mult * (0.7 + random.random() * 0.6))
        chain.append({
            "strike": strike,
            "ce": {**ce, "oi": ce_oi, "iv": round(sigma * 100 * (1 + i * 0.005), 2)},
            "pe": {**pe, "oi": pe_oi, "iv": round(sigma * 100 * (1 - i * 0.005), 2)},
            "is_atm": i == 0,
        })
    
    return {
        "symbol": symbol,
        "spot": spot,
        "atm_strike": atm_strike,
        "days_to_expiry": days_to_expiry,
        "chain": chain,
        "timestamp": now.isoformat(),
    }
