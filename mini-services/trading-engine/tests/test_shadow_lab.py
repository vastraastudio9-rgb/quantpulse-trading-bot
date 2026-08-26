from datetime import datetime, timedelta, timezone

from shadow_lab import ShadowPaperLab


def signal(strategy="STRADDLE_BUY", price=100.0, stop=80.0, target=120.0):
    return {
        "strategy_key": strategy,
        "symbol": "NIFTY",
        "entry_price": price,
        "stop_loss": stop,
        "target": target,
        "confidence": 70,
        "legs": [{"action": "BUY"}],
        "paper_execution_eligible": True,
    }


def test_debit_shadow_path_closes_and_never_becomes_live(tmp_path):
    lab = ShadowPaperLab(tmp_path / "shadow.json")
    opened = lab.observe(signal(), "TRENDING_UP_STABLE", True, 75, .05,
                         datetime(2026, 1, 1, tzinfo=timezone.utc))
    closed = lab.observe(signal(price=121), "TRENDING_UP_STABLE", True, 75, .05,
                         datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))
    assert opened["paper_only"] is True and opened["live_eligible"] is False
    assert closed["closed"]["exit_reason"] == "TARGET_HIT"
    assert closed["closed"]["pnl"] > 0
    assert lab.status()["live_eligible"] is False


def test_credit_shadow_direction_and_persistence(tmp_path):
    path = tmp_path / "shadow.json"
    lab = ShadowPaperLab(path)
    opened_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    lab.observe(signal("STRADDLE_SELL", 100, 120, 70), "RANGE_BOUND_TIGHT", False, 35, .05, opened_at)
    result = lab.observe(signal("STRADDLE_SELL", 69, 120, 70), "RANGE_BOUND_TIGHT", False, 35, .05,
                         opened_at + timedelta(minutes=5))
    assert result["closed"]["pnl"] > 0
    restored = ShadowPaperLab(path).status()
    assert restored["by_strategy"]["STRADDLE_SELL"]["counterfactual_trades"] == 1
    assert "Not eligible for strategy promotion" in restored["limitations"]


def test_invalid_signal_is_not_recorded(tmp_path):
    lab = ShadowPaperLab(tmp_path / "shadow.json")
    bad = signal()
    bad["paper_execution_eligible"] = False
    result = lab.observe(bad, "MIXED", False, 1, .05)
    assert result["accepted"] is False
    assert lab.status()["observations"] == 0
