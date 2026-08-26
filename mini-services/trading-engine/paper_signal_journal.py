"""Append-only journal for autonomous paper signals and their outcomes."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class PaperSignalJournal:
    def __init__(self, path: Optional[Path] = None):
        base = Path(os.getenv("JARVIS_STATE_DIR") or Path(__file__).parent / "data")
        self.path = Path(path or base / "paper_signals.jsonl")
        self._lock = threading.RLock()

    def _append(self, event: Dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")

    def record_detected(self, signal: Dict, regime: str, scope: str, notification: Optional[Dict] = None,
                        dedupe_minutes: int = 15) -> str:
        now = datetime.now(timezone.utc)
        if dedupe_minutes > 0:
            for existing in self.recent(100):
                same = (existing.get("symbol") == signal.get("symbol")
                        and existing.get("strategy_key") == signal.get("strategy_key")
                        and existing.get("direction") == signal.get("direction"))
                try:
                    age = (now - datetime.fromisoformat(existing["detected_at"].replace("Z", "+00:00"))).total_seconds()
                except (KeyError, ValueError, TypeError):
                    age = dedupe_minutes * 60 + 1
                if same and age < dedupe_minutes * 60:
                    return existing["signal_id"]
        signal_id = str(signal.get("signal_id") or f"PS-{uuid.uuid4().hex[:12]}")
        timestamp = now.isoformat()
        snapshot = {**signal, "signal_id": signal_id, "timestamp": signal.get("timestamp") or timestamp}
        self._append({"event": "DETECTED", "signal_id": signal_id, "timestamp": timestamp,
                      "signal": snapshot, "paper_status": "DETECTED", "regime": regime,
                      "execution_scope": scope, "notification": notification or {}})
        return signal_id

    def record_outcome(self, signal_id: str, status: str, details: Dict) -> None:
        self._append({"event": "OUTCOME", "signal_id": signal_id,
                      "timestamp": datetime.now(timezone.utc).isoformat(),
                      "paper_status": status, "outcome": details})

    def recent(self, limit: int = 50) -> List[Dict]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError):
            return []
        items: Dict[str, Dict] = {}
        order: List[str] = []
        for line in lines:
            try:
                event = json.loads(line)
                signal_id = event["signal_id"]
            except (ValueError, KeyError, TypeError):
                continue
            if event.get("event") == "DETECTED":
                items[signal_id] = {**event.get("signal", {}), "paper_status": event.get("paper_status"),
                                    "detected_at": event.get("timestamp"),
                                    "regime": event.get("regime"), "execution_scope": event.get("execution_scope"),
                                    "notification": event.get("notification", {})}
                order.append(signal_id)
            elif signal_id in items:
                items[signal_id]["paper_status"] = event.get("paper_status", items[signal_id].get("paper_status"))
                items[signal_id]["paper_outcome"] = event.get("outcome", {})
        return [items[key] for key in reversed(order[-limit:]) if key in items]


_journal: Optional[PaperSignalJournal] = None


def get_paper_signal_journal() -> PaperSignalJournal:
    global _journal
    if _journal is None:
        _journal = PaperSignalJournal()
    return _journal
