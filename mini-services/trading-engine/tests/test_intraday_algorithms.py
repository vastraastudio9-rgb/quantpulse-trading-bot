from datetime import datetime, timedelta, timezone

from intraday_algorithms import IntradayConfig, run_intraday_backtest


def bars(days=35):
    rows = []
    start = datetime(2026, 1, 1, 3, 45, tzinfo=timezone.utc)
    for day in range(days):
        session = start + timedelta(days=day)
        if session.weekday() >= 5:
            continue
        for index in range(30):
            base = 100 + day * .1 + ((index % 8) - 4) * .25
            rows.append({"timestamp": (session + timedelta(minutes=index * 5)).isoformat(),
                         "open": base - .05, "high": base + .2, "low": base - .2,
                         "close": base, "volume": 1000 + index * 10, "source": "TEST"})
    return rows


def test_intraday_strategies_are_event_driven_and_cost_aware():
    for strategy in ("VWAP_PULLBACK", "MEAN_REVERSION"):
        result = run_intraday_backtest(bars(), "NIFTYBEES", config=IntradayConfig(strategy=strategy, z_entry=1.0))
        assert result["status"] == "COMPLETED"
        assert result["data_source"] == "TEST"
        for trade in result["trades"]:
            assert trade["entry_time"] > trade["signal_time"]


def test_intraday_algorithm_rejects_unknown_strategy():
    result = run_intraday_backtest(bars(), "NIFTYBEES", config=IntradayConfig(strategy="UNKNOWN"))
    assert result["status"] == "FAILED"
