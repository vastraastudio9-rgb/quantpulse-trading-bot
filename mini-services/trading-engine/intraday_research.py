"""Leakage-resistant research for VWAP pullback and mean-reversion strategies."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from intraday_algorithms import IntradayConfig, run_intraday_backtest


IST = ZoneInfo("Asia/Kolkata")


def _day(bar: Dict) -> str:
    return datetime.fromisoformat(str(bar["timestamp"]).replace("Z", "+00:00")).astimezone(IST).date().isoformat()


def research_intraday_strategies(
    bars: List[Dict], symbol: str, lot_size: int = 1, tick_size: float = .01,
    output_path: Optional[Path] = None,
) -> Dict:
    sessions = sorted({_day(bar) for bar in bars})
    if len(sessions) < 40:
        return {"status": "INSUFFICIENT_DATA", "sessions": len(sessions), "minimum_sessions": 40,
                "paper_only": True, "live_eligible": False}
    train_end, validation_end = int(len(sessions) * .6), int(len(sessions) * .8)
    day_sets = [set(sessions[:train_end]), set(sessions[train_end:validation_end]), set(sessions[validation_end:])]
    train_bars, validation_bars, holdout_bars = ([bar for bar in bars if _day(bar) in days] for days in day_sets)
    tested = []
    configs = []
    for stop, reward, cutoff, direction in product((.75, 1.0, 1.25), (1.25, 1.5, 1.75), ("11:30", "14:30"), ("BOTH", "LONG")):
        configs.append(IntradayConfig(strategy="VWAP_PULLBACK", stop_atr_multiple=stop,
                                      reward_risk=reward, entry_cutoff=cutoff, trade_direction=direction))
    for lookback, zscore, stop, reward, direction in product((15, 20, 30), (1.5, 2.0, 2.5), (.75, 1.0), (1.25, 1.5), ("BOTH", "LONG")):
        configs.append(IntradayConfig(strategy="MEAN_REVERSION", lookback=lookback, z_entry=zscore,
                                      stop_atr_multiple=stop, reward_risk=reward, trade_direction=direction))
    for config in configs:
        train = run_intraday_backtest(train_bars, symbol, lot_size, tick_size, config=config)["metrics"]
        validation = run_intraday_backtest(validation_bars, symbol, lot_size, tick_size, config=config)["metrics"]
        valid_sample = train["trades"] >= 8 and validation["trades"] >= 4
        score = (min(train["return_pct"], validation["return_pct"])
                 - .6 * (train["max_drawdown_pct"] + validation["max_drawdown_pct"])) if valid_sample else -1e9
        tested.append({"config": config, "train": train, "validation": validation, "score": score})
    selected = max(tested, key=lambda item: item["score"])
    holdout_result = run_intraday_backtest(holdout_bars, symbol, lot_size, tick_size, config=selected["config"])
    holdout = holdout_result["metrics"]
    approved = (
        selected["score"] > -1e8 and holdout["trades"] >= 5
        and all(metrics["return_pct"] > 0 and metrics["profit_factor"] >= 1.15
                for metrics in (selected["train"], selected["validation"], holdout))
        and holdout["max_drawdown_pct"] <= 12
    )
    report = {
        "status": "PAPER_CANDIDATE" if approved else "REJECTED",
        "generated_at": datetime.now(timezone.utc).isoformat(), "paper_only": True, "live_eligible": False,
        "symbol": symbol, "data_source": bars[0].get("source", "UNKNOWN"), "sessions": len(sessions),
        "split_sessions": {"train": len(day_sets[0]), "validation": len(day_sets[1]), "holdout": len(day_sets[2])},
        "candidates_tested": len(tested), "selected_config": asdict(selected["config"]),
        "train": selected["train"], "validation": selected["validation"], "holdout": holdout,
        "reason": "Passed all paper-candidate gates" if approved else "Selected strategy failed validation or untouched holdout gates",
        "limitations": ["Forward paper fills are required before PAPER_VALIDATED", "Live activation is never automatic"],
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp = output_path.with_suffix(".tmp")
        temp.write_text(json.dumps(report, indent=2), encoding="utf-8")
        temp.replace(output_path)
    return report
