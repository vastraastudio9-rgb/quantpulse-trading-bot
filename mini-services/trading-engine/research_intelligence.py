"""Persistent PAPER-only research intelligence and experiment governance."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def _state_dir() -> Path:
    return Path(os.getenv("JARVIS_STATE_DIR") or Path(__file__).parent / "data")


def _git_commit() -> Optional[str]:
    try:
        root = Path(__file__).resolve().parents[2]
        value = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                               text=True, timeout=3, check=True).stdout.strip()
        return value or None
    except (OSError, subprocess.SubprocessError):
        return None


class ExperimentRegistry:
    """Append-only experiment registry; identical designs keep one identity."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or _state_dir() / "experiment_registry.jsonl")
        self._lock = threading.RLock()

    @staticmethod
    def fingerprint(strategy: str, symbol: str, config: Dict, provenance: Dict) -> str:
        design = {"strategy": strategy, "symbol": symbol, "config": config, "provenance": provenance}
        raw = json.dumps(design, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def register(self, strategy: str, symbol: str, config: Dict, provenance: Dict,
                 metrics: Dict, stage: str, verdict: str, limitations: Optional[List[str]] = None) -> Dict:
        experiment_id = self.fingerprint(strategy, symbol, config, provenance)
        event = {
            "experiment_id": experiment_id, "recorded_at": datetime.now(timezone.utc).isoformat(),
            "strategy": strategy, "symbol": symbol, "config": config, "provenance": provenance,
            "metrics": metrics, "stage": stage, "verdict": verdict,
            "limitations": limitations or [], "git_commit": _git_commit(),
            "paper_only": True, "live_eligible": False,
        }
        with self._lock:
            existing = next((item for item in self.recent(5000)
                             if item.get("experiment_id") == experiment_id
                             and item.get("stage") == stage), None)
            if existing:
                return {"registered": False, "reason": "Experiment stage already recorded", "experiment": existing}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, separators=(",", ":"), default=str) + "\n")
        return {"registered": True, "experiment": event}

    def recent(self, limit: int = 100) -> List[Dict]:
        try:
            rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return []
        return list(reversed(rows[-max(1, limit):]))

    def status(self) -> Dict:
        rows = self.recent(5000)
        return {
            "experiments": len({row.get("experiment_id") for row in rows}),
            "records": len(rows), "latest": rows[:20], "paper_only": True, "live_eligible": False,
        }


def _metrics(rows: List[Dict]) -> Dict:
    pnls = [float(row.get("pnl", 0) or 0) for row in rows]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    return {
        "trades": len(rows), "wins": len(wins),
        "win_rate": round(len(wins) / len(rows) * 100, 1) if rows else 0,
        "pnl": round(sum(pnls), 2),
        "expectancy": round(sum(pnls) / len(rows), 2) if rows else 0,
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else (None if gross_profit else 0),
    }


class StrategyIntelligence:
    """Analyze actual and shadow evidence without mixing their promotion value."""

    @staticmethod
    def analyze(actual_trades: Iterable[Dict], shadow_trades: Iterable[Dict],
                recent_window: int = 20, minimum_drift_samples: int = 10) -> Dict:
        actual, shadow = list(actual_trades), list(shadow_trades)
        actual_groups: Dict[str, List[Dict]] = defaultdict(list)
        shadow_groups: Dict[str, List[Dict]] = defaultdict(list)
        for row in actual:
            key = f"{row.get('strategy', 'UNKNOWN')}|{row.get('regime_at_entry', 'UNKNOWN')}"
            actual_groups[key].append(row)
        for row in shadow:
            key = f"{row.get('strategy', 'UNKNOWN')}|{row.get('regime', 'UNKNOWN')}"
            shadow_groups[key].append(row)

        regime_performance = {}
        for key in sorted(set(actual_groups) | set(shadow_groups)):
            regime_performance[key] = {
                "actual": _metrics(actual_groups[key]), "shadow_model": _metrics(shadow_groups[key]),
                "promotion_evidence": len(actual_groups[key]),
            }

        drift = {}
        by_strategy: Dict[str, List[Dict]] = defaultdict(list)
        for row in actual:
            by_strategy[str(row.get("strategy", "UNKNOWN"))].append(row)
        for strategy, rows in by_strategy.items():
            recent = rows[-recent_window:]
            baseline = rows[:-len(recent)] if recent else []
            recent_stats, baseline_stats = _metrics(recent), _metrics(baseline)
            enough = len(recent) >= minimum_drift_samples and len(baseline) >= minimum_drift_samples
            expectancy_break = enough and baseline_stats["expectancy"] > 0 and recent_stats["expectancy"] < 0
            win_rate_drop = enough and baseline_stats["win_rate"] - recent_stats["win_rate"] >= 20
            drift[strategy] = {
                "status": "QUARANTINE_REVIEW" if expectancy_break or win_rate_drop else
                          "STABLE" if enough else "INSUFFICIENT_DATA",
                "recent": recent_stats, "baseline": baseline_stats,
                "actual_evidence_only": True,
            }
        return {
            "regime_performance": regime_performance, "drift": drift,
            "actual_trades": len(actual), "shadow_trades": len(shadow),
            "meta_label": {
                "status": "READY_FOR_TRAINING" if len(actual) >= 100 else "INSUFFICIENT_ACTUAL_LABELS",
                "actual_labels": len(actual), "minimum_labels": 100,
                "method": "CALIBRATED_CLASSIFIER_AFTER_CHRONOLOGICAL_VALIDATION",
                "shadow_labels_accepted": False,
            },
            "limitations": ["Shadow/model evidence is excluded from promotion and drift quarantine"],
            "paper_only": True, "live_eligible": False,
        }

    @staticmethod
    def rank_signals(signals: Iterable[Dict], recommended: Iterable[str], governance: Dict,
                     open_positions: Iterable[Dict]) -> List[Dict]:
        recommended_set = set(recommended)
        exposed_symbols = {str(item.get("symbol", item.get("instrument", ""))) for item in open_positions}
        ranked = []
        for signal in signals:
            strategy, symbol = str(signal.get("strategy_key", "")), str(signal.get("symbol", ""))
            state = governance.get(strategy, {}).get("state", "PAPER_LEARNING")
            if state == "QUARANTINED" or signal.get("paper_execution_eligible") is not True:
                continue
            confidence = float(signal.get("confidence", 0) or 0)
            score = confidence
            score += 15 if strategy in recommended_set else -20
            score -= 12 if symbol in exposed_symbols else 0
            score += 5 if state == "PAPER_VALIDATED" else 0
            ranked.append({**signal, "ranking_score": round(score, 2),
                           "ranking_reasons": {"regime_compatible": strategy in recommended_set,
                                               "existing_symbol_exposure": symbol in exposed_symbols,
                                               "governance_state": state},
                           "paper_only": True, "live_eligible": False})
        return sorted(ranked, key=lambda item: item["ranking_score"], reverse=True)


def backup_research_state(state_dir: Optional[Path] = None, retention_days: int = 14,
                          now: Optional[datetime] = None) -> Dict:
    """Copy non-secret research state to a dated local backup directory."""
    source = Path(state_dir or _state_dir())
    current = now or datetime.now(timezone.utc)
    target = source / "backups" / current.strftime("%Y-%m-%d")
    target.mkdir(parents=True, exist_ok=True)
    allowed = {".json", ".jsonl"}
    copied, manifest = 0, []
    for path in source.iterdir() if source.exists() else []:
        if not path.is_file() or path.suffix.lower() not in allowed or "secret" in path.name.lower():
            continue
        destination = target / path.name
        shutil.copy2(path, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        manifest.append({"file": path.name, "sha256": digest, "bytes": destination.stat().st_size})
        copied += 1
    (target / "manifest.json").write_text(json.dumps({"created_at": current.isoformat(),
                                                       "files": manifest}, indent=2), encoding="utf-8")
    cutoff = current.date() - timedelta(days=max(1, retention_days))
    removed = 0
    for directory in (source / "backups").iterdir():
        if directory.is_dir():
            try:
                if datetime.strptime(directory.name, "%Y-%m-%d").date() < cutoff:
                    shutil.rmtree(directory)
                    removed += 1
            except ValueError:
                continue
    return {"status": "COMPLETED", "path": str(target), "files": copied,
            "expired_backups_removed": removed, "contains_secrets": False}


_registry: Optional[ExperimentRegistry] = None


def get_experiment_registry() -> ExperimentRegistry:
    global _registry
    if _registry is None:
        _registry = ExperimentRegistry()
    return _registry
