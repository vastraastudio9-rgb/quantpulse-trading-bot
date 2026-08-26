from jarvis_assistant import compose_answer


def snapshot():
    return {
        "mode": "PAPER", "live_execution": False,
        "autonomy": {"running": True, "phase": "MARKET_MONITORING", "health": "OK",
                     "rnd": {"running": False, "latest": {"status": "REJECTED"}}},
        "risk": {"capital": {}, "pnl": {"realized_today": -100, "unrealized": 250},
                 "positions": [{"symbol": "NIFTY", "strategy": "ORB", "side": "LONG", "unrealized_pnl": 250}],
                 "limits": {"kill_switch": False, "daily_loss_lock": False, "positions_used": 1,
                            "max_positions": 5, "daily_loss_remaining": 2900}},
        "scanner": {"running": True, "symbols": ["NIFTY", "BANKNIFTY"], "scan_interval_seconds": 30,
                    "last_scan": {"symbol": "NIFTY", "action": "NO_TRADE", "reason": "Mixed regime"}},
        "signals": [{"symbol": "NIFTY", "strategy_name": "ORB", "paper_status": "POSITION_OPENED"}],
        "journal": {}, "brokers": {"telegram": True, "kite": False},
        "release": {"restart_required": True, "preflight": {"blockers": ["No open paper positions"]}},
    }


def test_whole_system_briefing_is_grounded_and_paper_only():
    answer = compose_answer("What is happening?", snapshot())
    assert "PAPER mode" in answer
    assert "Live execution is OFF" in answer
    assert "1 open paper positions" in answer


def test_signal_and_risk_questions_use_relevant_state():
    signal = compose_answer("Any signals?", snapshot())
    risk = compose_answer("Is risk safe?", snapshot())
    assert "Latest recorded paper signal is NIFTY ORB" in signal
    assert "Kill switch is inactive" in risk


def test_release_and_broker_answers_never_imply_live_execution():
    release = compose_answer("Do we need an update restart?", snapshot())
    broker = compose_answer("Is Kite connected?", snapshot())
    assert "Restart blockers" in release
    assert "Kite is not connected" in broker
    assert "Live execution is OFF" in release
    assert "No broker order will be placed" in broker
