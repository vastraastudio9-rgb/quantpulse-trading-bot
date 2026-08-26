"""Persistent forward-paper validation for frozen intraday research candidates."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

from intraday_algorithms import IntradayConfig, run_intraday_backtest


IST = ZoneInfo("Asia/Kolkata")


def _timestamp(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class ForwardValidationRegistry:
    """Track unseen post-selection evidence without granting live permission."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.state = self._load()

    def _load(self) -> Dict:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("candidates"), list):
                return value
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass
        return {"version": 1, "candidates": []}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        temp.replace(self.path)

    @staticmethod
    def _fingerprint(symbol: str, config: Dict) -> str:
        raw = json.dumps({"symbol": symbol, "config": config}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def register(self, report: Dict, latest_bar_timestamp: str) -> Dict:
        if report.get("status") != "PAPER_CANDIDATE" or not report.get("selected_config"):
            return {"registered": False, "reason": "Research did not pass paper-candidate gates"}
        symbol = str(report.get("symbol", "NIFTYBEES"))
        config = dict(report["selected_config"])
        fingerprint = self._fingerprint(symbol, config)
        existing = next((item for item in self.state["candidates"] if item["id"] == fingerprint), None)
        if existing:
            return {"registered": False, "reason": "Candidate already tracked", "candidate": existing}
        for item in self.state["candidates"]:
            if item.get("status") == "FORWARD_TESTING":
                item["status"] = "SUPERSEDED"
        candidate = {
            "id": fingerprint, "symbol": symbol, "config": config,
            "selected_at": report.get("generated_at") or datetime.now(timezone.utc).isoformat(),
            "baseline_timestamp": latest_bar_timestamp, "status": "FORWARD_TESTING",
            "minimum_sessions": 20, "minimum_trades": 10,
            "metrics": None, "sessions": 0, "paper_only": True, "live_eligible": False,
        }
        self.state["candidates"].append(candidate)
        self._save()
        return {"registered": True, "candidate": candidate}

    def evaluate(self, bars: List[Dict], lot_size: int = 1, tick_size: float = .01) -> Dict:
        active = [item for item in self.state["candidates"] if item.get("status") == "FORWARD_TESTING"]
        results = []
        for candidate in active:
            baseline = _timestamp(candidate["baseline_timestamp"])
            unseen = [bar for bar in bars if _timestamp(bar.get("timestamp")) > baseline]
            sessions = len({_timestamp(bar["timestamp"]).astimezone(IST).date().isoformat() for bar in unseen})
            result = run_intraday_backtest(
                unseen, candidate["symbol"], lot_size, tick_size,
                config=IntradayConfig(**candidate["config"]),
            )
            metrics = result.get("metrics", {})
            candidate["sessions"] = sessions
            candidate["metrics"] = metrics
            candidate["evaluated_at"] = datetime.now(timezone.utc).isoformat()
            enough = sessions >= candidate["minimum_sessions"] and int(metrics.get("trades", 0)) >= candidate["minimum_trades"]
            if enough:
                passed = (float(metrics.get("return_pct", 0)) > 0
                          and float(metrics.get("profit_factor", 0)) >= 1.15
                          and float(metrics.get("max_drawdown_pct", 999)) <= 12)
                candidate["status"] = "FORWARD_VALIDATED" if passed else "FORWARD_REJECTED"
            results.append(candidate)
        if active:
            self._save()
        return {"evaluated": len(results), "candidates": results,
                "paper_only": True, "live_eligible": False}

    def status(self) -> Dict:
        return {"candidates": list(reversed(self.state["candidates"])),
                "paper_only": True, "live_eligible": False}
