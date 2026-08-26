"""Leakage-resistant ORB parameter research with an untouched holdout."""
from __future__ import annotations

from dataclasses import asdict
from itertools import product
from typing import Dict, List
from zoneinfo import ZoneInfo
from datetime import datetime

from orb_algorithm import ORBConfig, run_orb_backtest


IST = ZoneInfo("Asia/Kolkata")


def _sessions(bars: List[Dict]) -> List[str]:
    return sorted({datetime.fromisoformat(str(bar["timestamp"]).replace("Z", "+00:00"))
                   .astimezone(IST).date().isoformat() for bar in bars})


def _slice(bars: List[Dict], days: set[str]) -> List[Dict]:
    return [bar for bar in bars if datetime.fromisoformat(str(bar["timestamp"]).replace("Z", "+00:00"))
            .astimezone(IST).date().isoformat() in days]


def _score(metrics: Dict) -> float:
    if metrics["trades"] < 4 or metrics["max_drawdown_pct"] > 8:
        return -1e9
    return metrics["return_pct"] * 2 + min(metrics["profit_factor"], 4) * 2 - metrics["max_drawdown_pct"]


def optimize_orb(bars: List[Dict], symbol: str = "NIFTYBEES", initial_capital: float = 100000) -> Dict:
    sessions = _sessions(bars)
    if len(sessions) < 30:
        return {"status": "INSUFFICIENT_DATA", "sessions": len(sessions), "minimum_sessions": 30}
    train_end, validation_end = int(len(sessions) * .6), int(len(sessions) * .8)
    train_days, validation_days, holdout_days = (set(sessions[:train_end]),
                                                  set(sessions[train_end:validation_end]),
                                                  set(sessions[validation_end:]))
    segments = {"train": _slice(bars, train_days), "validation": _slice(bars, validation_days),
                "holdout": _slice(bars, holdout_days)}
    candidates, tested = [], []
    for opening, rel_volume, atr_stop, rr, cutoff in product(
            (15, 30), (.8, 1.0, 1.2), (.75, 1.0, 1.25), (1.25, 1.5, 2.0), ("11:30", "14:30")):
        config = ORBConfig(opening_range_minutes=opening, entry_start="09:30" if opening == 15 else "09:45",
                           relative_volume_min=rel_volume, stop_atr_multiple=atr_stop,
                           reward_risk=rr, entry_cutoff=cutoff, max_trades_per_day=1)
        train = run_orb_backtest(segments["train"], symbol, 1, .01, initial_capital, config)["metrics"]
        validation = run_orb_backtest(segments["validation"], symbol, 1, .01, initial_capital, config)["metrics"]
        score = _score(validation)
        tested.append({"config": config, "train": train, "validation": validation, "score": score})
        if train["trades"] >= 8 and train["return_pct"] > 0 and train["profit_factor"] > 1:
            candidates.append({"config": config, "train": train, "validation": validation, "score": score})
    if not candidates:
        best = max(tested, key=lambda item: item["train"]["return_pct"])
        return {"status": "REJECTED", "reason": "No profitable training candidate met minimum evidence",
                "paper_only": True, "sessions": len(sessions), "candidates_tested": 108,
                "best_training_config": asdict(best["config"]),
                "best_training_metrics": best["train"], "validation_metrics": best["validation"]}
    selected = max(candidates, key=lambda item: item["score"])
    holdout_result = run_orb_backtest(segments["holdout"], symbol, 1, .01, initial_capital, selected["config"])
    holdout = holdout_result["metrics"]
    approved = (selected["score"] > -1e8 and holdout["trades"] >= 4 and holdout["return_pct"] > 0
                and holdout["profit_factor"] > 1 and holdout["max_drawdown_pct"] <= 8)
    return {"status": "APPROVED_PAPER" if approved else "REJECTED", "paper_only": True,
            "symbol": symbol, "sessions": len(sessions), "split_sessions": {
                "train": len(train_days), "validation": len(validation_days), "holdout": len(holdout_days)},
            "candidates_tested": 108, "selected_config": asdict(selected["config"]),
            "train": selected["train"], "validation": selected["validation"], "holdout": holdout,
            "holdout_trades": holdout_result["trades"],
            "reason": "Passed untouched holdout gates" if approved else "Best validation candidate failed untouched holdout gates"}
