"""
JARVIS Paper Trading Execution Engine

Connects: signal generation → risk check → position open → SL/TP monitor → position close
This is the bridge between strategy signals and the portfolio risk engine.

In PAPER mode: all trades are simulated, no real orders placed.
In LIVE mode: would route to broker (Zerodha/MT5) — requires human approval per charter.

Execution flow:
  1. Signal generated (from strategies.py or external)
  2. Pre-trade risk check (risk_engine._pre_trade_checks)
  3. If pass: open position with Greeks, SL, TP
  4. Monitor loop: check live quotes vs SL/TP
  5. On SL/TP hit: close position, record P&L
  6. Update portfolio metrics

Fail-closed: if ANY risk check fails, position is NOT opened.
"""
import math
import time
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import random
import os

from risk_engine import PortfolioRiskEngine, Position, get_portfolio_engine
from market_data import get_live_quote, INSTRUMENTS
from greeks import greeks_bundle
from observability import logger, metrics


class PaperExecutionEngine:
    """Paper trading execution engine. Singleton per trading session."""

    def __init__(self, risk_engine: PortfolioRiskEngine = None):
        self.risk_engine = risk_engine or get_portfolio_engine()
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitoring = False
        self._signal_queue: List[Dict] = []

    def process_signal(self, signal: Dict) -> Dict:
        """Process a trading signal → risk check → open position (if approved).
        
        Args:
            signal: Signal dict from strategies.generate_signal()
        
        Returns:
            {accepted: bool, position_id: str, reason: str}
        """
        with self._lock:
            if signal.get("execution_eligible") is False:
                if not signal.get("paper_execution_eligible", False):
                    return {"accepted": False, "reason": "Signal failed structural validation"}
                from trading_mode import get_trading_mode
                if get_trading_mode().status()["mode"] != "PAPER":
                    return {"accepted": False, "reason": "Research candidates are restricted to PAPER mode"}
            symbol = signal.get("symbol", "")
            strategy = signal.get("strategy_key", "")
            legs = signal.get("legs", [])
            
            if not legs:
                return {"accepted": False, "reason": "No legs in signal"}
            
            # Get current quote for spot price
            try:
                quote = get_live_quote(symbol)
                spot = quote["ltp"]
            except Exception as e:
                return {"accepted": False, "reason": f"Failed to get quote: {e}"}
            
            # Determine position side from legs
            # For multi-leg: if net credit (sells > buys in premium terms) → SHORT
            # If net debit (buys > sells) → LONG
            # If equal count, use premium-weighted approach
            sell_premium = sum(l.get("premium", 0) for l in legs if l.get("action") == "SELL")
            buy_premium = sum(l.get("premium", 0) for l in legs if l.get("action") == "BUY")
            # SHORT if we collected more premium than we paid (net credit)
            side = "SHORT" if sell_premium > buy_premium else "LONG"
            
            # Get instrument config
            cfg = INSTRUMENTS.get(symbol)
            if not cfg:
                return {"accepted": False, "reason": f"Unknown symbol: {symbol}"}
            
            # Autonomous supervisor may provide a risk-sized quantity.  It must
            # remain a positive whole number of exchange lots.
            lot_size = int(cfg["lot_size"])
            requested_quantity = int(signal.get("quantity", lot_size) or lot_size)
            quantity = max(lot_size, (requested_quantity // lot_size) * lot_size)
            signal_price = float(signal.get("entry_price", 0) or 0)
            slippage_ticks = max(0, int(os.getenv("PAPER_SLIPPAGE_TICKS", "2")))
            entry_slippage = float(cfg["tick_size"]) * slippage_ticks
            entry_price = signal_price + entry_slippage if side == "LONG" else max(0.05, signal_price - entry_slippage)
            commission = max(0.0, float(os.getenv("PAPER_COMMISSION_PER_ORDER", "20")))
            stop_loss = signal.get("stop_loss", 0)
            take_profit = signal.get("target", 0)
            
            # Compute Greeks for the position — aggregate across ALL legs (not just first)
            # This properly handles multi-leg strategies (Iron Condor, Butterfly, etc.)
            t_to_expiry = 5 / 252
            r = 0.07
            sigma = cfg["volatility"]
            
            # Use ATM strike for representative pricing
            strike = spot
            # For multi-leg, use "MULTI" as option_type so check_stops doesn't try BS revaluation
            option_type = "MULTI" if len(legs) > 1 else legs[0].get("type", "CE")
            
            # Aggregate Greeks across all legs (net delta, gamma, theta, vega)
            net_delta = 0
            net_gamma = 0
            net_theta = 0
            net_vega = 0
            try:
                for leg in legs:
                    leg_strike = leg.get("strike", spot)
                    leg_type = leg.get("type", "CE")
                    leg_action = leg.get("action", "BUY")
                    sign = 1 if leg_action == "BUY" else -1
                    g = greeks_bundle(spot, leg_strike, t_to_expiry, r, sigma, leg_type)
                    net_delta += g["delta"] * sign
                    net_gamma += g["gamma"] * sign
                    net_theta += g["theta"] * sign
                    net_vega += g["vega"] * sign
                delta = net_delta
                gamma = net_gamma
                theta = net_theta
                vega = net_vega
            except Exception:
                delta = gamma = theta = vega = 0
            
            # Create Position object
            position_id = f"POS-{int(time.time())}-{random.randint(1000,9999)}"
            position = Position(
                id=position_id,
                symbol=symbol,
                strategy=strategy,
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,
                spot=spot,
                strike=strike,
                option_type=option_type,
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                stop_loss=stop_loss,
                take_profit=take_profit,
                unrealized_pnl=0,
                opened_at=datetime.now(timezone.utc).isoformat(),
                legs=legs,
                signal_price=signal_price,
                entry_slippage=entry_slippage,
                estimated_costs=commission * 2,
                regime_at_entry=str(signal.get("regime_at_entry", "UNKNOWN")),
                confidence_at_entry=float(signal.get("confidence", 0) or 0),
                ranking_score=float(signal.get("ranking_score", 0) or 0),
                paper_signal_id=str(signal.get("paper_signal_id", "")),
            )
            
            # Pre-trade risk check
            accepted, reason = self.risk_engine.add_position(position)
            
            if accepted:
                logger.trade(
                    "position_opened",
                    strategy=strategy,
                    symbol=symbol,
                    position_id=position_id,
                    side=side,
                    entry_price=entry_price,
                    quantity=quantity,
                )
                metrics.inc_counter("positions_opened_total", strategy=strategy, symbol=symbol, side=side)
                return {
                    "accepted": True,
                    "position_id": position_id,
                    "reason": "Position opened",
                    "side": side,
                    "entry_price": entry_price,
                    "signal_price": signal_price,
                    "entry_slippage": entry_slippage,
                    "estimated_costs": commission * 2,
                    "quantity": quantity,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                }
            else:
                logger.warning(
                    "position_rejected",
                    strategy=strategy,
                    symbol=symbol,
                    reason=reason,
                )
                metrics.inc_counter("positions_rejected_total", strategy=strategy, symbol=symbol, reason=reason[:50])
                return {
                    "accepted": False,
                    "position_id": None,
                    "reason": reason,
                }

    def close_position(self, position_id: str, exit_price: Optional[float] = None, reason: str = "MANUAL") -> Dict:
        """Close a position manually.
        
        Args:
            position_id: Position to close
            exit_price: Exit price (if None, uses current LTP)
            reason: Close reason (MANUAL, SL_HIT, TP_HIT, TIME_EXIT, KILL_SWITCH)
        """
        with self._lock:
            # Find position
            pos = next((p for p in self.risk_engine.positions if p.id == position_id), None)
            if not pos:
                return {"success": False, "error": "Position not found"}
            if exit_price is None:
                # For options, use current option premium (already updated by check_stops)
                # For non-options, use spot
                if pos.option_type in ("CE", "PE", "MULTI"):
                    exit_price = pos.current_price  # option premium
                else:
                    try:
                        quote = get_live_quote(pos.symbol)
                        exit_price = quote["ltp"]
                    except Exception:
                        exit_price = pos.current_price
            
            result = self.risk_engine.remove_position(position_id, exit_price, reason)
            
            if result.get("success"):
                logger.trade(
                    "position_closed",
                    strategy=pos.strategy,
                    symbol=pos.symbol,
                    position_id=position_id,
                    exit_price=exit_price,
                    pnl=result.get("pnl", 0),
                    reason=reason,
                )
                metrics.record_trade(pos.strategy, pos.symbol, result.get("pnl", 0))
                
                # Record in trade journal for post-trade analysis
                try:
                    from trade_journal import get_journal
                    journal = get_journal()
                    journal.record_trade({
                        "position_id": position_id,
                        "symbol": pos.symbol,
                        "strategy": pos.strategy,
                        "side": pos.side,
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "quantity": pos.quantity,
                        "pnl": result.get("pnl", 0),
                        "pnl_pct": round((result.get("pnl", 0) / (pos.entry_price * pos.quantity)) * 100, 2) if pos.entry_price and pos.quantity else 0,
                        "exit_reason": reason,
                        "entry_time": pos.opened_at,
                        "exit_time": datetime.now(timezone.utc).isoformat(),
                        "spot_at_entry": pos.spot,
                        "spot_at_exit": pos.spot,  # would need current spot here
                        "delta_at_entry": pos.delta,
                        "theta_at_entry": pos.theta,
                        "vega_at_entry": pos.vega,
                        "signal_price": pos.signal_price,
                        "entry_slippage": pos.entry_slippage,
                        "estimated_costs": pos.estimated_costs,
                        "regime_at_entry": pos.regime_at_entry,
                        "confidence_at_entry": pos.confidence_at_entry,
                        "ranking_score": pos.ranking_score,
                    })
                except Exception as e:
                    logger.error(f"Failed to record trade in journal: {e}")
                if pos.paper_signal_id:
                    try:
                        from paper_signal_journal import get_paper_signal_journal
                        get_paper_signal_journal().record_outcome(pos.paper_signal_id, "POSITION_CLOSED", {
                            "position_id": position_id, "pnl": result.get("pnl", 0),
                            "exit_price": exit_price, "exit_reason": reason,
                        })
                    except Exception as e:
                        logger.error(f"Failed to link paper signal outcome: {e}")
            
            return result

    def monitor_positions(self) -> List[Dict]:
        """Check all open positions for SL/TP breaches.
        
        Returns list of positions that were closed.
        """
        with self._lock:
            if not self.risk_engine.positions:
                return []
            
            # Get current quotes for all position symbols
            quotes = {}
            for pos in self.risk_engine.positions:
                if pos.symbol not in quotes:
                    try:
                        quote = get_live_quote(pos.symbol)
                        quotes[pos.symbol] = quote["ltp"]
                    except Exception:
                        pass
            
            # Check stops
            to_close = self.risk_engine.check_stops(quotes)
            
            closed = []
            for item in to_close:
                result = self.close_position(item["position_id"], item["exit_price"], item["reason"])
                if result.get("success"):
                    closed.append({
                        "position_id": item["position_id"],
                        "exit_price": item["exit_price"],
                        "reason": item["reason"],
                        "pnl": result.get("pnl", 0),
                    })
            
            return closed

    def start_monitoring(self, interval_seconds: int = 5) -> bool:
        """Start background monitoring thread.
        
        Checks all positions every `interval_seconds` for SL/TP breaches.
        """
        with self._lock:
            if self._monitoring:
                return False
            self._monitoring = True
            
            def monitor_loop():
                while self._monitoring:
                    try:
                        closed = self.monitor_positions()
                        for c in closed:
                            logger.risk(
                                f"Position auto-closed: {c['position_id']} ({c['reason']}) P&L ₹{c['pnl']:.0f}",
                                alert_level="WARNING" if c["pnl"] < 0 else "INFO",
                            )
                    except Exception as e:
                        logger.error(f"Monitor loop error: {e}")
                    time.sleep(interval_seconds)
            
            self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
            self._monitor_thread.start()
            logger.info("Position monitoring started", interval_seconds=interval_seconds)
            return True

    def stop_monitoring(self) -> bool:
        """Stop background monitoring."""
        with self._lock:
            self._monitoring = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=10)
                self._monitor_thread = None
            logger.info("Position monitoring stopped")
            return True

    def status(self) -> Dict:
        """Get execution engine status."""
        return {
            "monitoring_active": self._monitoring,
            "queue_length": len(self._signal_queue),
            "risk_engine_status": self.risk_engine.status(),
        }


# Singleton
_execution_engine: Optional[PaperExecutionEngine] = None

def get_execution_engine() -> PaperExecutionEngine:
    global _execution_engine
    if _execution_engine is None:
        _execution_engine = PaperExecutionEngine()
    return _execution_engine
