"""Release identity and fail-closed restart readiness for the local engine."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]


def git_head() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
            text=True, timeout=3, check=True,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


BOOT_COMMIT = git_head()
BOOTED_AT = datetime.now(timezone.utc).isoformat()


def restart_preflight(open_positions: int, mode: str, telegram_configured: bool,
                      encrypted_vault_configured: bool) -> Dict:
    checks = [
        {"key": "paper_mode", "label": "Trading mode is PAPER", "ok": mode == "PAPER"},
        {"key": "flat_portfolio", "label": "No open paper positions", "ok": open_positions == 0},
        {"key": "telegram_recovery", "label": "Telegram can recover after restart",
         "ok": not telegram_configured or encrypted_vault_configured},
    ]
    blockers = [check["label"] for check in checks if not check["ok"]]
    return {"safe_to_restart": not blockers, "checks": checks, "blockers": blockers,
            "live_execution_allowed": False}


def release_status() -> Dict:
    from brokers import telegram_bot
    from risk_engine import get_portfolio_engine
    from secret_store import LocalSecretStore
    from trading_mode import get_trading_mode

    workspace_commit = git_head()
    risk = get_portfolio_engine().status()
    mode = get_trading_mode().status()["mode"]
    preflight = restart_preflight(
        int(risk.get("exposure", {}).get("positions", 0)), mode,
        telegram_bot.is_configured(), LocalSecretStore().configured(),
    )
    return {
        "boot_commit": BOOT_COMMIT, "workspace_commit": workspace_commit,
        "booted_at": BOOTED_AT,
        "restart_required": bool(BOOT_COMMIT and workspace_commit and BOOT_COMMIT != workspace_commit),
        "preflight": preflight, "paper_only": True, "live_eligible": False,
    }
