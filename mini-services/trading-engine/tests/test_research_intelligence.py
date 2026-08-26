from datetime import datetime, timedelta, timezone

from research_intelligence import ExperimentRegistry, StrategyIntelligence, backup_research_state


def test_experiment_registry_is_immutable_and_never_live(tmp_path):
    registry = ExperimentRegistry(tmp_path / "experiments.jsonl")
    args = ("ORB", "NIFTY", {"range": 15}, {"source": "KITE", "hash": "abc"},
            {"holdout": {"trades": 20}}, "HOLDOUT", "PAPER_CANDIDATE")
    first = registry.register(*args)
    duplicate = registry.register(*args)
    assert first["registered"] is True
    assert first["experiment"]["live_eligible"] is False
    assert duplicate["registered"] is False
    assert registry.status()["experiments"] == 1


def test_intelligence_separates_actual_and_shadow_and_detects_drift():
    actual = []
    for i in range(20):
        actual.append({"strategy": "ORB", "regime_at_entry": "TREND", "pnl": 100})
    for i in range(10):
        actual.append({"strategy": "ORB", "regime_at_entry": "TREND", "pnl": -50})
    shadow = [{"strategy": "ORB", "regime": "RANGE", "pnl": 10000}]
    result = StrategyIntelligence.analyze(actual, shadow, recent_window=10)
    assert result["actual_trades"] == 30 and result["shadow_trades"] == 1
    assert result["drift"]["ORB"]["status"] == "QUARANTINE_REVIEW"
    assert result["regime_performance"]["ORB|RANGE"]["promotion_evidence"] == 0
    assert result["meta_label"]["status"] == "INSUFFICIENT_ACTUAL_LABELS"
    assert result["meta_label"]["shadow_labels_accepted"] is False


def test_signal_ranking_penalizes_regime_and_existing_exposure():
    base = {"paper_execution_eligible": True, "confidence": 70, "symbol": "NIFTY"}
    signals = [{**base, "strategy_key": "ORB"}, {**base, "strategy_key": "CONDOR", "symbol": "GOLD"}]
    governance = {"ORB": {"state": "PAPER_LEARNING"}, "CONDOR": {"state": "PAPER_LEARNING"}}
    ranked = StrategyIntelligence.rank_signals(signals, ["CONDOR"], governance, [{"symbol": "NIFTY"}])
    assert ranked[0]["strategy_key"] == "CONDOR"
    assert all(item["live_eligible"] is False for item in ranked)


def test_backup_excludes_secret_files_and_expires_old_directories(tmp_path):
    (tmp_path / "journal.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "secret_vault.json").write_text("do-not-copy", encoding="utf-8")
    old = tmp_path / "backups" / "2025-01-01"
    old.mkdir(parents=True)
    result = backup_research_state(tmp_path, retention_days=14,
                                   now=datetime(2026, 1, 20, tzinfo=timezone.utc))
    target = tmp_path / "backups" / "2026-01-20"
    assert (target / "journal.jsonl").exists()
    assert not (target / "secret_vault.json").exists()
    assert result["contains_secrets"] is False and not old.exists()
