"""Event-driven VWAP pullback and mean-reversion research algorithms."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
from statistics import mean, pstdev
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class IntradayConfig:
    strategy: str = "VWAP_PULLBACK"
    lookback: int = 20
    z_entry: float = 2.0
    stop_atr_multiple: float = 1.0
    reward_risk: float = 1.5
    risk_per_trade_pct: float = 0.35
    max_trades_per_day: int = 1
    slippage_ticks: int = 2
    commission_per_order: float = 20.0
    entry_start: str = "09:45"
    entry_cutoff: str = "14:30"
    forced_exit: str = "15:15"
    trade_direction: str = "BOTH"


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def _atr(bars: List[Dict], period: int = 14) -> float:
    ranges = [max(cur["high"] - cur["low"], abs(cur["high"] - prev["close"]),
                  abs(cur["low"] - prev["close"])) for prev, cur in zip(bars, bars[1:])]
    return mean(ranges[-period:]) if ranges else 0.0


def run_intraday_backtest(
    bars: List[Dict], symbol: str, lot_size: int = 1, tick_size: float = .01,
    initial_capital: float = 100000, config: Optional[IntradayConfig] = None,
) -> Dict:
    config = config or IntradayConfig()
    if config.strategy not in {"VWAP_PULLBACK", "MEAN_REVERSION"}:
        return {"status": "FAILED", "error": "Unsupported intraday strategy", "trades": []}
    if config.trade_direction not in {"BOTH", "LONG", "SHORT"}:
        return {"status": "FAILED", "error": "Invalid trade direction", "trades": []}
    if not bars:
        return {"status": "FAILED", "error": "No candles", "trades": []}

    ordered = sorted(bars, key=lambda row: row["timestamp"])
    capital = peak = initial_capital
    max_drawdown, trades, state, pending, position = 0.0, [], {}, None, None
    for index, bar in enumerate(ordered):
        stamp = datetime.fromisoformat(str(bar["timestamp"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        local, volume = stamp.astimezone(IST), max(float(bar.get("volume", 0) or 0), 0)
        day = local.date().isoformat()
        session = state.setdefault(day, {"bars": [], "trades": 0, "cum_pv": 0.0, "cum_volume": 0.0,
                                         "previous_close": None, "previous_vwap": None})
        typical = (bar["high"] + bar["low"] + bar["close"]) / 3
        session["cum_pv"] += typical * volume
        session["cum_volume"] += volume
        vwap = session["cum_pv"] / session["cum_volume"] if session["cum_volume"] else None
        session["bars"].append(bar)

        if pending and pending["index"] == index and position is None:
            fill = bar["open"] + pending["side"] * tick_size * config.slippage_ticks
            budget = capital * config.risk_per_trade_pct / 100
            lots = max(1, math.floor(budget / max(pending["risk"] * lot_size, 1e-9)))
            position = {**pending, "entry": fill, "entry_time": bar["timestamp"], "quantity": lots * lot_size,
                        "stop": fill - pending["side"] * pending["risk"],
                        "target": fill + pending["side"] * pending["risk"] * config.reward_risk}
            pending = None

        if position:
            exit_price = reason = None
            if position["side"] == 1 and bar["low"] <= position["stop"]:
                exit_price, reason = position["stop"] - tick_size * config.slippage_ticks, "STOP"
            elif position["side"] == 1 and bar["high"] >= position["target"]:
                exit_price, reason = position["target"] - tick_size * config.slippage_ticks, "TARGET"
            elif position["side"] == -1 and bar["high"] >= position["stop"]:
                exit_price, reason = position["stop"] + tick_size * config.slippage_ticks, "STOP"
            elif position["side"] == -1 and bar["low"] <= position["target"]:
                exit_price, reason = position["target"] + tick_size * config.slippage_ticks, "TARGET"
            elif local.time() >= _clock(config.forced_exit):
                exit_price, reason = bar["close"] - position["side"] * tick_size * config.slippage_ticks, "TIME"
            if exit_price is not None:
                pnl = (exit_price - position["entry"]) * position["side"] * position["quantity"] - 2 * config.commission_per_order
                capital += pnl
                session["trades"] += 1
                trades.append({"symbol": symbol, "strategy": config.strategy,
                               "side": "LONG" if position["side"] == 1 else "SHORT",
                               "signal_time": position["signal_time"], "entry_time": position["entry_time"],
                               "exit_time": bar["timestamp"], "pnl": round(pnl, 2), "exit_reason": reason})
                position = None

        can_signal = (position is None and pending is None and vwap is not None
                      and _clock(config.entry_start) <= local.time() <= _clock(config.entry_cutoff)
                      and session["trades"] < config.max_trades_per_day and index + 1 < len(ordered))
        if can_signal:
            history, side = session["bars"], 0
            if config.strategy == "VWAP_PULLBACK" and session["previous_vwap"] is not None:
                if session["previous_close"] <= session["previous_vwap"] and bar["close"] > vwap and bar["close"] > history[0]["open"]:
                    side = 1
                elif session["previous_close"] >= session["previous_vwap"] and bar["close"] < vwap and bar["close"] < history[0]["open"]:
                    side = -1
            elif config.strategy == "MEAN_REVERSION" and len(history) >= config.lookback:
                closes = [float(item["close"]) for item in history[-config.lookback:]]
                deviation = pstdev(closes)
                zscore = (bar["close"] - mean(closes)) / deviation if deviation else 0
                side = 1 if zscore <= -config.z_entry and bar["close"] < vwap else -1 if zscore >= config.z_entry and bar["close"] > vwap else 0
            if (config.trade_direction == "LONG" and side != 1) or (config.trade_direction == "SHORT" and side != -1):
                side = 0
            atr = _atr(history)
            if side and atr > 0:
                pending = {"index": index + 1, "side": side, "signal_time": bar["timestamp"],
                           "risk": atr * config.stop_atr_multiple}

        session["previous_close"], session["previous_vwap"] = bar["close"], vwap
        peak = max(peak, capital)
        max_drawdown = max(max_drawdown, (peak - capital) / peak * 100 if peak else 0)

    pnls = [row["pnl"] for row in trades]
    wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p <= 0]
    pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) else (99.99 if wins else 0)
    return {"status": "COMPLETED", "strategy": config.strategy, "symbol": symbol,
            "data_source": ordered[0].get("source", "UNKNOWN"), "config": asdict(config),
            "metrics": {"initial_capital": initial_capital, "final_capital": round(capital, 2),
                        "return_pct": round((capital / initial_capital - 1) * 100, 2), "trades": len(trades),
                        "wins": len(wins), "losses": len(losses),
                        "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else 0,
                        "profit_factor": round(pf, 3), "max_drawdown_pct": round(max_drawdown, 2),
                        "expectancy": round(sum(pnls) / len(pnls), 2) if pnls else 0}, "trades": trades}
