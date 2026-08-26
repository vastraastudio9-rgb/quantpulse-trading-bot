"""Safety and orchestration tests for JARVIS autonomy supervisor."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from autonomy import AutonomySupervisor, automation_readiness


def test_automation_readiness_is_evidence_based_and_excludes_live():
    result = automation_readiness([
        {"key": "one", "label": "One", "ok": True},
        {"key": "two", "label": "Two", "ok": False},
    ])
    assert result["score_pct"] == 50
    assert result["blockers"] == ["Two"]
    assert result["live_execution_automated"] is False


def test_supervisor_defaults_to_disabled_and_paper_only(tmp_path):
    supervisor = AutonomySupervisor(tmp_path)
    status = supervisor.status()
    assert status["enabled"] is False
    assert status["running"] is False
    assert status["paper_only"] is True
    assert status["promotion"]["automatic_live_activation"] is False


def test_configuration_is_bounded_and_persisted(tmp_path):
    supervisor = AutonomySupervisor(tmp_path)
    supervisor.configure({"risk_per_trade_pct": 50, "heartbeat_seconds": 1, "max_hold_minutes": 9999})
    assert supervisor.config.risk_per_trade_pct == 1.0
    assert supervisor.config.heartbeat_seconds == 5
    assert supervisor.config.max_hold_minutes == 1440
    restored = AutonomySupervisor(tmp_path)
    assert restored.config.risk_per_trade_pct == 1.0


def test_decision_journal_round_trip(tmp_path):
    supervisor = AutonomySupervisor(tmp_path)
    supervisor.record_decision("TEST", "NIFTY", "Safety gate", {"accepted": False})
    decisions = supervisor.decisions()
    assert decisions[0]["action"] == "TEST"
    assert decisions[0]["context"]["accepted"] is False


def test_position_sizing_returns_exchange_lots(tmp_path, monkeypatch):
    import risk_engine
    risk_engine._portfolio_engine = None
    monkeypatch.setenv("ENGINE_DATA_DIR", str(tmp_path / "risk"))
    supervisor = AutonomySupervisor(tmp_path / "autonomy")
    sizing = supervisor.position_size({
        "symbol": "NIFTY", "entry_price": 100, "stop_loss": 130, "confidence": 80,
    })
    assert sizing["quantity"] >= 75
    assert sizing["quantity"] % 75 == 0
    assert sizing["risk_budget"] > 0


def test_sparse_history_stays_paper_learning(tmp_path):
    supervisor = AutonomySupervisor(tmp_path)
    governance = supervisor.strategy_governance()["strategies"]
    assert governance
    assert all(item["state"] == "PAPER_LEARNING" for item in governance.values())


def test_rnd_runs_in_background_persists_and_never_enables_live(tmp_path, monkeypatch):
    supervisor = AutonomySupervisor(tmp_path)
    monkeypatch.setattr(supervisor, "_execute_rnd", lambda: {
        "status": "PAPER_CANDIDATE", "sessions": 60, "candidates_tested": 108,
        "paper_only": True, "live_eligible": False,
    })
    started = supervisor.trigger_rnd()
    assert started["started"] is True
    assert started["paper_only"] is True
    supervisor._rnd_thread.join(timeout=2)
    assert supervisor._rnd_running is False
    assert supervisor.status()["rnd"]["latest"]["status"] == "PAPER_CANDIDATE"
    assert supervisor.status()["rnd"]["latest"]["live_eligible"] is False
    assert AutonomySupervisor(tmp_path).status()["rnd"]["latest"]["status"] == "PAPER_CANDIDATE"
    assert supervisor.trigger_rnd()["status"] == "ALREADY_RUN_TODAY"


def test_rnd_trigger_is_non_blocking_and_records_failure(tmp_path, monkeypatch):
    supervisor = AutonomySupervisor(tmp_path)

    def fail_later():
        time.sleep(.05)
        raise RuntimeError("quality gate failed")

    monkeypatch.setattr(supervisor, "_execute_rnd", fail_later)
    started_at = time.monotonic()
    assert supervisor.trigger_rnd(force=True)["started"] is True
    assert time.monotonic() - started_at < .2
    supervisor._rnd_thread.join(timeout=2)
    status = supervisor.status()["rnd"]
    assert status["running"] is False
    assert status["latest"]["status"] == "FAILED"
    assert "quality gate failed" in status["latest"]["error"]
