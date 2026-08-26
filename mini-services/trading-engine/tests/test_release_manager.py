from release_manager import restart_preflight


def test_restart_requires_flat_paper_portfolio_and_secret_recovery():
    result = restart_preflight(1, "PAPER", True, False)
    assert result["safe_to_restart"] is False
    assert "No open paper positions" in result["blockers"]
    assert "Telegram can recover after restart" in result["blockers"]
    assert result["live_execution_allowed"] is False


def test_restart_is_safe_when_flat_and_encrypted():
    result = restart_preflight(0, "PAPER", True, True)
    assert result["safe_to_restart"] is True
    assert result["blockers"] == []


def test_restart_never_accepts_live_mode():
    result = restart_preflight(0, "LIVE", False, False)
    assert result["safe_to_restart"] is False
    assert "Trading mode is PAPER" in result["blockers"]
