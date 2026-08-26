"""JARVIS autonomous operations supervisor.

This module coordinates unattended PAPER trading.  It deliberately never changes
the trading mode and never submits live orders; live activation remains a human
operation guarded by trading_mode.py.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, time as clock_time, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from market_data import INSTRUMENTS, get_live_quote
from observability import logger, metrics


IST = ZoneInfo("Asia/Kolkata")


def automation_readiness(checks: List[Dict]) -> Dict:
    """Calculate honest paper/R&D automation readiness; LIVE is intentionally excluded."""
    total = len(checks)
    passed = sum(1 for check in checks if check.get("ok"))
    score = round((passed / total) * 100) if total else 0
    return {
        "score_pct": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "blockers": [check["label"] for check in checks if not check.get("ok")],
        "scope": "PAPER_RND_AUTOMATION",
        "live_execution_automated": False,
    }


@dataclass
class AutonomyConfig:
    enabled: bool = False
    heartbeat_seconds: int = 10
    max_quote_age_seconds: int = 45
    max_spread_pct: float = 2.5
    risk_per_trade_pct: float = 0.5
    max_hold_minutes: int = 360
    trailing_trigger_pct: float = 15.0
    trailing_lock_pct: float = 5.0
    min_promotion_trades: int = 30
    min_win_rate: float = 45.0
    min_profit_factor: float = 1.15
    max_promotion_drawdown_pct: float = 12.0
    auto_recover: bool = True
    reconcile_enabled: bool = True
    daily_workflow_enabled: bool = True


class AutonomySupervisor:
    """Fail-closed orchestration for all autonomous PAPER operations."""

    def __init__(self, state_dir: Optional[Path] = None):
        base = state_dir or Path(os.getenv("JARVIS_STATE_DIR") or Path(__file__).parent / "data")
        self.state_dir = Path(base)
        self.state_path = self.state_dir / "autonomy_state.json"
        self.decisions_path = self.state_dir / "decision_journal.jsonl"
        self.reports_path = self.state_dir / "daily_reports.jsonl"
        self.config = AutonomyConfig()
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_heartbeat: Optional[str] = None
        self._last_health: Dict = {"status": "NOT_RUN"}
        self._last_reconciliation: Dict = {"status": "NOT_RUN"}
        self._last_workflow_phase = "STOPPED"
        self._last_report_date: Optional[str] = None
        self._alerts: List[Dict] = []
        self._recovery_count = 0
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            allowed = set(AutonomyConfig.__dataclass_fields__)
            self.config = AutonomyConfig(**{k: v for k, v in raw.get("config", {}).items() if k in allowed})
            self._last_report_date = raw.get("last_report_date")
            self._recovery_count = int(raw.get("recovery_count", 0))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass

    def _save(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "config": asdict(self.config),
            "last_report_date": self._last_report_date,
            "recovery_count": self._recovery_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # A heartbeat and an operator request can persist concurrently. Use a
        # per-thread temporary file so atomic replacement is race-free on Windows.
        temp = self.state_path.with_name(f"{self.state_path.name}.{threading.get_ident()}.tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def configure(self, values: Dict) -> Dict:
        with self._lock:
            for key, value in values.items():
                if key == "enabled" or not hasattr(self.config, key):
                    continue
                setattr(self.config, key, value)
            self.config.heartbeat_seconds = max(5, min(60, int(self.config.heartbeat_seconds)))
            self.config.risk_per_trade_pct = max(0.1, min(1.0, float(self.config.risk_per_trade_pct)))
            self.config.max_hold_minutes = max(5, min(1440, int(self.config.max_hold_minutes)))
            self._save()
        return self.status()

    def start(self) -> Dict:
        with self._lock:
            self.config.enabled = True
            if self._running:
                self._save()
                return {"started": False, "running": True, "message": "Autonomy already running"}
            self._save()
            self._running = True
            self._thread = threading.Thread(target=self._loop, name="jarvis-autonomy", daemon=True)
            self._thread.start()
        self.record_decision("AUTONOMY_STARTED", "SYSTEM", "Unattended paper operations enabled", {})
        return {"started": True, "running": True, "paper_only": True}

    def stop(self) -> Dict:
        with self._lock:
            self._running = False
            self.config.enabled = False
            self._save()
        self.record_decision("AUTONOMY_STOPPED", "SYSTEM", "Autonomy supervisor stopped", {})
        return {"stopped": True, "running": False}

    def _loop(self) -> None:
        while self._running:
            try:
                self.run_cycle()
            except Exception as exc:
                self._alert("CRITICAL", "SUPERVISOR_ERROR", str(exc))
                logger.error(f"Autonomy supervisor cycle failed: {exc}")
            time.sleep(self.config.heartbeat_seconds)

    def run_cycle(self) -> Dict:
        self._last_heartbeat = datetime.now(timezone.utc).isoformat()
        health = self.check_health()
        if health["safe_to_trade"]:
            self.manage_lifecycle()
            if self.config.reconcile_enabled:
                self.reconcile()
            if self.config.auto_recover:
                self.recover_workers()
        self.run_daily_workflow()
        metrics.inc_counter("autonomy_heartbeats_total", status=health["status"])
        return {"health": health, "phase": self._last_workflow_phase}

    def check_health(self) -> Dict:
        checks: List[Dict] = []
        for symbol in INSTRUMENTS:
            try:
                started = time.monotonic()
                quote = get_live_quote(symbol)
                latency_ms = round((time.monotonic() - started) * 1000, 1)
                ltp = float(quote.get("ltp", 0))
                bid = float(quote.get("bid", ltp) or ltp)
                ask = float(quote.get("ask", ltp) or ltp)
                spread_pct = ((ask - bid) / ltp * 100) if ltp > 0 else 999
                healthy = ltp > 0 and spread_pct <= self.config.max_spread_pct
                checks.append({"symbol": symbol, "healthy": healthy, "ltp": ltp,
                               "spread_pct": round(spread_pct, 3), "latency_ms": latency_ms})
            except Exception as exc:
                checks.append({"symbol": symbol, "healthy": False, "error": str(exc)})
        unhealthy = [c for c in checks if not c["healthy"]]
        status = "OK" if not unhealthy else ("DEGRADED" if len(unhealthy) < len(checks) else "FAILED")
        self._last_health = {
            "status": status,
            "safe_to_trade": status == "OK",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if unhealthy:
            self._alert("CRITICAL", "MARKET_DATA_UNHEALTHY", f"{len(unhealthy)} quote feeds unhealthy")
        return self._last_health

    def strategy_governance(self) -> Dict:
        """Enable strategies by evidence; sparse history stays paper-only, not disabled."""
        from trade_journal import get_journal
        analysis = get_journal().analyze()
        breakdown = analysis.get("by_strategy", {}) if isinstance(analysis, dict) else {}
        decisions = {}
        for key in INSTRUMENTS:  # no-op to keep deterministic iteration elsewhere
            _ = key
        from strategies import STRATEGIES
        for key in STRATEGIES:
            stats = breakdown.get(key, {})
            trades = int(stats.get("trades", stats.get("count", 0)) or 0)
            win_rate = float(stats.get("win_rate", 0) or 0)
            profit_factor = float(stats.get("profit_factor", 0) or 0)
            if trades < self.config.min_promotion_trades:
                state, reason = "PAPER_LEARNING", f"Need {self.config.min_promotion_trades - trades} more closed trades"
            elif win_rate >= self.config.min_win_rate and profit_factor >= self.config.min_profit_factor:
                state, reason = "PAPER_VALIDATED", "Journal thresholds passed"
            else:
                state, reason = "QUARANTINED", "Performance thresholds failed"
            decisions[key] = {"state": state, "reason": reason, "trades": trades,
                              "win_rate": win_rate, "profit_factor": profit_factor}
        return {"strategies": decisions, "timestamp": datetime.now(timezone.utc).isoformat()}

    def strategy_allowed(self, strategy: str) -> Tuple[bool, str]:
        item = self.strategy_governance()["strategies"].get(strategy)
        if not item:
            return False, "Unknown strategy"
        return item["state"] != "QUARANTINED", item["reason"]

    def position_size(self, signal: Dict, regime_confidence: float = 65.0) -> Dict:
        """Volatility/confidence/drawdown-aware lot sizing, always capped by risk limits."""
        from risk_engine import get_portfolio_engine
        risk = get_portfolio_engine()
        symbol = signal.get("symbol", "")
        cfg = INSTRUMENTS.get(symbol, {})
        lot = int(cfg.get("lot_size", 1))
        entry = max(float(signal.get("entry_price", 0) or 0), 0.05)
        stop = float(signal.get("stop_loss", entry * 1.5) or entry * 1.5)
        per_unit_risk = max(abs(stop - entry), entry * 0.1, 0.05)
        confidence = min(100.0, max(0.0, float(signal.get("confidence", regime_confidence) or 0)))
        confidence_factor = max(0.25, (confidence - 50.0) / 50.0)
        volatility = float(cfg.get("volatility", 0.25) or 0.25)
        volatility_factor = min(1.0, 0.25 / max(volatility, 0.05))
        peak = max(risk.initial_capital, risk.current_capital)
        drawdown_pct = max(0.0, (peak - risk.current_capital) / peak * 100)
        drawdown_factor = max(0.25, 1.0 - drawdown_pct / 10.0)
        budget = risk.current_capital * self.config.risk_per_trade_pct / 100
        raw_qty = int((budget * confidence_factor * volatility_factor * drawdown_factor) / per_unit_risk)
        lots = max(1, raw_qty // lot)
        max_value = risk.current_capital * risk.limits.max_position_size_pct / 100
        max_lots = max(1, int(max_value / max(entry * lot, 0.05)))
        quantity = lot * min(lots, max_lots)
        return {"quantity": quantity, "lots": quantity // lot, "risk_budget": round(budget, 2),
                "confidence_factor": round(confidence_factor, 3), "volatility_factor": round(volatility_factor, 3),
                "drawdown_factor": round(drawdown_factor, 3)}

    def manage_lifecycle(self) -> Dict:
        from execution_engine import get_execution_engine
        from risk_engine import get_portfolio_engine
        engine = get_execution_engine()
        risk = get_portfolio_engine()
        closed = engine.monitor_positions()
        now = datetime.now(timezone.utc)
        actions = list(closed)
        for pos in list(risk.positions):
            try:
                opened = datetime.fromisoformat(pos.opened_at.replace("Z", "+00:00"))
                held_minutes = (now - opened).total_seconds() / 60
            except Exception:
                held_minutes = 0
            pnl_pct = (pos.unrealized_pnl / max(abs(pos.entry_price * pos.quantity), 1)) * 100
            if pnl_pct >= self.config.trailing_trigger_pct:
                locked = pos.entry_price * (1 - self.config.trailing_lock_pct / 100) if pos.side == "SHORT" else pos.entry_price * (1 + self.config.trailing_lock_pct / 100)
                if pos.side == "SHORT":
                    pos.stop_loss = min(pos.stop_loss or locked, locked)
                else:
                    pos.stop_loss = max(pos.stop_loss or locked, locked)
                risk._save_state()
            if held_minutes >= self.config.max_hold_minutes:
                result = engine.close_position(pos.id, reason="TIME_EXIT")
                if result.get("success"):
                    actions.append({"position_id": pos.id, "reason": "TIME_EXIT", "pnl": result.get("pnl", 0)})
        return {"actions": actions, "timestamp": now.isoformat()}

    def reconcile(self) -> Dict:
        """Validate internal paper state. Live broker reconciliation stays advisory/fail-closed."""
        from risk_engine import get_portfolio_engine
        from trading_mode import get_trading_mode
        risk = get_portfolio_engine()
        mode = get_trading_mode().status()
        ids = [p.id for p in risk.positions]
        issues = []
        if len(ids) != len(set(ids)):
            issues.append("Duplicate internal position IDs")
        for p in risk.positions:
            if p.quantity <= 0 or p.entry_price <= 0:
                issues.append(f"Invalid position values: {p.id}")
        if mode["mode"] == "LIVE":
            issues.append("Automated live reconciliation unavailable; human broker review required")
        status = "MATCHED" if not issues else "MISMATCH"
        self._last_reconciliation = {"status": status, "mode": mode["mode"],
                                     "internal_positions": len(ids), "issues": issues,
                                     "timestamp": datetime.now(timezone.utc).isoformat()}
        if issues:
            risk.activate_kill_switch("Reconciliation mismatch")
            self._alert("CRITICAL", "RECONCILIATION_MISMATCH", "; ".join(issues))
        return self._last_reconciliation

    def recover_workers(self) -> Dict:
        from auto_bot import get_auto_bot
        from execution_engine import get_execution_engine
        recovered = []
        execution = get_execution_engine()
        bot = get_auto_bot()
        if not execution.status()["monitoring_active"]:
            execution.start_monitoring(5)
            recovered.append("position_monitor")
        if bot.config.enabled and not bot.status()["running"]:
            bot.start()
            recovered.append("auto_bot")
        if recovered:
            self._recovery_count += len(recovered)
            self._save()
            self.record_decision("WORKER_RECOVERED", "SYSTEM", "Recovered stopped worker", {"workers": recovered})
        return {"recovered": recovered}

    def run_daily_workflow(self) -> Dict:
        if not self.config.daily_workflow_enabled:
            return {"phase": "DISABLED"}
        now = datetime.now(IST)
        current = now.time()
        weekday = now.weekday() < 5
        if not weekday:
            phase = "WEEKEND_RESEARCH"
        elif current < clock_time(9, 0):
            phase = "PRE_MARKET"
        elif current <= clock_time(15, 30):
            phase = "MARKET_MONITORING"
        else:
            phase = "POST_MARKET_REVIEW"
        self._last_workflow_phase = phase
        today = now.date().isoformat()
        if phase == "POST_MARKET_REVIEW" and self._last_report_date != today:
            self.generate_daily_report()
            self._last_report_date = today
            self._save()
        return {"phase": phase, "market_timezone": "Asia/Kolkata", "timestamp": now.isoformat()}

    def generate_daily_report(self) -> Dict:
        from auto_bot import get_auto_bot
        from risk_engine import get_portfolio_engine
        from trade_journal import get_journal
        report = {"date": datetime.now(IST).date().isoformat(), "risk": get_portfolio_engine().status(),
                  "bot": get_auto_bot().status(), "journal": get_journal().analyze(),
                  "promotion": self.promotion_status(), "generated_at": datetime.now(timezone.utc).isoformat()}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.reports_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, separators=(",", ":")) + "\n")
        return report

    def promotion_status(self) -> Dict:
        governance = self.strategy_governance()["strategies"]
        validated = [k for k, v in governance.items() if v["state"] == "PAPER_VALIDATED"]
        from trade_journal import get_journal
        analysis = get_journal().analyze()
        total = int(analysis.get("summary", {}).get("total_trades", 0)) if isinstance(analysis, dict) else 0
        blockers = []
        if not validated:
            blockers.append("No strategy has passed paper performance thresholds")
        if total < self.config.min_promotion_trades:
            blockers.append(f"Need at least {self.config.min_promotion_trades} closed paper trades")
        blockers.append("Human confirmation is always required for LIVE mode")
        return {"eligible_to_request_live_review": len(blockers) == 1, "validated_strategies": validated,
                "closed_paper_trades": total, "blockers": blockers, "automatic_live_activation": False}

    def record_decision(self, action: str, subject: str, reason: str, context: Dict) -> None:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action,
                 "subject": subject, "reason": reason, "context": context}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self._lock, self.decisions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")

    def decisions(self, limit: int = 100) -> List[Dict]:
        try:
            lines = self.decisions_path.read_text(encoding="utf-8").splitlines()
            return [json.loads(line) for line in lines[-limit:]][::-1]
        except (FileNotFoundError, OSError, ValueError):
            return []

    def _alert(self, level: str, code: str, message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not any(a["code"] == code and a["message"] == message for a in self._alerts[-20:]):
            self._alerts.append({"level": level, "code": code, "message": message, "timestamp": now})
            self._alerts = self._alerts[-100:]

    def status(self) -> Dict:
        from research_optimizer import load_policy
        from auto_bot import get_auto_bot
        from brokers import telegram_bot, zerodha
        from execution_engine import get_execution_engine
        from trading_mode import get_trading_mode
        research_policy = load_policy()
        mode = get_trading_mode().status()
        bot_running = get_auto_bot().status()["running"]
        monitor_running = get_execution_engine().status()["monitoring_active"]
        readiness = automation_readiness([
            {"key": "supervisor", "label": "Autonomy supervisor running", "ok": self._running},
            {"key": "scanner", "label": "Automatic strategy scanner running", "ok": bot_running},
            {"key": "position_monitor", "label": "Paper position monitor running", "ok": monitor_running},
            {"key": "reconciliation", "label": "Paper account reconciled", "ok": self._last_reconciliation.get("status") == "MATCHED"},
            {"key": "real_market", "label": "REAL_MARKET research evidence available", "ok": research_policy.get("evidence_grade") == "REAL_MARKET"},
            {"key": "research", "label": "Strategy R&D enabled", "ok": research_policy.get("research_active", True)},
            {"key": "paper", "label": "Paper trading enabled", "ok": mode.get("mode") == "PAPER" and research_policy.get("paper_trading_active", True)},
            {"key": "telegram", "label": "Telegram alerts configured", "ok": telegram_bot.is_configured()},
            {"key": "kite", "label": "Kite real-time broker feed configured", "ok": zerodha.is_configured()},
        ])
        return {"enabled": self.config.enabled, "running": self._running, "paper_only": True,
                "config": asdict(self.config), "heartbeat": self._last_heartbeat,
                "workflow_phase": self._last_workflow_phase, "health": self._last_health,
                "reconciliation": self._last_reconciliation, "recoveries": self._recovery_count,
                "promotion": self.promotion_status(), "governance": self.strategy_governance(),
                "research_policy": {"mode": research_policy.get("mode", "RISK_OFF"),
                                    "data_source": research_policy.get("data_source", "NONE"),
                                    "approved_by_symbol": research_policy.get("approved_by_symbol", {}),
                                    "live_eligible": False},
                "automation_readiness": readiness,
                "alerts": self._alerts[-20:], "recent_decisions": self.decisions(20),
                "timestamp": datetime.now(timezone.utc).isoformat()}


_supervisor: Optional[AutonomySupervisor] = None


def get_autonomy_supervisor() -> AutonomySupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = AutonomySupervisor()
    return _supervisor
