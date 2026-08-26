from pathlib import Path

import pytest

from main import resolve_market_import_path


def test_market_import_is_restricted_to_configured_directory(tmp_path, monkeypatch):
    allowed = tmp_path / "imports"
    allowed.mkdir()
    monkeypatch.setenv("MARKET_DATA_IMPORT_DIR", str(allowed))
    assert resolve_market_import_path("candles.csv") == (allowed / "candles.csv").resolve()

    with pytest.raises(ValueError):
        resolve_market_import_path(str(tmp_path / "outside.csv"))


def test_market_import_blocks_parent_traversal(tmp_path, monkeypatch):
    allowed = tmp_path / "imports"
    allowed.mkdir()
    monkeypatch.setenv("MARKET_DATA_IMPORT_DIR", str(allowed))
    with pytest.raises(ValueError):
        resolve_market_import_path(str(Path("..") / "secret.csv"))
