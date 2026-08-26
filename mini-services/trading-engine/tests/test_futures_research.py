import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from futures_research import apply_liquidity_gate, near_month_stock_futures, run_futures_orb_batch


def _future(name, symbol, expiry, token, segment="NFO-FUT", instrument_type="FUT"):
    return {
        "name": name, "tradingsymbol": symbol, "expiry": expiry,
        "instrument_token": token, "exchange": "NFO", "segment": segment,
        "instrument_type": instrument_type, "lot_size": 100, "tick_size": .05,
    }


def test_near_month_excludes_indices_expired_and_far_month():
    items = [
        _future("RELIANCE", "RELIANCE26AUGFUT", date(2026, 8, 27), 1),
        _future("RELIANCE", "RELIANCE26SEPFUT", date(2026, 9, 24), 2),
        _future("NIFTY", "NIFTY26AUGFUT", date(2026, 8, 27), 3),
        _future("TCS", "TCS26JULFUT", date(2026, 7, 30), 4),
    ]
    result = near_month_stock_futures(items, date(2026, 8, 1))
    assert [row["tradingsymbol"] for row in result] == ["RELIANCE26AUGFUT"]


def test_liquidity_gate_requires_price_volume_and_open_interest():
    contracts = near_month_stock_futures([
        _future("RELIANCE", "RELIANCE26AUGFUT", date(2026, 8, 27), 1),
        _future("TCS", "TCS26AUGFUT", date(2026, 8, 27), 2),
    ], date(2026, 8, 1))
    quotes = {
        "NFO:RELIANCE26AUGFUT": {"last_price": 1400, "volume": 20000, "oi": 9000},
        "NFO:TCS26AUGFUT": {"last_price": 3100, "volume": 500, "oi": 9000},
    }
    result = apply_liquidity_gate(contracts, quotes, 10000, 5000)
    assert [row["underlying"] for row in result] == ["RELIANCE"]


class FakeKite:
    def quote(self, keys):
        return {key: {"last_price": 100, "volume": 20000, "oi": 9000} for key in keys}

    def historical_data(self, token, start, end, interval, oi=False):
        # Deliberately too little evidence: the pipeline must reject, not approve.
        return [{"date": start + timedelta(minutes=5 * i), "open": 100, "high": 101,
                 "low": 99, "close": 100.5, "volume": 1000, "oi": 7000} for i in range(20)]


def test_batch_fails_closed_on_short_contract_history(tmp_path):
    instruments = [_future("RELIANCE", "RELIANCE26AUGFUT", date(2026, 8, 27), 1)]
    report = run_futures_orb_batch(FakeKite(), instruments, date(2026, 8, 1), date(2026, 8, 26),
                                   output_path=tmp_path / "report.json")
    assert report["approved_paper_count"] == 0
    assert report["results"][0]["research"]["rollover_archive_required"] is True
    assert report["live_eligible"] is False
