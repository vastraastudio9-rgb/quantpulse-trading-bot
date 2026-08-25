"""
Backtesting Engine (JARVIS-v2)
- Runs historical simulation of strategies
- Computes: Total Return %, Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor, Expectancy, Calmar
- Realistic costs: brokerage + STT + stamp duty + GST + slippage
- Uses Black-Scholes for premium revaluation (not constant gamma)
- NO look-ahead bias: decision on bar[i-1], execution on bar[i]["open"]
- Mark-to-market equity curve (Sharpe computed on actual returns, not flat periods)
- Supports OOS split + walk-forward via external orchestrator
"""
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import numpy as np
from market_data import generate_history, INSTRUMENTS
from greeks import option_price, greeks_bundle
from regime import atr, iv_rank, realized_volatility

# ============ COSTS (Indian F&O) ============
def calc_costs(premium: float, qty: int, is_sell: bool = False, slippage_ticks: int = 0, tick_size: float = 0.05) -> Dict:
    """Estimate transaction costs for options trade in India.
    Includes: brokerage, STT, exchange txn, GST, SEBI, stamp duty, slippage.
    
    Args:
        premium: option premium per unit
        qty: number of units (lot_size * num_lots)
        is_sell: True for SELL leg (STT applies)
        slippage_ticks: estimated slippage in ticks (e.g., 2-5 for ATM, 5-15 for OTM)
        tick_size: minimum price movement
    """
    turnover = premium * qty
    brokerage = 20.0  # ₹20 per executed order (capped at Zerodha)
    stt = turnover * 0.001 if is_sell else 0  # 0.1% STT on sell side only (options)
    exchange_txn = turnover * 0.00053  # ~0.053% exchange txn charge
    gst = (brokerage + exchange_txn) * 0.18  # 18% GST on brokerage + txn
    sebi = turnover * 0.000001  # ₹10 per crore
    stamp_duty = turnover * 0.00003 if not is_sell else 0  # 0.003% on buy side
    slippage_cost = slippage_ticks * tick_size * qty  # slippage in price * qty
    total = brokerage + stt + exchange_txn + gst + sebi + stamp_duty + slippage_cost
    return {
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange_txn": round(exchange_txn, 2),
        "gst": round(gst, 2),
        "sebi": round(sebi, 2),
        "stamp_duty": round(stamp_duty, 2),
        "slippage": round(slippage_cost, 2),
        "total": round(total, 2),
    }


# ============ SLIPPAGE MODEL ============
def estimate_slippage(symbol: str, strike_offset: int = 0) -> int:
    """Estimate slippage in ticks based on instrument + strike distance.
    
    NIFTY/BANKNIFTY ATM: 2-3 ticks
    NIFTY/BANKNIFTY OTM (offset 3+): 5-10 ticks
    MCX (Gold/NatGas): 5-15 ticks (less liquid)
    Forex (via MT5): typically 0.5-2 pips, modeled as 1-2 ticks
    """
    if symbol in ("NIFTY", "BANKNIFTY", "FINNIFTY"):
        if strike_offset <= 1:
            return random.randint(2, 4)
        elif strike_offset <= 3:
            return random.randint(4, 8)
        else:
            return random.randint(8, 15)
    elif symbol in ("GOLD", "NATURALGAS", "CRUDEOIL"):
        return random.randint(5, 15)
    else:  # Forex
        return random.randint(1, 3)


# ============ METRICS CALCULATION (JARVIS-v2) ============
def compute_metrics(
    equity_curve: List[float],
    trades: List[Dict],
    initial_capital: float,
    bars_per_year: int = 252,
) -> Dict:
    """Compute performance metrics.
    
    JARVIS-v2 fixes:
    - Mark-to-market equity curve (no flat periods inflating Sharpe)
    - Annualization factor configurable (252 for daily, 252*6.25*12 for 5-min)
    - Risk-free rate from Indian 10Y G-Sec (~7%)
    """
    if not equity_curve or len(equity_curve) < 2:
        return _empty_metrics()
    
    eq = np.array(equity_curve, dtype=float)
    final_capital = float(eq[-1])
    total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100.0
    
    # Bar-level returns (mark-to-market — equity curve already reflects this)
    returns = np.diff(eq) / eq[:-1]
    returns = returns[np.isfinite(returns)]
    
    if len(returns) == 0:
        return _empty_metrics()
    
    # Annualization
    ann_factor = math.sqrt(bars_per_year)
    mean_r = float(np.mean(returns))
    std_r = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    
    # Sharpe ratio (Indian risk-free: 7% G-Sec)
    rf_per_bar = 0.07 / bars_per_year
    sharpe = ((mean_r - rf_per_bar) / std_r * ann_factor) if std_r > 0 else 0.0
    
    # Sortino ratio (downside deviation only)
    downside = returns[returns < 0]
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    sortino = ((mean_r - rf_per_bar) / downside_std * ann_factor) if downside_std > 0 else 0.0
    
    # Max drawdown — computed on FULL equity curve, not sampled
    running_max = np.maximum.accumulate(eq)
    drawdowns = (eq - running_max) / running_max
    max_dd = float(abs(np.min(drawdowns)) * 100) if len(drawdowns) > 0 else 0.0
    
    # Calmar ratio (annualized return / max DD)
    years = len(equity_curve) / bars_per_year if bars_per_year > 0 else 1
    if years > 0 and max_dd > 0:
        ann_return_pct = (((final_capital / initial_capital) ** (1 / years)) - 1) * 100 if final_capital > 0 else 0
        calmar = ann_return_pct / max_dd
    else:
        calmar = 0.0
    
    # Trade metrics
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = (len(wins) / len(pnls) * 100) if pnls else 0
    avg_win = float(np.mean(wins)) if wins else 0
    avg_loss = float(np.mean(losses)) if losses else 0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    expectancy = float(np.mean(pnls)) if pnls else 0
    
    # Win/loss ratio
    win_loss_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else 0
    
    # Largest win / largest loss (tail risk)
    largest_win = max(pnls) if pnls else 0
    largest_loss = min(pnls) if pnls else 0
    
    # Average hold duration (bars)
    durations = [t.get("duration_bars", 0) for t in trades]
    avg_duration = float(np.mean(durations)) if durations else 0
    
    # Exposure (% of bars with open position)
    if bars_per_year > 0 and "total_bars" in (locals() if False else {}):
        pass  # placeholder — needs total_bars passed in
    
    return {
        "initial_capital": round(initial_capital, 2),
        "final_capital": round(final_capital, 2),
        "total_return_pct": round(total_return_pct, 2),
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "win_loss_ratio": round(win_loss_ratio, 3),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else 99.99,
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "expectancy": round(expectancy, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "largest_win": round(largest_win, 2),
        "largest_loss": round(largest_loss, 2),
        "avg_duration_bars": round(avg_duration, 2),
    }

def _empty_metrics() -> Dict:
    return {
        "initial_capital": 0, "final_capital": 0, "total_return_pct": 0,
        "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
        "avg_win": 0, "avg_loss": 0, "win_loss_ratio": 0,
        "profit_factor": 0, "max_drawdown_pct": 0,
        "sharpe": 0, "sortino": 0, "calmar": 0,
        "expectancy": 0, "gross_profit": 0, "gross_loss": 0,
        "largest_win": 0, "largest_loss": 0, "avg_duration_bars": 0,
    }


# ============ BLACK-SCHOLES PREMIUM REVALUATION ============
def revalue_option_premium(
    entry_premium: float,
    entry_spot: float,
    current_spot: float,
    bars_held: int,
    total_bars_to_expiry: int,
    sigma: float,
    side: str,
    r: float = 0.07,
) -> float:
    """Revalue option premium using Black-Scholes.
    
    Instead of constant gamma/theta, we compute the actual option price
    at the current spot, with reduced time-to-expiry.
    
    Args:
        entry_premium: premium at entry (used to infer strike)
        entry_spot: spot at entry
        current_spot: current spot
        bars_held: bars elapsed since entry
        total_bars_to_expiry: bars from entry to expiry
        sigma: implied volatility (annualized, decimal)
        side: "BUY" (long) or "SELL" (short)
        r: risk-free rate
    
    Returns: current premium
    """
    # Infer ATM strike from entry (assume entry was ATM)
    strike = entry_spot
    # Time to expiry at entry (in years)
    if total_bars_to_expiry <= 0:
        return max(entry_premium * 0.1, 0.05)  # near expiry, deep ITM/OTM
    
    t_entry = total_bars_to_expiry / 252.0  # assuming daily bars
    t_now = max((total_bars_to_expiry - bars_held) / 252.0, 1 / 252.0)
    
    # Compute initial IV-implied price (calibrate sigma to entry_premium)
    # For simplicity, assume entry_premium ≈ BS price with given sigma at entry
    # Then revalue at current spot with reduced time
    try:
        # Average of CE and PE for straddle-like behavior
        ce_price = option_price(entry_spot, strike, t_entry, r, sigma, "CE")
        pe_price = option_price(entry_spot, strike, t_entry, r, sigma, "PE")
        # Scale factor to match entry_premium
        if ce_price + pe_price > 0:
            scale = entry_premium / ((ce_price + pe_price) / 2)
        else:
            scale = 1.0
        
        # Revalue at current spot
        ce_now = option_price(current_spot, strike, t_now, r, sigma, "CE")
        pe_now = option_price(current_spot, strike, t_now, r, sigma, "PE")
        avg_now = (ce_now + pe_now) / 2 * scale
        return max(avg_now, 0.05)
    except Exception:
        # Fallback to simplified model
        spot_move_pct = (current_spot - entry_spot) / entry_spot if entry_spot else 0
        # For straddle: premium increases with |spot move| (gamma), decreases with time (theta)
        gamma_effect = abs(spot_move_pct) * 4  # ~4x for ATM
        theta_decay = (bars_held / total_bars_to_expiry) * 0.3  # 30% decay over life
        if side == "SELL":
            # For short: premium change is opposite (we want it to decay)
            return entry_premium * (1 - theta_decay + gamma_effect * 0.5)
        else:
            return entry_premium * (1 + gamma_effect - theta_decay)


# ============ BACKTEST RUNNER (JARVIS-v2) ============
def run_backtest(
    strategy_key: str,
    symbol: str,
    days: int = 180,
    timeframe: str = "1d",
    initial_capital: float = 100000.0,
    lot_size: int = 1,
    sl_pct: float = 25.0,
    tp_pct: float = 50.0,
    max_positions: int = 1,
    slippage_enabled: bool = True,
    mark_to_market: bool = True,
) -> Dict:
    """Run a backtest for given strategy on historical data.
    
    JARVIS-v2 fixes:
    - NO look-ahead bias: decision uses bars[i-1] data, execution at bars[i]["open"]
    - Black-Scholes premium revaluation (not constant gamma)
    - Slippage modeled per instrument + strike distance
    - Mark-to-market equity curve (no flat periods)
    - Realistic costs including slippage
    - Configurable bars_per_year for Sharpe annualization
    
    Returns full results: metrics, equity curve, monthly returns, trades list, diagnostics.
    """
    if symbol not in INSTRUMENTS:
        raise ValueError(f"Unknown symbol: {symbol}")
    
    cfg = INSTRUMENTS[symbol]
    actual_lot = cfg["lot_size"]
    qty = actual_lot * lot_size
    sigma = cfg["volatility"]
    tick_size = cfg["tick_size"]
    
    # Bars per year for annualization
    bars_per_year = {"1m": 252 * 375, "5m": 252 * 75, "15m": 252 * 25, "1h": 252 * 6, "1d": 252}.get(timeframe, 252)
    
    # Get historical data
    bars = generate_history(symbol, days=days, timeframe=timeframe)
    if not bars:
        return {"status": "FAILED", "error": "No historical data", "metrics": _empty_metrics()}
    
    # Run strategy simulation
    trades = []
    equity_curve = [initial_capital]
    equity_dates = [bars[0]["timestamp"]]
    
    capital = initial_capital
    open_position = None
    bars_with_position = 0
    total_bars = len(bars)
    
    # Strategy logic per type — NO LOOK-AHEAD: decide on bar[i-1], execute on bar[i]["open"]
    for i in range(2, len(bars)):
        # === DECISION PHASE: use bars[i-1] and earlier ===
        prev_bar = bars[i - 1]
        prev_prev = bars[i - 2]
        current_bar = bars[i]
        
        # ATR-like range from PREVIOUS bar (no future data)
        prev_range = prev_bar["high"] - prev_bar["low"]
        avg_range = float(np.mean([b["high"] - b["low"] for b in bars[max(0, i - 11) : i - 1]])) if i > 11 else prev_range
        
        # Entry logic — decision made BEFORE current bar
        if open_position is None and i < len(bars) - 2:
            should_enter = False
            entry_premium = 0
            side = "SELL"
            strike_offset = 0  # for slippage estimation
            entry_iv_rank = 0  # VRP-specific: IV rank at entry
            # DTE assumption: weekly expiry (5 trading days). Used for BS pricing.
            dte_bars = 5 if timeframe == "1d" else 5 * 75
            t_to_expiry = dte_bars / bars_per_year
            # Use actual BS price for entry premium (not spot * 0.008 which understated by ~50%)
            spot_for_pricing = prev_bar["close"]
            atm_strike = spot_for_pricing  # simplified: assume ATM
            ce_atm = option_price(spot_for_pricing, atm_strike, t_to_expiry, 0.07, sigma, "CE")
            pe_atm = option_price(spot_for_pricing, atm_strike, t_to_expiry, 0.07, sigma, "PE")
            straddle_premium = ce_atm + pe_atm
            # OTM strangle: estimate as ~60% of straddle (rough approximation)
            strangle_premium = straddle_premium * 0.55
            # Iron condor net credit ~35% of straddle
            iron_condor_credit = straddle_premium * 0.35
            # Iron butterfly net credit ~70% of straddle (sell ATM straddle, buy OTM wings)
            iron_butterfly_credit = straddle_premium * 0.65
            # Long butterfly net debit ~15% of strike width
            long_butterfly_debit = straddle_premium * 0.15
            # Calendar spread net debit ~30% of near-month premium
            calendar_debit = ce_atm * 0.4
            # Long straddle (buy) = full straddle premium
            long_straddle_cost = straddle_premium
            # Single-leg buy (scalper/ORB): ATM option
            single_leg_cost = ce_atm  # ~half of straddle

            if strategy_key in ("STRADDLE_SELL", "STRANGLE_SELL"):
                if prev_range < avg_range * 0.9:
                    should_enter = True
                    entry_premium = straddle_premium if strategy_key == "STRADDLE_SELL" else strangle_premium
                    strike_offset = 0 if strategy_key == "STRADDLE_SELL" else 3

            elif strategy_key == "STRADDLE_BUY":
                if prev_range > avg_range * 1.3:
                    should_enter = True
                    side = "BUY"
                    entry_premium = long_straddle_cost

            elif strategy_key == "IRON_CONDOR":
                if prev_range < avg_range * 0.85:
                    should_enter = True
                    entry_premium = iron_condor_credit
                    strike_offset = 3

            elif strategy_key == "MOMENTUM_SCALPER":
                bar_pos = (prev_bar["close"] - prev_bar["low"]) / (prev_range if prev_range > 0 else 1)
                if bar_pos > 0.75 or bar_pos < 0.25:
                    should_enter = True
                    side = "BUY"
                    entry_premium = single_leg_cost
                    strike_offset = 1

            elif strategy_key == "OPENING_RANGE_BREAKOUT":
                if prev_bar["close"] > prev_prev["high"] or prev_bar["close"] < prev_prev["low"]:
                    should_enter = True
                    side = "BUY"
                    entry_premium = single_leg_cost
                    strike_offset = 2

            elif strategy_key in ("LONG_BUTTERFLY", "IRON_BUTTERFLY"):
                if prev_range < avg_range * 0.85:
                    should_enter = True
                    side = "SELL"
                    entry_premium = iron_butterfly_credit if strategy_key == "IRON_BUTTERFLY" else long_butterfly_debit
                    strike_offset = 0 if strategy_key == "IRON_BUTTERFLY" else 2

            elif strategy_key == "CALENDAR_SPREAD":
                day_chg = abs(prev_bar["close"] - bars[max(0, i - 6)]["close"]) / bars[max(0, i - 6)]["close"]
                if prev_range < avg_range * 0.95 and day_chg < 0.01:
                    should_enter = True
                    side = "BUY"
                    entry_premium = calendar_debit

            elif strategy_key == "VRP_HARVEST":
                # VRP Harvest: enter ONLY when IV Rank > 70 (real edge condition)
                # Uses 60-bar lookback for IV rank computation
                if i >= 60:
                    current_iv_rank = iv_rank(bars[:i], lookback=60)
                    if current_iv_rank > 70:
                        should_enter = True
                        entry_premium = iron_condor_credit
                        strike_offset = 3
                        # Store IV rank at entry for exit logic
                        entry_iv_rank = current_iv_rank
            
            if should_enter:
                # === EXECUTION PHASE: execute at current_bar["open"] (next bar after decision) ===
                # Realistic: you decided at end of prev_bar, placed order, fills at current_bar open
                exec_price = current_bar["open"]
                # Adjust premium based on actual exec price vs prev close (gap effect)
                gap_factor = exec_price / prev_bar["close"] if prev_bar["close"] else 1.0
                entry_premium = entry_premium * gap_factor
                
                slippage_ticks = estimate_slippage(symbol, strike_offset) if slippage_enabled else 0
                costs = calc_costs(entry_premium, qty, is_sell=(side == "SELL"), slippage_ticks=slippage_ticks, tick_size=tick_size)
                
                # Estimate total bars to expiry (assume weekly expiry = 5 trading days)
                total_bars_to_expiry = 5 if timeframe == "1d" else 5 * (252 * 6 if timeframe == "1h" else 75)
                
                # SL/TP logic: for SELL strategies, use premium-based SL (sl_pct on premium collected)
                # For BUY strategies, use premium-based SL on debit paid
                # BUT scale SL to be at least 1 ATR worth of spot move (more realistic)
                # This prevents the "SL hit on day 1 due to normal vol" problem
                atr_at_entry = atr(bars[:i], 14) if i >= 14 else avg_range
                # Minimum SL = 1 ATR worth of premium impact (~ATR * gamma leverage ~4x for ATM)
                min_sl_premium = atr_at_entry * 2  # ~2 ATR = realistic spot move tolerance
                sl_premium = entry_premium * (sl_pct / 100)
                if side == "SELL" and sl_premium < min_sl_premium:
                    sl_premium = min_sl_premium  # use larger SL if % based is too tight
                tp_premium = entry_premium * (tp_pct / 100)
                
                open_position = {
                    "entry_bar": i,
                    "entry_time": current_bar["timestamp"],
                    "entry_price": entry_premium,
                    "side": side,
                    "spot_at_entry": exec_price,
                    "costs": costs["total"],
                    "slippage": costs["slippage"],
                    "qty": qty,
                    "sl_price": (entry_premium + sl_premium) if side == "SELL" else (entry_premium - sl_premium),
                    "tp_price": (entry_premium - tp_premium) if side == "SELL" else (entry_premium + tp_premium),
                    "total_bars_to_expiry": total_bars_to_expiry,
                    "sigma": sigma,
                    "atr_at_entry": atr_at_entry,
                    "strategy_key": strategy_key,
                    "entry_iv_rank": entry_iv_rank,
                }
        
        # === EXIT / MARK-TO-MARKET PHASE ===
        if open_position is not None:
            bars_held = i - open_position["entry_bar"]
            current_spot = current_bar["close"]
            
            # Revalue premium using Black-Scholes (not constant gamma)
            current_premium = revalue_option_premium(
                entry_premium=open_position["entry_price"],
                entry_spot=open_position["spot_at_entry"],
                current_spot=current_spot,
                bars_held=bars_held,
                total_bars_to_expiry=open_position["total_bars_to_expiry"],
                sigma=open_position["sigma"],
                side=open_position["side"],
            )
            current_premium = max(current_premium, 0.05)
            
            # Track unrealized P&L for mark-to-market
            if open_position["side"] == "SELL":
                unrealized_pnl = (open_position["entry_price"] - current_premium) * qty - open_position["costs"]
            else:
                unrealized_pnl = (current_premium - open_position["entry_price"]) * qty - open_position["costs"]
            
            # Determine exit reason
            exit_reason = None
            if open_position["side"] == "SELL" and current_premium >= open_position["sl_price"]:
                exit_reason = "SL_HIT"
            elif open_position["side"] == "BUY" and current_premium <= open_position["sl_price"]:
                exit_reason = "SL_HIT"
            elif open_position["side"] == "SELL" and current_premium <= open_position["tp_price"]:
                exit_reason = "TP_HIT"
            elif open_position["side"] == "BUY" and current_premium >= open_position["tp_price"]:
                exit_reason = "TP_HIT"
            elif bars_held >= min(open_position["total_bars_to_expiry"], 5):  # max 5 bars or to expiry
                exit_reason = "TIME_EXIT"
            
            # VRP-specific exit: exit when IV Rank normalizes (< 30)
            if open_position.get("strategy_key") == "VRP_HARVEST" and not exit_reason:
                if i >= 60:
                    current_iv_rank_exit = iv_rank(bars[:i+1], lookback=60)
                    if current_iv_rank_exit < 30:
                        exit_reason = "IV_NORMALIZED"
            
            # Mark-to-market equity
            if mark_to_market:
                mtm_capital = capital + unrealized_pnl
            else:
                mtm_capital = capital
            
            if exit_reason:
                # Exit slippage
                exit_slippage = estimate_slippage(symbol, 0) if slippage_enabled else 0
                exit_costs = calc_costs(current_premium, qty, is_sell=(open_position["side"] == "BUY"), slippage_ticks=exit_slippage, tick_size=tick_size)
                
                if open_position["side"] == "SELL":
                    pnl = (open_position["entry_price"] - current_premium) * qty
                else:
                    pnl = (current_premium - open_position["entry_price"]) * qty
                pnl -= (open_position["costs"] + exit_costs["total"])
                
                capital += pnl
                trades.append({
                    "entry_time": open_position["entry_time"],
                    "exit_time": current_bar["timestamp"],
                    "side": open_position["side"],
                    "entry_price": round(open_position["entry_price"], 2),
                    "exit_price": round(current_premium, 2),
                    "qty": qty,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round((pnl / (open_position["entry_price"] * qty)) * 100, 2),
                    "exit_reason": exit_reason,
                    "spot_entry": round(open_position["spot_at_entry"], 2),
                    "spot_exit": round(current_spot, 2),
                    "duration_bars": bars_held,
                    "costs": round(open_position["costs"] + exit_costs["total"], 2),
                    "slippage": round(open_position["slippage"] + exit_costs["slippage"], 2),
                })
                open_position = None
                equity_curve.append(round(capital, 2))
            else:
                bars_with_position += 1
                equity_curve.append(round(mtm_capital, 2))
        else:
            # No open position — equity stays flat
            equity_curve.append(round(capital, 2))
        
        equity_dates.append(current_bar["timestamp"])
    
    # Close any remaining open position at last bar
    if open_position is not None:
        last_bar = bars[-1]
        current_premium = revalue_option_premium(
            open_position["entry_price"],
            open_position["spot_at_entry"],
            last_bar["close"],
            len(bars) - open_position["entry_bar"],
            open_position["total_bars_to_expiry"],
            open_position["sigma"],
            open_position["side"],
        )
        if open_position["side"] == "SELL":
            pnl = (open_position["entry_price"] - current_premium) * qty
        else:
            pnl = (current_premium - open_position["entry_price"]) * qty
        pnl -= open_position["costs"]
        capital += pnl
        trades.append({
            "entry_time": open_position["entry_time"],
            "exit_time": last_bar["timestamp"],
            "side": open_position["side"],
            "entry_price": round(open_position["entry_price"], 2),
            "exit_price": round(current_premium, 2),
            "qty": qty,
            "pnl": round(pnl, 2),
            "pnl_pct": round((pnl / (open_position["entry_price"] * qty)) * 100, 2),
            "exit_reason": "EOD_FORCE_CLOSE",
            "spot_entry": round(open_position["spot_at_entry"], 2),
            "spot_exit": round(last_bar["close"], 2),
            "duration_bars": len(bars) - open_position["entry_bar"],
            "costs": round(open_position["costs"], 2),
            "slippage": round(open_position["slippage"], 2),
        })
        equity_curve[-1] = round(capital, 2)
    
    # Compute metrics
    metrics = compute_metrics(equity_curve, trades, initial_capital, bars_per_year=bars_per_year)
    
    # Add exposure metric
    metrics["exposure_pct"] = round((bars_with_position / total_bars) * 100, 2) if total_bars > 0 else 0
    
    # Monthly returns
    monthly_returns = _compute_monthly_returns(equity_dates, equity_curve)
    
    # Sample equity curve to ~100 points for frontend chart (but keep full for metrics)
    step = max(1, len(equity_curve) // 100)
    sampled_curve = [{"date": equity_dates[i], "value": equity_curve[i]} for i in range(0, len(equity_curve), step)]
    if sampled_curve and sampled_curve[-1]["date"] != equity_dates[-1]:
        sampled_curve.append({"date": equity_dates[-1], "value": equity_curve[-1]})
    
    return {
        "status": "COMPLETED",
        "strategy_key": strategy_key,
        "symbol": symbol,
        "timeframe": timeframe,
        "days": days,
        "bars_processed": len(bars),
        "metrics": metrics,
        "equity_curve": sampled_curve,
        "equity_curve_full_points": len(equity_curve),  # signal to frontend that full curve exists
        "monthly_returns": monthly_returns,
        "trades": trades[-50:],  # last 50 trades for display
        "trades_count_total": len(trades),
        "all_trades": trades,  # full list for validation framework
        "slippage_total": round(sum(t.get("slippage", 0) for t in trades), 2),
        "costs_total": round(sum(t.get("costs", 0) for t in trades), 2),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": "JARVIS-v2",
    }

def _compute_monthly_returns(dates: List[str], equity: List[float]) -> List[Dict]:
    """Compute monthly returns % for heatmap."""
    if not dates:
        return []
    monthly = {}
    for i, (d, v) in enumerate(zip(dates, equity)):
        dt = datetime.fromisoformat(d.replace("Z", "+00:00").replace("+00:00", "+00:00"))
        key = f"{dt.year}-{dt.month:02d}"
        if key not in monthly:
            monthly[key] = {"start": v, "end": v}
        monthly[key]["end"] = v
    
    result = []
    for k, v in monthly.items():
        year, month = map(int, k.split("-"))
        ret_pct = ((v["end"] - v["start"]) / v["start"]) * 100 if v["start"] else 0
        result.append({
            "year": year,
            "month": month,
            "month_name": datetime(year, month, 1).strftime("%b"),
            "return_pct": round(ret_pct, 2),
        })
    return result
