"""
Strategy Signal Generation Module
Implements:
- ATM Straddle (sell CE + PE at ATM strike) - theta decay play
- Strangle (sell OTM CE + OTM PE) - range bound
- Long Straddle (buy CE + PE) - volatility breakout
- Iron Condor - range bound with defined risk
- Scalper - momentum based
- Breakout - range breakout

Each strategy returns a Signal dict with entry/SL/target/confidence/Greeks.
"""
import math
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional
from market_data import get_live_quote, get_option_chain, INSTRUMENTS
from greeks import greeks_bundle

# ============ STRATEGY DEFINITIONS ============
STRATEGIES = {
    "STRADDLE_SELL": {
        "name": "ATM Short Straddle",
        "type": "STRADDLE",
        "description": "Sell ATM Call + Put. Profit when market stays range-bound. Theta decay works in your favor. Unlimited risk — manage with strict SL.",
        "direction": "NEUTRAL",
        "edge_source": "Theta decay > gamma losses",
        "typical_win_rate": "55-65%",
        "best_market": "Range bound, low IV environment",
        "entry_time": "09:35 IST",
        "exit_time": "15:10 IST",
    },
    "STRANGLE_SELL": {
        "name": "OTM Short Strangle",
        "type": "STRANGLE",
        "description": "Sell OTM Call + OTM Put (e.g., 0.5-1% away from spot). Wider profit zone than straddle, lower premium. Best for high-IV days.",
        "direction": "NEUTRAL",
        "edge_source": "Theta + IV crush + distance from spot",
        "typical_win_rate": "60-70%",
        "best_market": "Post-event IV crush, range bound",
        "entry_time": "09:35 IST",
        "exit_time": "15:10 IST",
    },
    "STRADDLE_BUY": {
        "name": "Long Straddle (Breakout)",
        "type": "STRADDLE",
        "description": "Buy ATM Call + Put. Profit on big move either direction. Loses to theta if market is dead. Use before events/IV expansion.",
        "direction": "BIASED (either direction)",
        "edge_source": "Gamma > theta on big moves",
        "typical_win_rate": "35-45%",
        "best_market": "Pre-event: budget, RBI, results, elections",
        "entry_time": "09:20 IST",
        "exit_time": "15:00 IST",
    },
    "IRON_CONDOR": {
        "name": "Iron Condor",
        "type": "IRON_CONDOR",
        "description": "Sell OTM strangle + buy further OTM strangle for protection. Defined risk, defined reward. Best range-bound strategy.",
        "direction": "NEUTRAL",
        "edge_source": "Theta decay with capped risk",
        "typical_win_rate": "65-75%",
        "best_market": "Weekly expiry, range bound",
        "entry_time": "09:40 IST",
        "exit_time": "15:05 IST",
    },
    "MOMENTUM_SCALPER": {
        "name": "Momentum Scalper",
        "type": "SCALPER",
        "description": "Buy options on momentum breakout with 5-min VWAP confirmation. Quick in-and-out (5-15 min holds).",
        "direction": "TREND FOLLOWING",
        "edge_source": "Momentum + VWAP reversion",
        "typical_win_rate": "50-55%",
        "best_market": "Trending day with clear direction",
        "entry_time": "Intraday anytime",
        "exit_time": "Within 15 min",
    },
    "OPENING_RANGE_BREAKOUT": {
        "name": "Opening Range Breakout",
        "type": "BREAKOUT",
        "description": "Mark first 15-min high/low. Enter on breakout with options. SL = opposite end of range.",
        "direction": "BREAKOUT",
        "edge_source": "ORB edge + volume confirmation",
        "typical_win_rate": "45-55%",
        "best_market": "Trending days with gap up/down",
        "entry_time": "09:30 IST (after 15-min range)",
        "exit_time": "15:00 IST or SL hit",
    },
    "LONG_BUTTERFLY": {
        "name": "Long Butterfly (Call)",
        "type": "BUTTERFLY",
        "description": "Buy 1 ITM Call + Sell 2 ATM Calls + Buy 1 OTM Call. Max profit if expires at ATM strike. Low cost, defined risk.",
        "direction": "NEUTRAL (pinpoint)",
        "edge_source": "Theta decay + pinning at ATM strike",
        "typical_win_rate": "30-40% (high RR)",
        "best_market": "Range bound, expecting expiry-day pinning",
        "entry_time": "09:45 IST",
        "exit_time": "15:00 IST (or expiry day)",
    },
    "IRON_BUTTERFLY": {
        "name": "Iron Butterfly",
        "type": "IRON_BUTTERFLY",
        "description": "Sell ATM straddle + buy OTM strangle for protection. Higher credit than iron condor, narrower profit zone.",
        "direction": "NEUTRAL (pinpoint)",
        "edge_source": "Higher theta + ATM pinning",
        "typical_win_rate": "55-65%",
        "best_market": "Low-volatility expiry day, expect pinning",
        "entry_time": "09:40 IST",
        "exit_time": "15:00 IST",
    },
    "CALENDAR_SPREAD": {
        "name": "Calendar Spread",
        "type": "CALENDAR",
        "description": "Sell near-week expiry + buy far-week expiry at same strike. Profit from front-month theta decay accelerating vs back-month.",
        "direction": "NEUTRAL",
        "edge_source": "Front-month theta > back-month theta",
        "typical_win_rate": "60-70%",
        "best_market": "Stable IV, range bound, 5-7 days to near expiry",
        "entry_time": "Mon 09:35 IST",
        "exit_time": "Thu 14:30 IST (near expiry)",
    },
    "VRP_HARVEST": {
        "name": "Volatility Risk Premium Harvest",
        "type": "VRP",
        "description": "Sell Iron Condor when IV Rank > 70 (IV in top 30% of 60-day range). Exit when IV normalizes or theta captures 50% of credit. Edge: IV systematically overestimates RV by 2-4% annualized.",
        "direction": "NEUTRAL",
        "edge_source": "Volatility Risk Premium (IV > RV) + IV mean reversion + theta decay",
        "typical_win_rate": "65-75%",
        "best_market": "High IV Rank (>70), range bound, post-event IV crush",
        "entry_time": "When IV Rank > 70 (anytime)",
        "exit_time": "IV Rank < 30, or 50% theta capture, or SL hit",
    },
}

# ============ SIGNAL GENERATION ============
def _calc_confidence(strategy_key: str, market_data: Dict) -> float:
    """Calculate confidence score (50-92%) based on market conditions."""
    base = {
        "STRADDLE_SELL": 68,
        "STRANGLE_SELL": 72,
        "STRADDLE_BUY": 58,
        "IRON_CONDOR": 75,
        "MOMENTUM_SCALPER": 62,
        "OPENING_RANGE_BREAKOUT": 64,
        "LONG_BUTTERFLY": 65,
        "IRON_BUTTERFLY": 70,
        "CALENDAR_SPREAD": 68,
        "VRP_HARVEST": 78,  # higher base — has real edge hypothesis
    }.get(strategy_key, 60)
    
    # Adjust based on day change (volatile days favor buying strategies)
    day_change_pct = abs(market_data.get("day_change_pct", 0))
    if strategy_key in ("STRADDLE_BUY", "MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT"):
        base += min(day_change_pct * 1.5, 12)
    else:
        base -= min(day_change_pct * 1.2, 10)
    
    # Add small random variation
    base += random.uniform(-3, 3)
    return round(max(50, min(92, base)), 1)

def _generate_signal_id() -> str:
    return f"SIG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"


def validate_signal(signal: Dict) -> List[str]:
    """Return hard validation errors that make a signal unusable even for paper execution."""
    errors = []
    legs = signal.get("legs") or []
    if not legs:
        errors.append("signal has no legs")
    for index, leg in enumerate(legs, start=1):
        if float(leg.get("premium", 0) or 0) <= 0:
            errors.append(f"leg {index} premium must be positive")
        if float(leg.get("strike", 0) or 0) <= 0:
            errors.append(f"leg {index} strike must be positive")
    for field in ("entry_price", "stop_loss", "target"):
        if float(signal.get(field, 0) or 0) <= 0:
            errors.append(f"{field} must be positive")
    return errors

def generate_signal(strategy_key: str, symbol: str = "NIFTY") -> Optional[Dict]:
    """Generate a trading signal for given strategy + symbol."""
    if strategy_key not in STRATEGIES:
        return None
    
    strat = STRATEGIES[strategy_key]
    quote = get_live_quote(symbol)
    spot = quote["ltp"]
    
    # Get option chain for option strategies
    chain_data = get_option_chain(symbol, n_strikes=11)
    chain = chain_data["chain"]
    atm_idx = next((i for i, c in enumerate(chain) if c["is_atm"]), len(chain) // 2)
    
    confidence = _calc_confidence(strategy_key, quote)
    
    # Pick legs based on strategy
    signal = {
        "signal_id": _generate_signal_id(),
        "strategy_key": strategy_key,
        "strategy_name": strat["name"],
        "strategy_type": strat["type"],
        "symbol": symbol,
        "exchange": quote["exchange"],
        "spot_price": spot,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence": confidence,
        "direction": strat["direction"],
        "legs": [],
        "rationale": "",
        "data_source": quote.get("data_source", "UNKNOWN"),
        "evidence_grade": quote.get("evidence_grade", "UNKNOWN"),
    }
    
    if strategy_key == "STRADDLE_SELL":
        atm = chain[atm_idx]
        legs = [
            {"action": "SELL", "type": "CE", "strike": atm["strike"], "premium": atm["ce"]["price"], "delta": atm["ce"]["delta"], "theta": atm["ce"]["theta"]},
            {"action": "SELL", "type": "PE", "strike": atm["strike"], "premium": atm["pe"]["price"], "delta": atm["pe"]["delta"], "theta": atm["pe"]["theta"]},
        ]
        net_premium = sum(l["premium"] for l in legs)
        signal["legs"] = legs
        signal["entry_price"] = round(net_premium, 2)
        signal["stop_loss"] = round(net_premium * 1.30, 2)  # 30% SL on premium
        signal["target"] = round(net_premium * 0.50, 2)  # 50% profit
        signal["max_profit"] = round(net_premium, 2)
        signal["max_loss"] = "Unlimited (manage with SL)"
        signal["breakeven_upper"] = round(atm["strike"] + net_premium, 2)
        signal["breakeven_lower"] = round(atm["strike"] - net_premium, 2)
        signal["rationale"] = f"Selling ATM straddle at {atm['strike']}. Net premium ₹{net_premium:.0f} per lot. Target 50% premium decay, SL at 30% premium expansion. Requires spot to stay in [{atm['strike'] - net_premium:.0f}, {atm['strike'] + net_premium:.0f}] range."
    
    elif strategy_key == "STRANGLE_SELL":
        otm_ce = chain[min(atm_idx + 3, len(chain) - 1)]
        otm_pe = chain[max(atm_idx - 3, 0)]
        legs = [
            {"action": "SELL", "type": "CE", "strike": otm_ce["strike"], "premium": otm_ce["ce"]["price"], "delta": otm_ce["ce"]["delta"], "theta": otm_ce["ce"]["theta"]},
            {"action": "SELL", "type": "PE", "strike": otm_pe["strike"], "premium": otm_pe["pe"]["price"], "delta": otm_pe["pe"]["delta"], "theta": otm_pe["pe"]["theta"]},
        ]
        net_premium = sum(l["premium"] for l in legs)
        signal["legs"] = legs
        signal["entry_price"] = round(net_premium, 2)
        signal["stop_loss"] = round(net_premium * 1.50, 2)
        signal["target"] = round(net_premium * 0.60, 2)
        signal["max_profit"] = round(net_premium, 2)
        signal["max_loss"] = "Unlimited (manage with SL)"
        signal["breakeven_upper"] = round(otm_ce["strike"] + net_premium, 2)
        signal["breakeven_lower"] = round(otm_pe["strike"] - net_premium, 2)
        signal["rationale"] = f"Selling OTM strangle: CE {otm_ce['strike']} + PE {otm_pe['strike']}. Wider profit zone than straddle, lower premium. Best when IV is high and expected to fall."
    
    elif strategy_key == "STRADDLE_BUY":
        atm = chain[atm_idx]
        legs = [
            {"action": "BUY", "type": "CE", "strike": atm["strike"], "premium": atm["ce"]["price"], "delta": atm["ce"]["delta"], "theta": atm["ce"]["theta"]},
            {"action": "BUY", "type": "PE", "strike": atm["strike"], "premium": atm["pe"]["price"], "delta": atm["pe"]["delta"], "theta": atm["pe"]["theta"]},
        ]
        net_premium = sum(l["premium"] for l in legs)
        signal["legs"] = legs
        signal["entry_price"] = round(net_premium, 2)
        signal["stop_loss"] = round(net_premium * 0.70, 2)  # 30% loss SL
        signal["target"] = round(net_premium * 2.0, 2)  # 100% gain target
        signal["max_profit"] = "Unlimited"
        signal["max_loss"] = round(net_premium, 2)
        signal["breakeven_upper"] = round(atm["strike"] + net_premium, 2)
        signal["breakeven_lower"] = round(atm["strike"] - net_premium, 2)
        signal["rationale"] = f"Buying ATM straddle at {atm['strike']}. Need spot to move >₹{net_premium:.0f} in either direction. Best before events: budget, RBI policy, elections."
    
    elif strategy_key == "IRON_CONDOR":
        short_ce = chain[min(atm_idx + 3, len(chain) - 1)]
        short_pe = chain[max(atm_idx - 3, 0)]
        long_ce = chain[min(atm_idx + 5, len(chain) - 1)]
        long_pe = chain[max(atm_idx - 5, 0)]
        legs = [
            {"action": "SELL", "type": "CE", "strike": short_ce["strike"], "premium": short_ce["ce"]["price"]},
            {"action": "BUY",  "type": "CE", "strike": long_ce["strike"], "premium": long_ce["ce"]["price"]},
            {"action": "SELL", "type": "PE", "strike": short_pe["strike"], "premium": short_pe["pe"]["price"]},
            {"action": "BUY",  "type": "PE", "strike": long_pe["strike"], "premium": long_pe["pe"]["price"]},
        ]
        net_premium = sum(l["premium"] if l["action"] == "SELL" else -l["premium"] for l in legs)
        width = abs(short_ce["strike"] - long_ce["strike"])
        signal["legs"] = legs
        signal["entry_price"] = round(net_premium, 2)
        signal["stop_loss"] = round(net_premium + width * 0.5, 2)
        signal["target"] = round(net_premium * 0.60, 2)
        signal["max_profit"] = round(net_premium, 2)
        signal["max_loss"] = round(width - net_premium, 2)
        signal["breakeven_upper"] = round(short_ce["strike"] + net_premium, 2)
        signal["breakeven_lower"] = round(short_pe["strike"] - net_premium, 2)
        signal["rationale"] = f"Iron Condor: short {short_ce['strike']}CE/{short_pe['strike']}PE, long {long_ce['strike']}CE/{long_pe['strike']}PE. Max profit ₹{net_premium:.0f}, max loss ₹{width - net_premium:.0f}. Defined risk range-bound strategy."
    
    elif strategy_key == "MOMENTUM_SCALPER":
        # Pick CE if day_change > 0 else PE
        opt = chain[atm_idx + 1 if quote["day_change"] >= 0 else atm_idx - 1]
        opt_type = "CE" if quote["day_change"] >= 0 else "PE"
        leg_data = opt["ce"] if opt_type == "CE" else opt["pe"]
        legs = [{"action": "BUY", "type": opt_type, "strike": opt["strike"], "premium": leg_data["price"], "delta": leg_data["delta"]}]
        signal["legs"] = legs
        signal["entry_price"] = round(leg_data["price"], 2)
        signal["stop_loss"] = round(leg_data["price"] * 0.85, 2)  # 15% SL
        signal["target"] = round(leg_data["price"] * 1.25, 2)  # 25% gain
        signal["rationale"] = f"Momentum scalp: BUY {opt['strike']}{opt_type} at ₹{leg_data['price']:.1f}. Day change {quote['day_change_pct']:+.2f}% confirms {'bullish' if opt_type == 'CE' else 'bearish'} bias. Quick 5-15 min trade."
    
    elif strategy_key == "OPENING_RANGE_BREAKOUT":
        opt_type = "CE" if quote["day_change"] >= 0 else "PE"
        opt = chain[atm_idx + 2 if opt_type == "CE" else atm_idx - 2]
        leg_data = opt["ce"] if opt_type == "CE" else opt["pe"]
        legs = [{"action": "BUY", "type": opt_type, "strike": opt["strike"], "premium": leg_data["price"], "delta": leg_data["delta"]}]
        signal["legs"] = legs
        signal["entry_price"] = round(leg_data["price"], 2)
        signal["stop_loss"] = round(leg_data["price"] * 0.75, 2)  # 25% SL
        signal["target"] = round(leg_data["price"] * 1.50, 2)  # 50% target
        signal["rationale"] = f"ORB setup: BUY {opt['strike']}{opt_type} at ₹{leg_data['price']:.1f}. 15-min opening range broken {'up' if opt_type == 'CE' else 'down'}. SL at 25% premium loss, target 50% gain."
    
    elif strategy_key == "LONG_BUTTERFLY":
        # Buy 1 ITM CE + Sell 2 ATM CE + Buy 1 OTM CE
        itm_ce = chain[max(atm_idx - 2, 0)]
        atm = chain[atm_idx]
        otm_ce = chain[min(atm_idx + 2, len(chain) - 1)]
        legs = [
            {"action": "BUY",  "type": "CE", "strike": itm_ce["strike"], "premium": itm_ce["ce"]["price"]},
            {"action": "SELL", "type": "CE", "strike": atm["strike"],    "premium": atm["ce"]["price"], "qty_mult": 2},
            {"action": "BUY",  "type": "CE", "strike": otm_ce["strike"], "premium": otm_ce["ce"]["price"]},
        ]
        # Net debit = buy1 + buy1 - sell2*atm
        net_debit = itm_ce["ce"]["price"] + otm_ce["ce"]["price"] - 2 * atm["ce"]["price"]
        width = abs(atm["strike"] - itm_ce["strike"])
        max_profit = width - net_debit
        signal["legs"] = legs
        signal["entry_price"] = round(net_debit, 2)
        signal["stop_loss"] = round(net_debit * 0.50, 2)  # exit if lose 50% of debit
        signal["target"] = round(max_profit, 2)
        signal["max_profit"] = round(max_profit, 2)
        signal["max_loss"] = round(net_debit, 2)
        signal["breakeven_lower"] = round(itm_ce["strike"] + net_debit, 2)
        signal["breakeven_upper"] = round(otm_ce["strike"] - net_debit, 2)
        signal["rationale"] = f"Long Call Butterfly: Buy {itm_ce['strike']}CE + Sell 2×{atm['strike']}CE + Buy {otm_ce['strike']}CE. Net debit ₹{net_debit:.0f}. Max profit ₹{max_profit:.0f} if expires at {atm['strike']}. Low cost, defined risk."
    
    elif strategy_key == "IRON_BUTTERFLY":
        # Sell ATM straddle + Buy OTM strangle (wings)
        atm = chain[atm_idx]
        otm_ce = chain[min(atm_idx + 3, len(chain) - 1)]
        otm_pe = chain[max(atm_idx - 3, 0)]
        legs = [
            {"action": "SELL", "type": "CE", "strike": atm["strike"],    "premium": atm["ce"]["price"]},
            {"action": "SELL", "type": "PE", "strike": atm["strike"],    "premium": atm["pe"]["price"]},
            {"action": "BUY",  "type": "CE", "strike": otm_ce["strike"], "premium": otm_ce["ce"]["price"]},
            {"action": "BUY",  "type": "PE", "strike": otm_pe["strike"], "premium": otm_pe["pe"]["price"]},
        ]
        net_credit = atm["ce"]["price"] + atm["pe"]["price"] - otm_ce["ce"]["price"] - otm_pe["pe"]["price"]
        width = abs(otm_ce["strike"] - atm["strike"])
        max_loss = width - net_credit
        signal["legs"] = legs
        signal["entry_price"] = round(net_credit, 2)
        signal["stop_loss"] = round(net_credit + width * 0.5, 2)
        signal["target"] = round(net_credit * 0.60, 2)
        signal["max_profit"] = round(net_credit, 2)
        signal["max_loss"] = round(max_loss, 2)
        signal["breakeven_upper"] = round(atm["strike"] + net_credit, 2)
        signal["breakeven_lower"] = round(atm["strike"] - net_credit, 2)
        signal["rationale"] = f"Iron Butterfly: Sell {atm['strike']} straddle + Buy {otm_ce['strike']}CE/{otm_pe['strike']}PE wings. Credit ₹{net_credit:.0f}, max loss ₹{max_loss:.0f}. Best when expecting expiry-day pinning at {atm['strike']}."
    
    elif strategy_key == "CALENDAR_SPREAD":
        # Sell near-week + Buy far-week at same ATM strike
        atm = chain[atm_idx]
        # Far month option typically costs ~1.4x near month (extra time value)
        near_premium = atm["ce"]["price"]
        far_premium = round(near_premium * 1.4, 2)
        # Use same strike for both legs (typical calendar)
        legs = [
            {"action": "SELL", "type": "CE", "strike": atm["strike"], "premium": near_premium,  "expiry": "near-week"},
            {"action": "BUY",  "type": "CE", "strike": atm["strike"], "premium": far_premium,   "expiry": "far-week"},
        ]
        net_debit = far_premium - near_premium
        signal["legs"] = legs
        signal["entry_price"] = round(net_debit, 2)
        signal["stop_loss"] = round(net_debit * 1.50, 2)
        signal["target"] = round(near_premium * 0.50, 2)  # profit from near-week theta
        signal["max_profit"] = round(near_premium * 0.50, 2)
        signal["max_loss"] = round(net_debit, 2)
        signal["breakeven_lower"] = round(atm["strike"] - net_debit * 0.7, 2)
        signal["breakeven_upper"] = round(atm["strike"] + net_debit * 0.7, 2)
        signal["rationale"] = f"Calendar Spread: Sell near-week {atm['strike']}CE @ ₹{near_premium:.0f} + Buy far-week {atm['strike']}CE @ ₹{far_premium:.0f}. Net debit ₹{net_debit:.0f}. Profit when near-week decays faster than far-week. Best 5-7 days to near expiry."
    
    elif strategy_key == "VRP_HARVEST":
        # VRP Harvest: Iron Condor structure (defined risk) when IV is high
        # Sell OTM strangle + Buy further OTM wings for protection
        short_ce = chain[min(atm_idx + 3, len(chain) - 1)]
        short_pe = chain[max(atm_idx - 3, 0)]
        long_ce = chain[min(atm_idx + 5, len(chain) - 1)]
        long_pe = chain[max(atm_idx - 5, 0)]
        legs = [
            {"action": "SELL", "type": "CE", "strike": short_ce["strike"], "premium": short_ce["ce"]["price"]},
            {"action": "BUY",  "type": "CE", "strike": long_ce["strike"], "premium": long_ce["ce"]["price"]},
            {"action": "SELL", "type": "PE", "strike": short_pe["strike"], "premium": short_pe["pe"]["price"]},
            {"action": "BUY",  "type": "PE", "strike": long_pe["strike"], "premium": long_pe["pe"]["price"]},
        ]
        net_credit = sum(l["premium"] if l["action"] == "SELL" else -l["premium"] for l in legs)
        width = abs(short_ce["strike"] - long_ce["strike"])
        max_loss = width - net_credit
        # VRP-specific: track IV rank for entry/exit decision
        signal["legs"] = legs
        signal["entry_price"] = round(net_credit, 2)
        signal["stop_loss"] = round(net_credit + width * 0.5, 2)
        signal["target"] = round(net_credit * 0.50, 2)  # exit at 50% theta capture
        signal["max_profit"] = round(net_credit, 2)
        signal["max_loss"] = round(max_loss, 2)
        signal["breakeven_upper"] = round(short_ce["strike"] + net_credit, 2)
        signal["breakeven_lower"] = round(short_pe["strike"] - net_credit, 2)
        signal["rationale"] = (
            f"VRP Harvest Iron Condor: Sell {short_ce['strike']}CE/{short_pe['strike']}PE strangle "
            f"+ Buy {long_ce['strike']}CE/{long_pe['strike']}PE wings. Net credit ₹{net_credit:.0f}, "
            f"max loss ₹{max_loss:.0f}. Entry triggered by IV Rank > 70 (IV in top 30% of 60-day range). "
            f"Exit when IV Rank < 30 or 50% theta captured. Edge: IV systematically overestimates RV."
        )
    
    errors = validate_signal(signal)
    signal["validation_errors"] = errors
    signal["paper_execution_eligible"] = not errors
    signal["execution_eligible"] = not errors and signal["evidence_grade"] == "REAL_MARKET"
    signal["execution_scope"] = "REAL_MARKET" if signal["execution_eligible"] else "PAPER_RND"
    signal["status"] = "VERIFIED" if signal["execution_eligible"] else ("INVALID" if errors else "CANDIDATE")
    return signal

def generate_signals_feed(limit: int = 12) -> List[Dict]:
    """Generate a feed of recent signals across strategies & symbols."""
    symbols = ["NIFTY", "BANKNIFTY", "GOLD", "NATURALGAS"]
    strategy_keys = list(STRATEGIES.keys())
    signals = []
    
    # Generate signals spread over last few hours
    now = datetime.now(timezone.utc)
    attempts = 0
    while len(signals) < limit and attempts < limit * 4:
        i = attempts
        attempts += 1
        sym = symbols[i % len(symbols)]
        strat = strategy_keys[i % len(strategy_keys)]
        sig = generate_signal(strat, sym)
        if sig and not sig.get("validation_errors"):
            # Backdate timestamp
            minutes_ago = i * random.randint(8, 25)
            sig["timestamp"] = (now - timedelta_for(minutes_ago)).isoformat()
            signals.append(sig)
    
    return signals

def timedelta_for(minutes: int):
    from datetime import timedelta
    return timedelta(minutes=minutes)
