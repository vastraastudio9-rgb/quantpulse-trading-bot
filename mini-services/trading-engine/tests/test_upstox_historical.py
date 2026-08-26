import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brokers import upstox


def test_upstox_historical_uses_v3_date_order_and_encodes_key(monkeypatch):
    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"data": {"candles": [["2025-01-02T09:15:00+05:30", 1, 2, 0.5, 1.5, 10, 4]]}}

    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return _Response()

    monkeypatch.setattr(upstox, "is_configured", lambda: True)
    import requests
    monkeypatch.setattr(requests, "get", fake_get)
    result = upstox.fetch_historical("NSE_INDEX|Nifty 50", "5minute", "2025-01-01", "2025-01-02")
    assert "/v3/historical-candle/NSE_INDEX%7CNifty%2050/minutes/5/2025-01-02/2025-01-01" in captured["url"]
    assert result[0]["open_interest"] == 4
