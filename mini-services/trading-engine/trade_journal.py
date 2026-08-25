"""
JARVIS Trade Journal + Post-Trade Analysis

Records every closed trade with full context (regime at entry, strategy, symbol,
entry/exit, P&L, hold time, exit reason). Provides analytics for the learning loop:
  - Win/loss attribution by strategy, symbol, regime, exit reason
  - Average hold time, expectancy per strategy
  - Best/worst performing combinations
  - Streak analysis (consecutive wins/losses)
  - Time-of-day analysis (which hours perform best)

This closes the learning loop: SIGNAL → DECISION → EXECUTION → RESULT → ANALYSIS → IMPROVEMENT.
"""
import math
import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np

from observability import logger


class TradeJournal:
    """Records and analyzes closed trades for the learning loop."""

    def __init__(self):
        self._lock = threading.RLock()
        self._trades: List[Dict] = []

    def record_trade(self, trade: Dict) -> None:
        """Record a closed trade with full context.
        
        Expected fields:
          - position_id, symbol, strategy, side
          - entry_price, exit_price, quantity
          - pnl, pnl_pct, exit_reason
          - entry_time, exit_time
          - regime_at_entry (optional)
          - confidence_at_entry (optional)
          - spot_at_entry, spot_at_exit (optional)
        """
        with self._lock:
            # Enrich with computed fields
            entry_time = self._parse_time(trade.get("entry_time"))
            exit_time = self._parse_time(trade.get("exit_time"))
            hold_seconds = (exit_time - entry_time).total_seconds() if entry_time and exit_time else 0
            
            enriched = {
                **trade,
                "hold_seconds": round(hold_seconds, 0),
                "hold_minutes": round(hold_seconds / 60, 1),
                "hold_hours": round(hold_seconds / 3600, 2),
                "is_win": trade.get("pnl", 0) > 0,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            self._trades.append(enriched)
            
            logger.trade(
                "Trade recorded in journal",
                strategy=trade.get("strategy", ""),
                symbol=trade.get("symbol", ""),
                pnl=trade.get("pnl", 0),
                exit_reason=trade.get("exit_reason", ""),
            )

    def _parse_time(self, time_str: Optional[str]) -> Optional[datetime]:
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def get_all_trades(self) -> List[Dict]:
        """Get all recorded trades."""
        with self._lock:
            return list(self._trades)

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get most recent trades."""
        with self._lock:
            return list(reversed(self._trades[-limit:]))

    def analyze(self) -> Dict:
        """Run full post-trade analysis.
        
        Returns:
          - Summary stats (total trades, win rate, avg P&L, expectancy)
          - Per-strategy breakdown
          - Per-symbol breakdown
          - Per-regime breakdown
          - Per-exit-reason breakdown
          - Streak analysis
          - Time analysis
        """
        with self._lock:
            trades = list(self._trades)

        if not trades:
            return {"status": "NO_TRADES", "message": "No trades recorded yet"}

        pnls = [t.get("pnl", 0) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        # Summary
        summary = {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(pnls) * 100, 2) if pnls else 0,
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(float(np.mean(pnls)), 2) if pnls else 0,
            "avg_win": round(float(np.mean(wins)), 2) if wins else 0,
            "avg_loss": round(float(np.mean(losses)), 2) if losses else 0,
            "largest_win": round(max(pnls), 2) if pnls else 0,
            "largest_loss": round(min(pnls), 2) if pnls else 0,
            "expectancy": round(float(np.mean(pnls)), 2) if pnls else 0,
            "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else 99.99,
        }

        # Per-strategy breakdown
        by_strategy = self._breakdown(trades, "strategy")
        # Per-symbol breakdown
        by_symbol = self._breakdown(trades, "symbol")
        # Per-regime breakdown
        by_regime = self._breakdown(trades, "regime_at_entry")
        # Per-exit-reason breakdown
        by_exit_reason = self._breakdown(trades, "exit_reason")
        # Per-side breakdown
        by_side = self._breakdown(trades, "side")

        # Streak analysis
        streaks = self._streak_analysis(trades)

        # Time analysis (which hours perform best)
        time_analysis = self._time_analysis(trades)

        # Hold time analysis
        hold_times = [t.get("hold_minutes", 0) for t in trades]
        hold_analysis = {
            "avg_hold_minutes": round(float(np.mean(hold_times)), 1) if hold_times else 0,
            "median_hold_minutes": round(float(np.median(hold_times)), 1) if hold_times else 0,
            "min_hold_minutes": round(min(hold_times), 1) if hold_times else 0,
            "max_hold_minutes": round(max(hold_times), 1) if hold_times else 0,
        }

        return {
            "summary": summary,
            "by_strategy": by_strategy,
            "by_symbol": by_symbol,
            "by_regime": by_regime,
            "by_exit_reason": by_exit_reason,
            "by_side": by_side,
            "streaks": streaks,
            "time_analysis": time_analysis,
            "hold_analysis": hold_analysis,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _breakdown(self, trades: List[Dict], key: str) -> Dict:
        """Break down trades by a key (strategy, symbol, etc.)."""
        groups = defaultdict(list)
        for t in trades:
            k = t.get(key, "UNKNOWN")
            groups[k].append(t.get("pnl", 0))

        result = {}
        for k, pnls in groups.items():
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]
            result[k] = {
                "trades": len(pnls),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(pnls) * 100, 1) if pnls else 0,
                "total_pnl": round(sum(pnls), 2),
                "avg_pnl": round(float(np.mean(pnls)), 2) if pnls else 0,
                "expectancy": round(float(np.mean(pnls)), 2) if pnls else 0,
            }
        return result

    def _streak_analysis(self, trades: List[Dict]) -> Dict:
        """Analyze consecutive win/loss streaks."""
        if not trades:
            return {}

        streaks = []
        current_type = None
        current_len = 0

        for t in trades:
            is_win = t.get("pnl", 0) > 0
            if current_type is None:
                current_type = "WIN" if is_win else "LOSS"
                current_len = 1
            elif (is_win and current_type == "WIN") or (not is_win and current_type == "LOSS"):
                current_len += 1
            else:
                streaks.append({"type": current_type, "length": current_len})
                current_type = "WIN" if is_win else "LOSS"
                current_len = 1
        if current_type:
            streaks.append({"type": current_type, "length": current_len})

        win_streaks = [s["length"] for s in streaks if s["type"] == "WIN"]
        loss_streaks = [s["length"] for s in streaks if s["type"] == "LOSS"]

        return {
            "max_win_streak": max(win_streaks) if win_streaks else 0,
            "max_loss_streak": max(loss_streaks) if loss_streaks else 0,
            "avg_win_streak": round(float(np.mean(win_streaks)), 1) if win_streaks else 0,
            "avg_loss_streak": round(float(np.mean(loss_streaks)), 1) if loss_streaks else 0,
            "current_streak": {"type": current_type, "length": current_len} if current_type else None,
        }

    def _time_analysis(self, trades: List[Dict]) -> Dict:
        """Analyze performance by hour of day."""
        hourly = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
        for t in trades:
            entry_time = self._parse_time(t.get("entry_time"))
            if entry_time:
                hour = entry_time.hour
                hourly[hour]["trades"] += 1
                if t.get("pnl", 0) > 0:
                    hourly[hour]["wins"] += 1
                hourly[hour]["pnl"] += t.get("pnl", 0)

        result = {}
        for hour, stats in sorted(hourly.items()):
            result[f"{hour:02d}:00"] = {
                "trades": stats["trades"],
                "win_rate": round(stats["wins"] / stats["trades"] * 100, 1) if stats["trades"] else 0,
                "total_pnl": round(stats["pnl"], 2),
            }
        return result

    def clear(self) -> int:
        """Clear all trades. Returns count cleared."""
        with self._lock:
            count = len(self._trades)
            self._trades.clear()
            return count


# Singleton
_journal: Optional[TradeJournal] = None

def get_journal() -> TradeJournal:
    global _journal
    if _journal is None:
        _journal = TradeJournal()
    return _journal
