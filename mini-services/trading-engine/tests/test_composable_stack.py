import pytest

from composable_stack import StackConfig, get_stack_manifest


STACK_ENV = (
    "MARKET_DATA_PROVIDER", "FAST_RESEARCH_ENGINE", "VALIDATION_ENGINE",
    "EXECUTION_PROVIDER", "GREEKS_PROVIDER", "FOREX_GATEWAY",
    "SCALE_UP_ENGINE", "ALLOW_LIVE_TRADING",
)


def _clear(monkeypatch):
    for name in STACK_ENV:
        monkeypatch.delenv(name, raising=False)


def test_default_stack_is_single_route_paper_only(monkeypatch):
    _clear(monkeypatch)
    manifest = get_stack_manifest()
    assert manifest["execution_provider_count"] == 1
    assert manifest["duplicate_execution_routes_blocked"] is True
    assert manifest["research_can_place_orders"] is False
    assert manifest["paper_only"] is True
    execution = next(row for row in manifest["components"] if row["role"] == "execution")
    assert execution == {"role": "execution", "selected": "PAPER", "status": "PAPER_ONLY"}


def test_live_capable_provider_fails_back_to_paper_without_server_permission(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("EXECUTION_PROVIDER", "OPENALGO")
    config = StackConfig.from_environment()
    assert config.execution_provider == "PAPER"
    assert config.live_allowed is False


def test_optional_vectorbt_is_reported_without_becoming_execution(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("FAST_RESEARCH_ENGINE", "VECTORBT")
    manifest = get_stack_manifest()
    research = next(row for row in manifest["components"] if row["role"] == "fast_research")
    assert research["selected"] == "VECTORBT"
    assert research["status"] in {"AVAILABLE", "MISSING_OPTIONAL_DEPENDENCY"}
    assert manifest["research_can_place_orders"] is False


def test_unknown_provider_is_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("EXECUTION_PROVIDER", "KITE_AND_OPENALGO")
    with pytest.raises(ValueError, match="EXECUTION_PROVIDER"):
        StackConfig.from_environment()
