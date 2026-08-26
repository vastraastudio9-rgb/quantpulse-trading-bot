import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auto_bot import AutoTradingBot, BotConfig, select_policy_candidates


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


def test_valid_paper_signal_alerts_once_per_cooldown(monkeypatch):
    monkeypatch.setattr("auto_bot.telegram_bot.is_configured", lambda: True)
    sent = []
    monkeypatch.setattr("auto_bot.telegram_bot.send_alert", lambda **kwargs: sent.append(kwargs) or {"ok": True})
    bot = AutoTradingBot(BotConfig(signal_alert_cooldown_minutes=15))
    signal = {
        "symbol": "NIFTY", "strategy_key": "OPENING_RANGE_BREAKOUT", "strategy_name": "ORB",
        "direction": "BULLISH", "confidence": 70, "entry_price": 100,
        "stop_loss": 90, "target": 120, "paper_execution_eligible": True,
    }
    first = bot._notify_paper_signal(signal, "TRENDING_UP_STABLE", "PAPER_RND")
    second = bot._notify_paper_signal(signal, "TRENDING_UP_STABLE", "PAPER_RND")
    assert first["sent"] is True
    assert second["sent"] is False
    assert second["reason"] == "Signal alert cooldown"
    assert len(sent) == 1
    assert "PAPER ONLY" in sent[0]["message"]
    assert bot.status()["paper_signal_alerts"]["sent_total"] == 1


def test_structurally_invalid_signal_is_not_alerted(monkeypatch):
    monkeypatch.setattr("auto_bot.telegram_bot.is_configured", lambda: True)
    monkeypatch.setattr("auto_bot.telegram_bot.send_alert", lambda **kwargs: {"ok": True})
    bot = AutoTradingBot()
    result = bot._notify_paper_signal({"paper_execution_eligible": False}, "MIXED", "PAPER_RND")
    assert result["sent"] is False
    assert bot.status()["paper_signal_alerts"]["sent_total"] == 0
