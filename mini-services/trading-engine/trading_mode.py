"""Server-enforced PAPER/LIVE mode with fail-closed live activation."""
import json
import os
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict


@dataclass
class TradingModeState:
    mode: str = "PAPER"
    broker: str = ""


class TradingModeManager:
    CONFIRMATION = "ENABLE LIVE TRADING"

    def __init__(self) -> None:
        data_dir = Path(os.getenv("ENGINE_DATA_DIR") or Path(__file__).parent / "data")
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "trading-mode.json"
        self._lock = threading.RLock()
        self.state = TradingModeState()
        self._load()
        # A restart always returns to PAPER unless the server explicitly allows
        # live trading. This prevents a stale file from silently enabling LIVE.
        if not self.live_allowed:
            self.state = TradingModeState()
            self._save()

    @property
    def live_allowed(self) -> bool:
        return os.getenv("ALLOW_LIVE_TRADING", "false").lower() == "true"

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self.state = TradingModeState(mode=raw.get("mode", "PAPER"), broker=raw.get("broker", ""))
        except (FileNotFoundError, ValueError, OSError):
            self.state = TradingModeState()

    def _save(self) -> None:
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self.state), indent=2), encoding="utf-8")
        temp.replace(self._path)

    def status(self) -> Dict:
        return {**asdict(self.state), "live_allowed": self.live_allowed, "autonomous_live_allowed": False}

    def set_paper(self) -> Dict:
        with self._lock:
            self.state = TradingModeState()
            self._save()
            return self.status()

    def set_live(self, broker: str, confirmation: str, connected: bool) -> Dict:
        broker = broker.upper()
        if not self.live_allowed:
            raise PermissionError("LIVE trading is disabled on the server")
        if confirmation != self.CONFIRMATION:
            raise PermissionError(f"Confirmation must exactly match: {self.CONFIRMATION}")
        if broker not in {"ZERODHA", "FYERS"}:
            raise ValueError("Only ZERODHA and FYERS are supported for guarded live routing")
        if not connected:
            raise ConnectionError(f"{broker} must pass a connection test before LIVE mode")
        with self._lock:
            self.state = TradingModeState(mode="LIVE", broker=broker)
            self._save()
            return self.status()


_manager = TradingModeManager()


def get_trading_mode() -> TradingModeManager:
    return _manager
