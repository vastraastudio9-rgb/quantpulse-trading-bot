from datetime import datetime, timezone

from forward_validation import ForwardValidationRegistry
from tests.test_intraday_algorithms import bars


def candidate_report(config=None):
    return {
        "status": "PAPER_CANDIDATE", "symbol": "NIFTYBEES",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected_config": config or {"strategy": "MEAN_REVERSION", "lookback": 15, "z_entry": 1.0},
    }


def test_candidate_is_frozen_persisted_and_not_duplicated(tmp_path):
    path = tmp_path / "forward.json"
    registry = ForwardValidationRegistry(path)
    report = candidate_report()
    first = registry.register(report, "2026-01-01T00:00:00+00:00")
    second = registry.register(report, "2026-02-01T00:00:00+00:00")
    assert first["registered"] is True
    assert second["registered"] is False
    restored = ForwardValidationRegistry(path).status()
    assert len(restored["candidates"]) == 1
    assert restored["candidates"][0]["baseline_timestamp"] == "2026-01-01T00:00:00+00:00"
    assert restored["live_eligible"] is False


def test_only_post_selection_bars_count_as_forward_evidence(tmp_path):
    registry = ForwardValidationRegistry(tmp_path / "forward.json")
    sample = bars(25)
    baseline = sample[74]["timestamp"]
    registry.register(candidate_report(), baseline)
    result = registry.evaluate(sample)
    tracked = result["candidates"][0]
    expected_sessions = len({bar["timestamp"][:10] for bar in sample if bar["timestamp"] > baseline})
    assert tracked["sessions"] == expected_sessions
    assert tracked["paper_only"] is True
    assert tracked["live_eligible"] is False


def test_rejected_research_is_not_registered(tmp_path):
    registry = ForwardValidationRegistry(tmp_path / "forward.json")
    result = registry.register({"status": "REJECTED", "selected_config": {}}, "2026-01-01T00:00:00Z")
    assert result["registered"] is False
    assert registry.status()["candidates"] == []
