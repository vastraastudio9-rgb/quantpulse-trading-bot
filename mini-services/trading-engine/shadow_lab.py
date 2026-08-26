"""Persistent, execution-isolated shadow paper laboratory for strategy diversity."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


CREDIT_STRATEGIES = {"STRADDLE_SELL", "STRANGLE_SELL", "IRON_CONDOR", "IRON_BUTTERFLY", "VRP_HARVEST"}


class ShadowPaperLab:
    """Simulate one-lot strategy paths without importing any execution engine."""

    def __init__(self, path: Optional[Path] = None, max_hold_minutes: int = 60):
        base = Path(os.getenv("JARVIS_STATE_DIR") or Path(__file__).parent / "data")
        self.path = Path(path or base / "shadow_lab.json")
        self.max_hold_minutes = max(5, int(max_hold_minutes))
        self._lock = threading.RLock()
        self.state = self._load()

    def _load(self) -> Dict:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("open"), dict) and isinstance(value.get("trades"), list):
                return value
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass
        return {"version": 1, "open": {}, "trades": [], "observations": 0, "last_cycle": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        temp.replace(self.path)

    @staticmethod
    def _time(value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    def observe(self, signal: Dict, regime: str, compatible: bool, lot_size: int, tick_size: float,
                now: Optional[datetime] = None) -> Dict:
        """Mark/close/open a shadow path. This method has no broker or portfolio dependency."""
        current_time = now or datetime.now(timezone.utc)
        strategy, symbol = str(signal.get("strategy_key", "")), str(signal.get("symbol", ""))
        key = f"{strategy}:{symbol}"
        mark = float(signal.get("entry_price", 0) or 0)
        if not strategy or not symbol or mark <= 0 or signal.get("paper_execution_eligible") is not True:
            return {"accepted": False, "reason": "Invalid shadow observation"}
        with self._lock:
            self.state["observations"] = int(self.state.get("observations", 0)) + 1
            closed = None
            position = self.state["open"].get(key)
            if position:
                age_minutes = (current_time - self._time(position["opened_at"])).total_seconds() / 60
                is_credit = bool(position["is_credit"])
                stop_hit = mark >= position["stop_loss"] if is_credit else mark <= position["stop_loss"]
                target_hit = mark <= position["target"] if is_credit else mark >= position["target"]
                reason = "STOP_HIT" if stop_hit else "TARGET_HIT" if target_hit else "TIME_EXIT" if age_minutes >= self.max_hold_minutes else None
                if reason:
                    direction = -1 if is_credit else 1
                    gross = (mark - position["entry_price"]) * direction * position["quantity"]
                    pnl = round(gross - position["estimated_costs"], 2)
                    closed = {**position, "exit_price": mark, "closed_at": current_time.isoformat(),
                              "exit_reason": reason, "pnl": pnl, "win": pnl > 0}
                    self.state["trades"].append(closed)
                    self.state["trades"] = self.state["trades"][-5000:]
                    del self.state["open"][key]
                else:
                    position["current_price"] = mark
                    position["updated_at"] = current_time.isoformat()
            opened = None
            if key not in self.state["open"] and closed is None:
                legs = max(1, len(signal.get("legs") or []))
                quantity = max(1, int(lot_size))
                slippage = max(0.0, float(tick_size)) * 2 * legs
                is_credit = strategy in CREDIT_STRATEGIES
                entry = max(.01, mark - slippage if is_credit else mark + slippage)
                costs = 20.0 * 2 * legs + slippage * quantity * 2
                opened = {
                    "key": key, "strategy": strategy, "symbol": symbol, "regime": regime,
                    "compatible_regime": bool(compatible), "is_credit": is_credit,
                    "entry_price": round(entry, 4), "current_price": mark,
                    "stop_loss": float(signal.get("stop_loss", 0)), "target": float(signal.get("target", 0)),
                    "confidence": float(signal.get("confidence", 0)), "quantity": quantity,
                    "estimated_costs": round(costs, 2), "opened_at": current_time.isoformat(),
                    "evidence_grade": "SHADOW_MODEL", "paper_only": True, "live_eligible": False,
                }
                self.state["open"][key] = opened
            self.state["last_cycle"] = current_time.isoformat()
            self._save()
            return {"accepted": True, "opened": opened, "closed": closed,
                    "paper_only": True, "live_eligible": False}

    def status(self) -> Dict:
        with self._lock:
            trades = list(self.state["trades"])
            open_positions = list(self.state["open"].values())
        strategies = sorted({item["strategy"] for item in trades + open_positions})
        breakdown = {}
        for strategy in strategies:
            closed = [item for item in trades if item["strategy"] == strategy]
            opened = [item for item in open_positions if item["strategy"] == strategy]
            wins = [item for item in closed if item["pnl"] > 0]
            losses = [item for item in closed if item["pnl"] < 0]
            gross_profit = sum(item["pnl"] for item in wins)
            gross_loss = abs(sum(item["pnl"] for item in losses))
            breakdown[strategy] = {
                "closed": len(closed), "open": len(opened), "wins": len(wins),
                "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
                "pnl": round(sum(item["pnl"] for item in closed), 2),
                "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else (None if gross_profit else 0),
                "compatible_trades": sum(1 for item in closed if item.get("compatible_regime")),
                "counterfactual_trades": sum(1 for item in closed if not item.get("compatible_regime")),
            }
        return {"status": "SHADOW_ONLY", "observations": int(self.state.get("observations", 0)),
                "open_positions": len(open_positions), "closed_trades": len(trades),
                "by_strategy": breakdown, "last_cycle": self.state.get("last_cycle"),
                "limitations": ["Model-derived option marks", "Not eligible for strategy promotion"],
                "paper_only": True, "live_eligible": False}

    def closed_trades(self) -> list[Dict]:
        """Return a defensive copy for research analytics only."""
        with self._lock:
            return [dict(item) for item in self.state["trades"]]


_lab: Optional[ShadowPaperLab] = None


def get_shadow_lab() -> ShadowPaperLab:
    global _lab
    if _lab is None:
        _lab = ShadowPaperLab()
    return _lab
