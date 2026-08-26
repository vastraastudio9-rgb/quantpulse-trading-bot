"""Deterministic, state-grounded JARVIS dashboard assistant."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict


def system_snapshot() -> Dict:
    from auto_bot import get_auto_bot
    from autonomy import get_autonomy_supervisor
    from brokers import telegram_bot, zerodha
    from paper_signal_journal import get_paper_signal_journal
    from release_manager import release_status
    from risk_engine import get_portfolio_engine
    from trade_journal import get_journal
    from trading_mode import get_trading_mode

    risk = get_portfolio_engine().status()
    bot = get_auto_bot().status()
    autonomy = get_autonomy_supervisor().status()
    journal = get_journal().analyze()
    signals = get_paper_signal_journal().recent(20)
    release = release_status()
    return {
        "mode": get_trading_mode().status()["mode"],
        "live_execution": False,
        "autonomy": {"running": autonomy["running"], "phase": autonomy["workflow_phase"],
                     "health": autonomy["health"].get("status"), "rnd": autonomy.get("rnd", {})},
        "risk": {"capital": risk["capital"], "pnl": risk["pnl"], "positions": risk["positions"],
                 "limits": risk["limits"]},
        "scanner": bot,
        "signals": signals,
        "journal": journal,
        "brokers": {"telegram": telegram_bot.is_configured(), "kite": zerodha.is_configured()},
        "release": release,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _money(value) -> str:
    return f"₹{float(value or 0):,.0f}"


def compose_answer(question: str, snapshot: Dict) -> str:
    q = (question or "").lower().strip()
    risk, scanner = snapshot["risk"], snapshot["scanner"]
    positions = risk.get("positions", [])
    limits = risk.get("limits", {})
    signals = snapshot.get("signals", [])
    prefix = "JARVIS is in PAPER mode. Live execution is OFF. "

    if any(word in q for word in ("position", "trade", "p&l", "pnl", "profit", "loss")):
        if positions:
            detail = "; ".join(
                f"{item['symbol']} {item['strategy']} {item['side']}, unrealized {_money(item.get('unrealized_pnl'))}"
                for item in positions[:4]
            )
            return prefix + f"There are {len(positions)} open paper positions: {detail}. Realized today is {_money(risk['pnl'].get('realized_today'))}."
        return prefix + f"There are no open paper positions. Realized today is {_money(risk['pnl'].get('realized_today'))}."

    if any(word in q for word in ("signal", "scanner", "setup")):
        last = scanner.get("last_scan") or {}
        recent = signals[0] if signals else None
        response = (f"The scanner is {'running' if scanner.get('running') else 'stopped'}, covering "
                    f"{len(scanner.get('symbols', []))} symbols every {scanner.get('scan_interval_seconds', 0)} seconds. ")
        if recent:
            response += f"Latest recorded paper signal is {recent.get('symbol')} {recent.get('strategy_name')}, status {recent.get('paper_status', 'detected')}. "
        if last:
            response += f"Latest scan result: {last.get('symbol', '')} {last.get('action', '')}. {last.get('reason', '')}"
        return prefix + response

    if any(word in q for word in ("risk", "safe", "kill", "limit")):
        return (prefix + f"Kill switch is {'ACTIVE' if limits.get('kill_switch') else 'inactive'}. "
                f"Daily loss lock is {'ACTIVE' if limits.get('daily_loss_lock') else 'inactive'}. "
                f"{limits.get('positions_used', len(positions))} of {limits.get('max_positions', 0)} position slots are used. "
                f"Daily loss remaining is {_money(limits.get('daily_loss_remaining'))}.")

    if any(word in q for word in ("research", "r&d", "backtest", "algo", "strategy")):
        rnd = snapshot["autonomy"].get("rnd", {})
        latest = rnd.get("latest", {})
        return (prefix + f"Research automation is {'running' if rnd.get('running') else 'idle'}. "
                f"Latest R and D result is {latest.get('status', 'not run')}. "
                "Candidates require untouched holdout and forward-paper validation before approval.")

    if any(word in q for word in ("broker", "telegram", "kite", "zerodha")):
        brokers = snapshot["brokers"]
        return (prefix + f"Telegram is {'connected' if brokers.get('telegram') else 'not connected'}. "
                f"Kite is {'connected' if brokers.get('kite') else 'not connected'}. No broker order will be placed.")

    if any(word in q for word in ("update", "version", "restart", "release")):
        release = snapshot["release"]
        state = "waiting for restart" if release.get("restart_required") else "current"
        blockers = release.get("preflight", {}).get("blockers", [])
        return prefix + f"The engine release is {state}. " + (f"Restart blockers: {', '.join(blockers)}." if blockers else "Safe restart checks pass.")

    phase = snapshot["autonomy"].get("phase", "UNKNOWN").replace("_", " ")
    return (prefix + f"Autonomy is {'running' if snapshot['autonomy'].get('running') else 'stopped'} in {phase}. "
            f"System health is {snapshot['autonomy'].get('health', 'unknown')}. There are {len(positions)} open paper positions, "
            f"unrealized P and L is {_money(risk['pnl'].get('unrealized'))}, and {len(signals)} recent paper signals are stored. "
            f"The scanner is {'running' if scanner.get('running') else 'stopped'}.")


def briefing(question: str = "What is happening in the whole system?") -> Dict:
    snapshot = system_snapshot()
    return {"answer": compose_answer(question, snapshot), "snapshot": snapshot,
            "voice_safe": True, "paper_only": True, "live_eligible": False}
