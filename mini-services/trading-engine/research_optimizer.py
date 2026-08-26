"""Leakage-resistant paper research and policy selection for JARVIS.

The built-in market source is synthetic unless replaced by broker candles.  This
module therefore produces a PAPER policy, never evidence for automatic LIVE use.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from backtest import run_backtest
from market_data import INSTRUMENTS, generate_history
from strategies import STRATEGIES
from validation import monte_carlo_trade_shuffle


def _score(metrics: Dict) -> float:
    trades = metrics.get("total_trades", 0)
    if trades < 5:
        return -999.0
    return round(
        metrics.get("sharpe", 0) * 2.0
        + metrics.get("sortino", 0)
        + min(metrics.get("profit_factor", 0), 3.0)
        - metrics.get("max_drawdown_pct", 100) / 10.0,
        4,
    )


def _period_is_credible(metrics: Dict, min_trades: int = 5) -> bool:
    return (
        metrics.get("total_trades", 0) >= min_trades
        and metrics.get("total_return_pct", 0) > 0
        and metrics.get("profit_factor", 0) >= 1.05
        and metrics.get("max_drawdown_pct", 100) > 0
        and metrics.get("exposure_pct", 0) >= 5
        and metrics.get("losses", 0) >= 2
        and metrics.get("win_rate", 100) < 95
    )


def _passes(train: Dict, validation: Dict, holdout: Dict, mc: Dict) -> bool:
    return (
        _period_is_credible(train)
        and _period_is_credible(validation)
        and _period_is_credible(holdout, min_trades=10)
        and holdout.get("profit_factor", 0) >= 1.1
        and holdout.get("max_drawdown_pct", 100) <= 15
        and holdout.get("sharpe", -99) > 0
        and mc.get("status") == "COMPLETED"
        and mc.get("probability_of_ruin_20pct", 100) <= 20
    )


def run_research(
    symbols: Optional[List[str]] = None,
    strategies: Optional[List[str]] = None,
    days: int = 730,
    output_path: Optional[Path] = None,
) -> Dict:
    """Tune on train, select on validation, disclose untouched holdout results."""
    symbols = symbols or list(INSTRUMENTS)
    strategies = strategies or list(STRATEGIES)
    parameter_grid = [(sl, tp) for sl in (20.0, 30.0, 40.0) for tp in (25.0, 40.0, 55.0)]
    results = []
    data_sources = set()

    for symbol in symbols:
        bars = generate_history(symbol, days=days, timeframe="1d")
        data_sources.update(str(bar.get("source", "UNKNOWN")) for bar in bars[:1])
        n = len(bars)
        train_end, validation_end = int(n * 0.60), int(n * 0.80)
        train, validation, holdout = bars[:train_end], bars[train_end:validation_end], bars[validation_end:]
        for strategy in strategies:
            candidates = []
            for sl_pct, tp_pct in parameter_grid:
                train_result = run_backtest(strategy, symbol, days=days, sl_pct=sl_pct, tp_pct=tp_pct,
                                            bars_override=train)
                validation_result = run_backtest(strategy, symbol, days=days, sl_pct=sl_pct, tp_pct=tp_pct,
                                                 bars_override=validation)
                combined_score = _score(train_result["metrics"]) * 0.4 + _score(validation_result["metrics"]) * 0.6
                candidates.append((combined_score, sl_pct, tp_pct, train_result, validation_result))
            candidates.sort(key=lambda row: row[0], reverse=True)
            score, sl_pct, tp_pct, train_result, validation_result = candidates[0]
            holdout_result = run_backtest(strategy, symbol, days=days, sl_pct=sl_pct, tp_pct=tp_pct,
                                          bars_override=holdout)
            mc = monte_carlo_trade_shuffle(holdout_result.get("all_trades", []), 100000, n_runs=1000, seed=42)
            passed = _passes(train_result["metrics"], validation_result["metrics"], holdout_result["metrics"], mc)
            results.append({
                "symbol": symbol, "strategy": strategy, "sl_pct": sl_pct, "tp_pct": tp_pct,
                "selection_score": round(score, 4), "train": train_result["metrics"],
                "validation": validation_result["metrics"], "holdout": holdout_result["metrics"],
                "monte_carlo": mc, "passed": passed,
            })

    results.sort(key=lambda item: (_score(item["holdout"]), item["selection_score"]), reverse=True)
    approved = [item for item in results if item["passed"]]
    per_symbol = {}
    for symbol in symbols:
        choices = [item for item in approved if item["symbol"] == symbol]
        if choices:
            best = choices[0]
            per_symbol[symbol] = {"strategy": best["strategy"], "sl_pct": best["sl_pct"],
                                  "tp_pct": best["tp_pct"], "holdout": best["holdout"]}
    mode = "BALANCED" if len(per_symbol) >= 3 else "DEFENSIVE" if per_symbol else "RISK_OFF"
    real_sources = sorted(source for source in data_sources if not source.startswith("SYNTHETIC"))
    policy = {
        "version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode, "paper_only": True,
        "data_source": real_sources[0] if len(real_sources) == 1 and len(data_sources) == 1 else "+".join(sorted(data_sources)),
        "evidence_grade": "REAL_MARKET" if real_sources and len(real_sources) == len(data_sources) else "ENGINEERING_ONLY",
        "live_eligible": False,
        "methodology": "60% train, 20% validation selection, 20% untouched holdout; costs and slippage enabled",
        "approved_by_symbol": per_symbol,
        "approved_count": len(approved), "candidates_tested": len(results),
        "top_results": results[:25],
        "limitations": (["Broker historical option chains and paper fills are required before any live review"]
                        if real_sources and len(real_sources) == len(data_sources) else [
                            "Synthetic deterministic candles are engineering evidence, not proof of real-market profitability",
                            "Broker historical candles and paper fills are required before any live review",
                        ]),
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp = output_path.with_suffix(".tmp")
        temp.write_text(json.dumps(policy, indent=2), encoding="utf-8")
        temp.replace(output_path)
    return policy


def load_policy(path: Optional[Path] = None) -> Dict:
    path = path or Path(__file__).parent / "data" / "research-policy.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {"mode": "RISK_OFF", "paper_only": True, "live_eligible": False,
                "approved_by_symbol": {}, "limitations": ["No validated research policy available"]}
