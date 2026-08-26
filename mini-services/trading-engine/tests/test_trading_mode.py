import os

import pytest

from trading_mode import TradingModeManager
from live_execution import execute_live_legs


def test_live_mode_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ALLOW_LIVE_TRADING", raising=False)
    manager = TradingModeManager()
    with pytest.raises(PermissionError):
        manager.set_live("ZERODHA", manager.CONFIRMATION, connected=True)
    assert manager.status()["mode"] == "PAPER"


def test_live_mode_requires_exact_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    manager = TradingModeManager()
    with pytest.raises(PermissionError):
        manager.set_live("ZERODHA", "yes", connected=True)


def test_live_mode_requires_connected_supported_broker(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    manager = TradingModeManager()
    with pytest.raises(ConnectionError):
        manager.set_live("ZERODHA", manager.CONFIRMATION, connected=False)
    with pytest.raises(ValueError):
        manager.set_live("UNKNOWN", manager.CONFIRMATION, connected=True)


def test_live_router_fails_closed_while_paper():
    result = execute_live_legs([{"tradingsymbol": "TEST", "action": "BUY", "quantity": 1}])
    assert result["accepted"] is False
    assert result["orders"] == []
