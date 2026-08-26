from datetime import date

from kite_rnd_pipeline import run_nifty_orb_pipeline


class FakeStore:
    def __init__(self, status="PASS"):
        self.status = status

    def quality(self, symbol, timeframe, source):
        return {"status": self.status, "score": 100 if self.status == "PASS" else 70, "rows": 150}

    def bars(self, symbol, timeframe, source):
        return [{"timestamp": "2026-08-01T09:15:00+05:30", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10}]


def fake_download(*args):
    assert args[:3] == ("ZERODHA", "NIFTY", "NIFTY 50")
    return {"downloaded": 150, "credentials_persisted": False}


def test_kite_pipeline_runs_backtest_only_after_quality_passes():
    result = run_nifty_orb_pipeline(
        days=120,
        end_date=date(2026, 8, 26),
        downloader=fake_download,
        store_factory=lambda: FakeStore(),
        backtester=lambda *args: {"status": "COMPLETED", "metrics": {"total_trades": 3}},
    )
    assert result["status"] == "COMPLETED"
    assert result["paper_only"] is True
    assert result["live_eligible"] is False
    assert result["backtest"]["metrics"]["total_trades"] == 3


def test_kite_pipeline_fails_closed_on_bad_data():
    result = run_nifty_orb_pipeline(
        downloader=fake_download,
        store_factory=lambda: FakeStore("FAIL"),
        backtester=lambda *args: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert result["status"] == "DATA_REJECTED"
    assert result["backtest"] is None
