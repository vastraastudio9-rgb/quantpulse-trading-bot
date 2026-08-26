"""Event-driven Opening Range Breakout algorithm for real intraday candles."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


@dataclass
class ORBConfig:
    opening_range_minutes: int = 15
    volume_lookback: int = 20
    relative_volume_min: float = 1.15
    atr_period: int = 14
    stop_atr_multiple: float = 1.0
    reward_risk: float = 1.75
    risk_per_trade_pct: float = 0.35
    max_trades_per_day: int = 2
    consecutive_loss_stop: int = 2
    slippage_ticks: int = 2
    commission_per_order: float = 20.0
    entry_start: str = "09:30"
    entry_cutoff: str = "14:30"
    forced_exit: str = "15:15"


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def _atr(bars: List[Dict], period: int) -> float:
    if len(bars) < 2:
        return 0.0
    ranges = []
    for previous, current in zip(bars, bars[1:]):
        ranges.append(max(current["high"] - current["low"],
                          abs(current["high"] - previous["close"]),
                          abs(current["low"] - previous["close"])))
    return sum(ranges[-period:]) / min(len(ranges), period)


def run_orb_backtest(bars: List[Dict], symbol: str, lot_size: int, tick_size: float,
                     initial_capital: float = 100000, config: Optional[ORBConfig] = None) -> Dict:
    """Replay 5-minute candles. Decisions use close; fills occur next bar open."""
    config = config or ORBConfig()
    if not bars:
        return {"status": "FAILED", "error": "No candles", "trades": []}
    ordered = sorted(bars, key=lambda bar: bar["timestamp"])
    capital, peak, max_drawdown = initial_capital, initial_capital, 0.0
    trades, equity = [], []
    state: Dict[str, Dict] = {}
    pending = None
    position = None
    consecutive_losses = 0

    for index, bar in enumerate(ordered):
        timestamp = datetime.fromisoformat(str(bar["timestamp"]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        local = timestamp.astimezone(IST)
        day = local.date().isoformat()
        session = state.setdefault(day, {"bars": [], "or_high": None, "or_low": None, "trades": 0,
                                         "cum_pv": 0.0, "cum_volume": 0.0})
        session["bars"].append(bar)
        typical = (bar["high"] + bar["low"] + bar["close"]) / 3
        volume = max(float(bar.get("volume", 0) or 0), 0)
        session["cum_pv"] += typical * volume
        session["cum_volume"] += volume
        vwap = session["cum_pv"] / session["cum_volume"] if session["cum_volume"] else bar["close"]

        if time(9, 15) <= local.time() < _clock(config.entry_start):
            session["or_high"] = max(session["or_high"] or bar["high"], bar["high"])
            session["or_low"] = min(session["or_low"] or bar["low"], bar["low"])

        # Execute a signal only on the following bar's open.
        if pending and pending["execute_index"] == index and position is None:
            fill = bar["open"] + tick_size * config.slippage_ticks * pending["side"]
            risk_distance = pending["risk_distance"]
            budget = capital * config.risk_per_trade_pct / 100
            lots = max(1, math.floor(budget / max(risk_distance * lot_size, 1)))
            quantity = lots * lot_size
            position = {**pending, "entry_time": bar["timestamp"], "entry": fill, "quantity": quantity,
                        "stop": fill - risk_distance * pending["side"],
                        "target": fill + risk_distance * config.reward_risk * pending["side"]}
            pending = None

        if position:
            exit_price, reason = None, None
            if position["side"] == 1:
                if bar["low"] <= position["stop"]:
                    exit_price, reason = position["stop"] - tick_size * config.slippage_ticks, "STOP"
                elif bar["high"] >= position["target"]:
                    exit_price, reason = position["target"] - tick_size * config.slippage_ticks, "TARGET"
            else:
                if bar["high"] >= position["stop"]:
                    exit_price, reason = position["stop"] + tick_size * config.slippage_ticks, "STOP"
                elif bar["low"] <= position["target"]:
                    exit_price, reason = position["target"] + tick_size * config.slippage_ticks, "TARGET"
            if local.time() >= _clock(config.forced_exit) and exit_price is None:
                exit_price, reason = bar["close"] - tick_size * config.slippage_ticks * position["side"], "TIME"
            if exit_price is not None:
                pnl = (exit_price - position["entry"]) * position["side"] * position["quantity"]
                pnl -= config.commission_per_order * 2
                capital += pnl
                session["trades"] += 1
                consecutive_losses = consecutive_losses + 1 if pnl <= 0 else 0
                trades.append({"symbol": symbol, "side": "LONG" if position["side"] == 1 else "SHORT",
                               "signal_time": position["signal_time"], "entry_time": position["entry_time"],
                               "exit_time": bar["timestamp"],
                               "entry_price": round(position["entry"], 4), "exit_price": round(exit_price, 4),
                               "quantity": position["quantity"], "pnl": round(pnl, 2), "exit_reason": reason,
                               "risk_distance": round(position["risk_distance"], 4)})
                position = None

        history = session["bars"]
        can_signal = (
            position is None and pending is None and session["or_high"] is not None
            and _clock(config.entry_start) <= local.time() <= _clock(config.entry_cutoff)
            and session["trades"] < config.max_trades_per_day
            and consecutive_losses < config.consecutive_loss_stop
            and index + 1 < len(ordered)
        )
        if can_signal:
            recent_volumes = [float(item.get("volume", 0) or 0) for item in history[-config.volume_lookback - 1:-1]]
            average_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
            relative_volume = volume / average_volume if average_volume > 0 else 0
            atr = _atr(history, config.atr_period)
            side = 1 if bar["close"] > session["or_high"] and bar["close"] > vwap else -1 if bar["close"] < session["or_low"] and bar["close"] < vwap else 0
            if side and relative_volume >= config.relative_volume_min and atr > 0:
                range_risk = abs(bar["close"] - (session["or_low"] if side == 1 else session["or_high"]))
                risk_distance = max(atr * config.stop_atr_multiple, range_risk)
                pending = {"execute_index": index + 1, "side": side, "signal_time": bar["timestamp"],
                           "risk_distance": risk_distance, "relative_volume": relative_volume, "vwap": vwap}

        peak = max(peak, capital)
        max_drawdown = max(max_drawdown, (peak - capital) / peak * 100 if peak else 0)
        equity.append({"timestamp": bar["timestamp"], "capital": round(capital, 2)})

    pnls = [trade["pnl"] for trade in trades]
    wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p <= 0]
    profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) else 0
    return {"status": "COMPLETED", "algorithm": "ORB_V1", "symbol": symbol,
            "data_source": ordered[0].get("source", "UNKNOWN"), "config": asdict(config),
            "metrics": {"initial_capital": initial_capital, "final_capital": round(capital, 2),
                        "return_pct": round((capital / initial_capital - 1) * 100, 2),
                        "trades": len(trades), "wins": len(wins), "losses": len(losses),
                        "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else 0,
                        "profit_factor": round(profit_factor, 3), "max_drawdown_pct": round(max_drawdown, 2),
                        "expectancy": round(sum(pnls) / len(pnls), 2) if pnls else 0},
            "trades": trades, "equity": equity}
