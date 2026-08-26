import os
import sys
from datetime import date

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import nse_data_adapter


class _Store:
    def import_csv(self, path, source, symbol, exchange, timeframe):
        assert path.exists()
        assert (source, symbol, exchange, timeframe) == ("NSE_INDEX", "NIFTY", "NSE", "1d")
        return {"rows_accepted": 2, "rows_rejected": 0}


def test_download_nse_index_retains_raw_and_imports(monkeypatch, tmp_path):
    frame = pd.DataFrame([
        {"HistoricalDate": "02 Jan 2025", "OPEN": 101, "HIGH": 104, "LOW": 100, "CLOSE": 103},
        {"HistoricalDate": "01 Jan 2025", "OPEN": 100, "HIGH": 103, "LOW": 99, "CLOSE": 101},
    ])
    monkeypatch.setattr("jugaad_data.nse.index_df", lambda **kwargs: frame)
    monkeypatch.setattr(nse_data_adapter, "get_market_data_store", lambda: _Store())

    result = nse_data_adapter.download_nse_index(
        "nifty", date(2025, 1, 1), date(2025, 1, 3), raw_dir=tmp_path
    )

    assert result["downloaded"] == 2
    assert result["rows_accepted"] == 2
    assert result["index_name"] == "NIFTY 50"
    assert (tmp_path / "NIFTY_2025-01-01_2025-01-03.csv").exists()


def test_download_nse_index_rejects_invalid_request(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        nse_data_adapter.download_nse_index("SENSEX", date(2025, 1, 1), date(2025, 1, 3), tmp_path)
    with pytest.raises(ValueError, match="before"):
        nse_data_adapter.download_nse_index("NIFTY", date(2025, 1, 3), date(2025, 1, 3), tmp_path)
