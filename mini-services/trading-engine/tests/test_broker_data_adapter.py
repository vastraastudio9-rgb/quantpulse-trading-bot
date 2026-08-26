import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import broker_data_adapter


class _Broker:
    @staticmethod
    def is_configured():
        return True

    @staticmethod
    def fetch_historical(*args):
        return [
            {"timestamp": "2025-01-02T09:20:00+05:30", "open": 101, "high": 103, "low": 100, "close": 102, "volume": 12},
            {"timestamp": "2025-01-02T09:15:00+05:30", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 10},
        ]


class _Store:
    def import_csv(self, path, source, symbol, exchange, timeframe, token):
        assert path.exists()
        assert (source, symbol, exchange, timeframe, token) == ("ZERODHA", "NIFTY", "NSE", "5m", "NIFTY 50")
        return {"rows_accepted": 2, "rows_rejected": 0, "quality": {"status": "FAIL"}}


def test_broker_download_is_normalized_without_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(broker_data_adapter, "zerodha", _Broker)
    monkeypatch.setattr(broker_data_adapter, "get_market_data_store", lambda: _Store())
    result = broker_data_adapter.download_broker_candles(
        "zerodha", "nifty", "NIFTY 50", date(2025, 1, 1), date(2025, 1, 2), raw_dir=tmp_path
    )
    assert result["downloaded"] == 2
    assert result["credentials_persisted"] is False
    assert result["rows_accepted"] == 2


def test_broker_download_fails_closed(monkeypatch, tmp_path):
    class _Unconfigured:
        @staticmethod
        def is_configured():
            return False
    monkeypatch.setattr(broker_data_adapter, "upstox", _Unconfigured)
    with pytest.raises(RuntimeError, match="not configured"):
        broker_data_adapter.download_broker_candles(
            "UPSTOX", "NIFTY", "NSE_INDEX|Nifty 50", date(2025, 1, 1), date(2025, 1, 2), raw_dir=tmp_path
        )


def test_broker_download_rejects_unsafe_ranges(tmp_path):
    with pytest.raises(ValueError, match="366 days"):
        broker_data_adapter.download_broker_candles(
            "ZERODHA", "NIFTY", "NIFTY 50", date(2023, 1, 1), date(2025, 1, 2), raw_dir=tmp_path
        )
