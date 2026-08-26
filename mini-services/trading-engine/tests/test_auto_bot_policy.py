import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auto_bot import select_policy_candidates


def test_risk_off_keeps_paper_rnd_candidates_active():
    candidates, scope = select_policy_candidates(
        ["MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT"],
        {"mode": "RISK_OFF", "approved_by_symbol": {}}, "NIFTY", "PAPER",
    )
    assert candidates == ["MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT"]
    assert scope == "PAPER_RND"


def test_unapproved_candidates_are_blocked_outside_paper():
    candidates, scope = select_policy_candidates(
        ["MOMENTUM_SCALPER"], {"mode": "RISK_OFF", "approved_by_symbol": {}}, "NIFTY", "LIVE",
    )
    assert candidates == []
    assert scope == "LIVE_POLICY_BLOCKED"


def test_validated_policy_remains_narrow():
    candidates, scope = select_policy_candidates(
        ["MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT"],
        {"approved_by_symbol": {"NIFTY": {"strategy": "OPENING_RANGE_BREAKOUT"}}}, "NIFTY", "PAPER",
    )
    assert candidates == ["OPENING_RANGE_BREAKOUT"]
    assert scope == "VALIDATED_POLICY"
