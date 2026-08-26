from intraday_research import research_intraday_strategies
from tests.test_intraday_algorithms import bars


def test_intraday_research_requires_enough_sessions():
    result = research_intraday_strategies(bars(20), "NIFTYBEES")
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["live_eligible"] is False


def test_intraday_research_never_enables_live(tmp_path):
    result = research_intraday_strategies(bars(65), "NIFTYBEES", output_path=tmp_path / "report.json")
    assert result["status"] in {"PAPER_CANDIDATE", "REJECTED"}
    assert result["paper_only"] is True
    assert result["live_eligible"] is False
    assert result["candidates_tested"] == 108
