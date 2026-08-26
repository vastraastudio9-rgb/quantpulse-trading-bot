import csv
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from market_data_store import MarketDataStore, validate_candle
from orb_algorithm import ORBConfig, run_orb_backtest


def test_candle_quality_rejects_impossible_ohlc():
    errors = validate_candle({"open": 100, "high": 99, "low": 98, "close": 101, "volume": 1})
    assert errors


def test_csv_import_tracks_provenance_and_queries(tmp_path):
    path = tmp_path / "nifty.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Open", "High", "Low", "Close", "Volume"])
        writer.writeheader()
        writer.writerow({"Date": "2025-01-01", "Open": 100, "High": 110, "Low": 95, "Close": 105, "Volume": 1000})
        writer.writerow({"Date": "2025-01-02", "Open": 105, "High": 112, "Low": 101, "Close": 108, "Volume": 1200})
    store = MarketDataStore(tmp_path / "market.duckdb")
    result = store.import_csv(path, "NSE_ARCHIVE", "NIFTY", "NSE")
    assert result["rows_accepted"] == 2
    assert result["rows_rejected"] == 0
    bars = store.bars("NIFTY", source="NSE_ARCHIVE")
    assert len(bars) == 2
    assert bars[0]["source"] == "NSE_ARCHIVE"
    assert store.catalog()[0]["rows"] == 2


def _intraday_bars(days=8):
    bars = []
    base = datetime(2025, 1, 6, 3, 45, tzinfo=timezone.utc)  # 09:15 IST
    for day in range(days):
        session = base + timedelta(days=day)
        if session.weekday() >= 5:
            continue
        price = 100 + day
        for index in range(24):
            ts = session + timedelta(minutes=5 * index)
            # Opening range then a volume-confirmed breakout and follow through.
            move = 0 if index < 3 else (index - 2) * 0.35
            close = price + move
            bars.append({"timestamp": ts.isoformat(), "open": close - 0.1, "high": close + 0.3,
                         "low": close - 0.3, "close": close, "volume": 1000 if index < 3 else 1800,
                         "source": "TEST_REAL"})
    return bars


def test_orb_replay_uses_next_bar_and_reports_source():
    result = run_orb_backtest(_intraday_bars(), "NIFTY", lot_size=1, tick_size=0.05,
                              config=ORBConfig(relative_volume_min=1.0, forced_exit="11:10"))
    assert result["status"] == "COMPLETED"
    assert result["data_source"] == "TEST_REAL"
    for trade in result["trades"]:
        assert trade["entry_time"] > trade["signal_time"]


def test_orb_empty_data_fails_closed():
    result = run_orb_backtest([], "NIFTY", 75, 0.05)
    assert result["status"] == "FAILED"


def test_orb_loss_guard_resets_each_session():
    bars = _intraday_bars(days=8)
    result = run_orb_backtest(bars, "NIFTY", 1, 0.05,
                              config=ORBConfig(relative_volume_min=1.0, reward_risk=20,
                                               consecutive_loss_stop=1, forced_exit="11:10"))
    trade_days = {trade["entry_time"][:10] for trade in result["trades"]}
    assert len(trade_days) > 1


def test_orb_missing_volume_is_explicit_and_fail_closed_by_default():
    bars = [{**bar, "volume": 0} for bar in _intraday_bars()]
    blocked = run_orb_backtest(bars, "NIFTY", 1, 0.05,
                               config=ORBConfig(relative_volume_min=1.0, forced_exit="11:10"))
    assert blocked["metrics"]["trades"] == 0
    assert blocked["volume_data_available"] is False
    assert "No trades allowed" in blocked["limitations"][0]

    research = run_orb_backtest(bars, "NIFTY", 1, 0.05,
                                config=ORBConfig(allow_missing_volume=True, forced_exit="11:10"))
    assert research["metrics"]["trades"] > 0
    assert "bypassed" in research["limitations"][0]


def test_orb_opening_range_minutes_controls_first_signal_time():
    result = run_orb_backtest(_intraday_bars(), "NIFTY", 1, 0.05,
                              config=ORBConfig(opening_range_minutes=30, relative_volume_min=1.0,
                                               forced_exit="11:10"))
    for trade in result["trades"]:
        local_signal = datetime.fromisoformat(trade["signal_time"]).astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
        )
        assert (local_signal.hour, local_signal.minute) >= (9, 45)


def test_orb_direction_filter_is_enforced():
    long_only = run_orb_backtest(_intraday_bars(), "NIFTY", 1, 0.05,
                                 config=ORBConfig(trade_direction="LONG", relative_volume_min=1.0,
                                                  forced_exit="11:10"))
    assert long_only["trades"]
    assert {trade["side"] for trade in long_only["trades"]} == {"LONG"}

    invalid = run_orb_backtest(_intraday_bars(), "NIFTY", 1, 0.05,
                               config=ORBConfig(trade_direction="INVALID"))
    assert invalid["status"] == "FAILED"
