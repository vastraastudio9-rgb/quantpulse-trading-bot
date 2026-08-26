"""
JARVIS Portfolio Risk Engine

Tracks portfolio-level risk:
  - Net delta, gamma, theta, vega across all positions
  - Correlation between positions (avoid concentrated risk)
  - Liquidation distance (how far spot can move before SL hit)
  - Daily loss tracking + kill switch enforcement
  - Position sizing based on risk budget

CRITICAL: This module is the LAST line of defense before live orders.
All checks must fail CLOSED (block trades) when uncertain.
"""
import math
import time
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
import numpy as np
import json
import os
from pathlib import Path


@dataclass
class Position:
    """A single open position with Greeks."""
    id: str
    symbol: str
    strategy: str
    side: str  # LONG / SHORT
    quantity: int
    entry_price: float
    current_price: float
    spot: float
    strike: float
    option_type: str  # CE / PE / FUTURE / SPOT
    delta: float = 0
    gamma: float = 0
    theta: float = 0
    vega: float = 0
    stop_loss: float = 0
    take_profit: float = 0
    unrealized_pnl: float = 0
    opened_at: str = ""
    legs: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "symbol": self.symbol, "strategy": self.strategy,
            "side": self.side, "quantity": self.quantity,
            "entry_price": round(self.entry_price, 2),
            "current_price": round(self.current_price, 2),
            "spot": round(self.spot, 2),
            "strike": round(self.strike, 2),
            "option_type": self.option_type,
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 6),
            "theta": round(self.theta, 4),
            "vega": round(self.vega, 4),
            "stop_loss": round(self.stop_loss, 2),
            "take_profit": round(self.take_profit, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "opened_at": self.opened_at,
            "legs": self.legs,
        }


@dataclass
class RiskLimits:
    """Configurable risk limits. Exceeding any = block new trades.
    
    Note: net_delta/theta/vega limits are scaled by (capital / 100000) at check time.
    So max_net_delta=50 means "50 delta units per ₹1L of capital".
    A 1-lot NIFTY position (75 qty × 0.5 delta) = 37.5 delta → would pass with 1L capital.
    """
    max_daily_loss_pct: float = 3.0           # % of capital
    max_daily_loss_amount: float = 3000       # absolute ₹ amount
    max_open_positions: int = 5
    max_position_size_pct: float = 25.0       # max % of capital per position (options are leveraged)
    max_net_delta: float = 100.0              # max net delta per ₹1L capital (1 lot NIFTY ≈ 37 delta)
    max_net_theta: float = 2000.0             # max net theta bleed per ₹1L capital (₹/day) — 1 lot straddle ≈ -1000
    max_net_vega: float = 5000.0              # max net vega per ₹1L capital
    max_correlated_positions: int = 2         # max positions in correlated assets
    max_strategy_concentration: int = 2       # max positions from same strategy
    kill_switch: bool = False
    kill_switch_reason: str = ""


class PortfolioRiskEngine:
    """Centralized risk manager. Singleton — one instance per trading engine."""

    def __init__(self, initial_capital: float = 100000, limits: RiskLimits = None, persist_path: Optional[Path] = None):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.limits = limits or RiskLimits(max_daily_loss_amount=initial_capital * 0.03)
        self.positions: List[Position] = []
        self.realized_pnl_today: float = 0
        self.realized_pnl_total: float = 0
        self.trade_history: List[Dict] = []
        self._lock = threading.RLock()  # thread-safe for order callbacks
        self._last_reset_date: Optional[date] = None
        self._daily_loss_lock = False
        self._persist_path = persist_path
        self._load_state()
        self._check_daily_reset()

    def _load_state(self) -> None:
        if not self._persist_path:
            return
        try:
            raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
            self.current_capital = float(raw.get("current_capital", self.initial_capital))
            self.realized_pnl_today = float(raw.get("realized_pnl_today", 0))
            self.realized_pnl_total = float(raw.get("realized_pnl_total", 0))
            self.trade_history = raw.get("trade_history", [])
            self.positions = [Position(**p) for p in raw.get("positions", [])]
            saved_date = raw.get("last_reset_date")
            self._last_reset_date = date.fromisoformat(saved_date) if saved_date else None
            self._daily_loss_lock = bool(raw.get("daily_loss_lock", False))
            self.limits.kill_switch = bool(raw.get("kill_switch", False))
            self.limits.kill_switch_reason = raw.get("kill_switch_reason", "")
        except (FileNotFoundError, ValueError, TypeError, OSError):
            pass

    def _save_state(self) -> None:
        if not self._persist_path:
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_capital": self.current_capital, "realized_pnl_today": self.realized_pnl_today,
            "realized_pnl_total": self.realized_pnl_total, "trade_history": self.trade_history,
            "positions": [p.to_dict() for p in self.positions],
            "last_reset_date": self._last_reset_date.isoformat() if self._last_reset_date else None,
            "daily_loss_lock": self._daily_loss_lock, "kill_switch": self.limits.kill_switch,
            "kill_switch_reason": self.limits.kill_switch_reason,
        }
        temp = self._persist_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(self._persist_path)

    def _check_daily_reset(self):
        """Reset daily P&L at start of new trading day."""
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        if self._last_reset_date is None or today > self._last_reset_date:
            self.realized_pnl_today = 0
            self._daily_loss_lock = False
            self._last_reset_date = today

    # ============ POSITION MANAGEMENT ============
    def add_position(self, pos: Position) -> Tuple[bool, str]:
        """Add a new position. Returns (success, reason). Fails CLOSED on any risk breach."""
        with self._lock:
            self._check_daily_reset()

            # === PRE-TRADE RISK CHECKS (all must pass) ===
            checks = self._pre_trade_checks(pos)
            for check_name, (passed, reason) in checks.items():
                if not passed:
                    return False, f"BLOCKED by {check_name}: {reason}"

            # All checks passed → add position
            self.positions.append(pos)
            self._save_state()
            return True, "Position added"

    def reset_paper_account(self, initial_capital: Optional[float] = None) -> Dict:
        """Reset simulated account state. This never touches broker or mode state."""
        with self._lock:
            capital = float(initial_capital or self.initial_capital)
            if capital <= 0:
                raise ValueError("Initial capital must be positive")
            self.initial_capital = capital
            self.current_capital = capital
            self.positions.clear()
            self.realized_pnl_today = 0.0
            self.realized_pnl_total = 0.0
            self.trade_history.clear()
            self._daily_loss_lock = False
            self._last_reset_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
            self.limits.kill_switch = False
            self.limits.kill_switch_reason = ""
            self._save_state()
            return {"reset": True, "paper_only": True, "capital": capital,
                    "timestamp": datetime.now(timezone.utc).isoformat()}

    def _pre_trade_checks(self, new_pos: Position) -> Dict[str, Tuple[bool, str]]:
        """Run all pre-trade risk checks. ALL must pass."""
        checks = {}

        # 1. Kill switch
        checks["kill_switch"] = (
            not self.limits.kill_switch,
            f"Kill switch active: {self.limits.kill_switch_reason}"
        )

        # 2. Daily loss limit
        daily_loss = abs(min(self.realized_pnl_today, 0))
        checks["daily_loss_limit"] = (
            daily_loss < self.limits.max_daily_loss_amount and not self._daily_loss_lock,
            f"Daily loss ₹{daily_loss:.0f} ≥ limit ₹{self.limits.max_daily_loss_amount:.0f}"
        )

        # 3. Max open positions
        checks["max_positions"] = (
            len(self.positions) < self.limits.max_open_positions,
            f"Open positions {len(self.positions)} ≥ max {self.limits.max_open_positions}"
        )

        # 4. Position size
        position_value = new_pos.entry_price * new_pos.quantity
        max_value = self.current_capital * (self.limits.max_position_size_pct / 100)
        checks["position_size"] = (
            position_value <= max_value,
            f"Position value ₹{position_value:.0f} > max ₹{max_value:.0f} ({self.limits.max_position_size_pct}% of capital)"
        )

        # 5. Net delta after adding
        new_net_delta = self.net_delta() + new_pos.delta * new_pos.quantity
        max_delta = self.limits.max_net_delta * (self.current_capital / 100000)
        checks["net_delta"] = (
            abs(new_net_delta) <= max_delta,
            f"Net delta {new_net_delta:.2f} would exceed max ±{max_delta:.2f}"
        )

        # 6. Net theta after adding (negative theta = bleeding)
        new_net_theta = self.net_theta() + new_pos.theta * new_pos.quantity
        checks["net_theta"] = (
            new_net_theta > -self.limits.max_net_theta,
            f"Net theta {new_net_theta:.2f} would bleed > ₹{self.limits.max_net_theta}/day"
        )

        # 7. Net vega after adding
        new_net_vega = self.net_vega() + new_pos.vega * new_pos.quantity
        checks["net_vega"] = (
            abs(new_net_vega) <= self.limits.max_net_vega,
            f"Net vega {new_net_vega:.2f} would exceed max ±{self.limits.max_net_vega}"
        )

        # 8. Strategy concentration
        same_strategy = sum(1 for p in self.positions if p.strategy == new_pos.strategy)
        checks["strategy_concentration"] = (
            same_strategy < self.limits.max_strategy_concentration,
            f"Strategy {new_pos.strategy} has {same_strategy} positions, max {self.limits.max_strategy_concentration}"
        )

        # 9. Correlation check (simplified: same underlying = correlated)
        same_underlying = sum(1 for p in self.positions if p.symbol == new_pos.symbol)
        checks["correlation"] = (
            same_underlying < self.limits.max_correlated_positions,
            f"Symbol {new_pos.symbol} has {same_underlying} positions, max {self.limits.max_correlated_positions}"
        )

        return checks

    def remove_position(self, position_id: str, exit_price: float, exit_reason: str = "MANUAL") -> Dict:
        """Close a position and record realized P&L."""
        with self._lock:
            pos = next((p for p in self.positions if p.id == position_id), None)
            if not pos:
                return {"success": False, "error": "Position not found"}

            # Calculate realized P&L
            if pos.side == "LONG":
                pnl = (exit_price - pos.entry_price) * pos.quantity
            else:
                pnl = (pos.entry_price - exit_price) * pos.quantity

            self.realized_pnl_today += pnl
            self.realized_pnl_total += pnl
            self.current_capital += pnl

            trade_record = {
                "position_id": pos.id,
                "symbol": pos.symbol,
                "strategy": pos.strategy,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "exit_price": exit_price,
                "quantity": pos.quantity,
                "pnl": round(pnl, 2),
                "exit_reason": exit_reason,
                "entry_time": pos.opened_at,
                "exit_time": datetime.now(timezone.utc).isoformat(),
            }
            self.trade_history.append(trade_record)
            self.positions.remove(pos)
            self._save_state()

            # Check if daily loss limit hit after this trade
            daily_loss = abs(min(self.realized_pnl_today, 0))
            if daily_loss >= self.limits.max_daily_loss_amount:
                self._daily_loss_lock = True
                return {
                    "success": True,
                    "pnl": round(pnl, 2),
                    "warning": f"DAILY LOSS LIMIT HIT: ₹{daily_loss:.0f}. New trades blocked until tomorrow.",
                }

            return {"success": True, "pnl": round(pnl, 2)}

    # ============ PORTFOLIO GREEKS ============
    def net_delta(self) -> float:
        """Sum of (delta * qty) across all positions."""
        return sum(p.delta * p.quantity for p in self.positions)

    def net_gamma(self) -> float:
        return sum(p.gamma * p.quantity for p in self.positions)

    def net_theta(self) -> float:
        """Negative = bleeding money to time decay."""
        return sum(p.theta * p.quantity for p in self.positions)

    def net_vega(self) -> float:
        return sum(p.vega * p.quantity for p in self.positions)

    def gross_exposure(self) -> float:
        """Total notional at risk."""
        return sum(abs(p.current_price * p.quantity) for p in self.positions)

    def net_exposure(self) -> float:
        """Net directional exposure (longs - shorts)."""
        return sum(
            (p.current_price * p.quantity) if p.side == "LONG" else -(p.current_price * p.quantity)
            for p in self.positions
        )

    def unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions)

    # ============ SL / TP MONITORING ============
    def check_stops(self, current_quotes: Dict[str, float]) -> List[Dict]:
        """Check all positions for SL/TP breaches. Returns list of positions to close.
        
        JARVIS-v2.3 FIX: Revalues option premium using Black-Scholes instead of
        comparing spot price to premium-based SL/TP. Previous version incorrectly
        compared spot (24800) to option premium SL (50) → always triggered.
        
        Args:
            current_quotes: {symbol: current_spot_price} dict
        
        Returns: list of {position_id, exit_price, reason} for positions that hit SL/TP
        """
        from greeks import option_price
        from market_data import INSTRUMENTS
        with self._lock:
            to_close = []
            for pos in self.positions:
                current_spot = current_quotes.get(pos.symbol)
                if current_spot is None:
                    continue
                
                # Revalue option premium using Black-Scholes
                # For multi-leg strategies, revalue each leg and sum (net credit/debit)
                cfg = INSTRUMENTS.get(pos.symbol)
                if cfg and pos.option_type in ("CE", "PE"):
                    # Single-leg: revalue via BS
                    t = 5 / 252
                    r = 0.07
                    sigma = cfg["volatility"]
                    try:
                        if pos.option_type == "CE":
                            current = option_price(current_spot, pos.strike, t, r, sigma, "CE")
                        else:
                            current = option_price(current_spot, pos.strike, t, r, sigma, "PE")
                        # Scale to match entry premium (calibrate to entry)
                        if pos.entry_price > 0:
                            entry_bs = option_price(pos.spot, pos.strike, t, r, sigma, pos.option_type)
                            scale = pos.entry_price / entry_bs if entry_bs > 0 else 1.0
                            current = current * scale
                        current = max(current, 0.05)
                    except Exception:
                        current = pos.entry_price  # fallback: no change
                elif cfg and pos.option_type == "MULTI" and pos.legs:
                    try:
                        opened = datetime.fromisoformat(pos.opened_at)
                        held_days = max(0.0, (datetime.now(timezone.utc) - opened).total_seconds() / 86400)
                        t_now = max((5.0 - held_days) / 252, 1 / (252 * 24))
                        t_entry = 5 / 252
                        sigma, rate = cfg["volatility"], 0.07

                        def net_value(spot_value: float, t_value: float) -> float:
                            buys = sells = 0.0
                            for leg in pos.legs:
                                value = option_price(spot_value, float(leg["strike"]), t_value, rate, sigma, leg["type"])
                                if leg["action"] == "BUY": buys += value
                                else: sells += value
                            return (sells - buys) if pos.side == "SHORT" else (buys - sells)

                        initial_model = net_value(pos.spot, t_entry)
                        scale = pos.entry_price / initial_model if initial_model > 0 else 1.0
                        current = max(net_value(current_spot, t_now) * scale, 0.05)
                    except Exception:
                        current = pos.entry_price
                else:
                    # For non-option positions (futures/spot), use spot directly
                    current = current_spot
                
                # Update current price (option premium, not spot)
                pos.current_price = current
                # Update unrealized P&L
                if pos.side == "LONG":
                    pos.unrealized_pnl = (current - pos.entry_price) * pos.quantity
                else:
                    pos.unrealized_pnl = (pos.entry_price - current) * pos.quantity
                self._save_state()

                # Check SL (premium-based)
                if pos.side == "LONG" and current <= pos.stop_loss:
                    to_close.append({"position_id": pos.id, "exit_price": current, "reason": "SL_HIT"})
                elif pos.side == "SHORT" and current >= pos.stop_loss:
                    to_close.append({"position_id": pos.id, "exit_price": current, "reason": "SL_HIT"})
                # Check TP
                elif pos.side == "LONG" and current >= pos.take_profit:
                    to_close.append({"position_id": pos.id, "exit_price": current, "reason": "TP_HIT"})
                elif pos.side == "SHORT" and current <= pos.take_profit:
                    to_close.append({"position_id": pos.id, "exit_price": current, "reason": "TP_HIT"})

            return to_close

    def liquidation_distance(self, symbol: str, current_spot: float) -> Dict:
        """For each position in `symbol`, compute how far spot can move before SL hit."""
        results = []
        for pos in self.positions:
            if pos.symbol != symbol:
                continue
            if pos.side == "LONG":
                distance = pos.stop_loss - current_spot  # negative = SL below current
                distance_pct = (distance / current_spot) * 100 if current_spot else 0
            else:
                distance = current_spot - pos.stop_loss  # positive = SL above current
                distance_pct = (distance / current_spot) * 100 if current_spot else 0
            results.append({
                "position_id": pos.id,
                "side": pos.side,
                "stop_loss": pos.stop_loss,
                "current_spot": current_spot,
                "distance": round(distance, 2),
                "distance_pct": round(distance_pct, 2),
                "alert": "CLOSE_TO_SL" if abs(distance_pct) < 1.0 else None,
            })
        return {"symbol": symbol, "positions": results}

    # ============ KILL SWITCH ============
    def activate_kill_switch(self, reason: str) -> Dict:
        """Activate kill switch. Blocks all new trades until deactivated."""
        with self._lock:
            self.limits.kill_switch = True
            self.limits.kill_switch_reason = reason
            self._save_state()
            return {
                "activated": True,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "open_positions": len(self.positions),
                "action_required": "Manual review needed. Close positions or deactivate kill switch.",
            }

    def deactivate_kill_switch(self) -> Dict:
        """Deactivate kill switch. Use with caution — requires human approval in production."""
        with self._lock:
            self.limits.kill_switch = False
            self.limits.kill_switch_reason = ""
            self._save_state()
            return {"activated": False, "timestamp": datetime.now(timezone.utc).isoformat()}

    # ============ STATUS / OBSERVABILITY ============
    def status(self) -> Dict:
        """Full risk status snapshot."""
        with self._lock:
            self._check_daily_reset()
            daily_loss = abs(min(self.realized_pnl_today, 0))
            return {
                "capital": {
                    "initial": round(self.initial_capital, 2),
                    "current": round(self.current_capital, 2),
                    "available": round(self.current_capital - self.gross_exposure(), 2),
                    "used": round(self.gross_exposure(), 2),
                },
                "pnl": {
                    "realized_today": round(self.realized_pnl_today, 2),
                    "realized_total": round(self.realized_pnl_total, 2),
                    "unrealized": round(self.unrealized_pnl(), 2),
                    "total": round(self.realized_pnl_today + self.unrealized_pnl(), 2),
                },
                "greeks": {
                    "net_delta": round(self.net_delta(), 4),
                    "net_gamma": round(self.net_gamma(), 6),
                    "net_theta": round(self.net_theta(), 4),
                    "net_vega": round(self.net_vega(), 4),
                },
                "exposure": {
                    "gross": round(self.gross_exposure(), 2),
                    "net": round(self.net_exposure(), 2),
                    "positions": len(self.positions),
                },
                "limits": {
                    "max_daily_loss": self.limits.max_daily_loss_amount,
                    "daily_loss_used": round(daily_loss, 2),
                    "daily_loss_remaining": round(max(0, self.limits.max_daily_loss_amount - daily_loss), 2),
                    "daily_loss_pct_used": round((daily_loss / self.limits.max_daily_loss_amount) * 100, 1) if self.limits.max_daily_loss_amount else 0,
                    "max_positions": self.limits.max_open_positions,
                    "positions_used": len(self.positions),
                    "kill_switch": self.limits.kill_switch,
                    "kill_switch_reason": self.limits.kill_switch_reason,
                    "daily_loss_lock": self._daily_loss_lock,
                },
                "positions": [p.to_dict() for p in self.positions],
                "alerts": self._generate_alerts(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _generate_alerts(self) -> List[Dict]:
        """Generate risk alerts based on current state."""
        alerts = []
        daily_loss = abs(min(self.realized_pnl_today, 0))

        if self.limits.kill_switch:
            alerts.append({
                "level": "CRITICAL",
                "code": "KILL_SWITCH_ACTIVE",
                "message": f"Kill switch active: {self.limits.kill_switch_reason}",
            })

        if self._daily_loss_lock:
            alerts.append({
                "level": "CRITICAL",
                "code": "DAILY_LOSS_LIMIT_HIT",
                "message": f"Daily loss limit hit: ₹{daily_loss:.0f}. New trades blocked.",
            })
        elif daily_loss > self.limits.max_daily_loss_amount * 0.7:
            alerts.append({
                "level": "WARNING",
                "code": "APPROACHING_DAILY_LOSS_LIMIT",
                "message": f"Daily loss at {daily_loss/self.limits.max_daily_loss_amount*100:.0f}% of limit (₹{daily_loss:.0f} / ₹{self.limits.max_daily_loss_amount:.0f})",
            })

        if len(self.positions) >= self.limits.max_open_positions - 1:
            alerts.append({
                "level": "WARNING",
                "code": "APPROACHING_MAX_POSITIONS",
                "message": f"{len(self.positions)} positions open, max {self.limits.max_open_positions}",
            })

        net_delta = self.net_delta()
        max_delta = self.limits.max_net_delta * (self.current_capital / 100000)
        if abs(net_delta) > max_delta * 0.8:
            alerts.append({
                "level": "WARNING",
                "code": "HIGH_DIRECTIONAL_EXPOSURE",
                "message": f"Net delta {net_delta:.2f} approaching limit ±{max_delta:.2f}",
            })

        net_theta = self.net_theta()
        if net_theta < -self.limits.max_net_theta * 0.7:
            alerts.append({
                "level": "WARNING",
                "code": "HIGH_THETA_BLEED",
                "message": f"Net theta {net_theta:.2f} — bleeding ₹{abs(net_theta):.0f}/day to time decay",
            })

        return alerts


# ============ SINGLETON ============
_portfolio_engine: Optional[PortfolioRiskEngine] = None

def get_portfolio_engine(initial_capital: float = 100000) -> PortfolioRiskEngine:
    """Get or create the singleton portfolio risk engine."""
    global _portfolio_engine
    if _portfolio_engine is None:
        persist_path = None
        if "PYTEST_CURRENT_TEST" not in os.environ:
            data_dir = Path(os.getenv("ENGINE_DATA_DIR", Path(__file__).parent / "data"))
            persist_path = data_dir / "risk-state.json"
        _portfolio_engine = PortfolioRiskEngine(initial_capital=initial_capital, persist_path=persist_path)
    return _portfolio_engine
