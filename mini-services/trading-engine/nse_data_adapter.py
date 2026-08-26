"""Free NSE index history adapter backed by the open-source jugaad-data client."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Dict, Optional

from market_data_store import get_market_data_store


INDEX_NAMES = {
    "NIFTY": "NIFTY 50",
    "BANKNIFTY": "NIFTY BANK",
    "FINNIFTY": "NIFTY FINANCIAL SERVICES",
}


def download_nse_index(symbol: str, from_date: date, to_date: date,
                       raw_dir: Optional[Path] = None) -> Dict:
    """Download official NSE index history, retain raw CSV, then normalize it."""
    symbol = symbol.upper()
    if symbol not in INDEX_NAMES:
        raise ValueError(f"Unsupported NSE index: {symbol}")
    if from_date >= to_date:
        raise ValueError("from_date must be before to_date")
    try:
        from jugaad_data.nse import index_df
    except ImportError as exc:
        raise RuntimeError("jugaad-data is not installed") from exc
    frame = index_df(symbol=INDEX_NAMES[symbol], from_date=from_date, to_date=to_date)
    if frame is None or frame.empty:
        raise RuntimeError("NSE returned no index history")
    frame = frame.sort_values("HistoricalDate")
    root = raw_dir or Path(os.getenv("MARKET_DATA_DIR", Path(__file__).parent / "data" / "market")) / "raw" / "nse_index"
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{symbol}_{from_date.isoformat()}_{to_date.isoformat()}.csv"
    temp = target.with_suffix(".tmp")
    frame.to_csv(temp, index=False)
    temp.replace(target)
    imported = get_market_data_store().import_csv(target, "NSE_INDEX", symbol, "NSE", "1d")
    return {"downloaded": len(frame), "raw_file": str(target), "index_name": INDEX_NAMES[symbol], **imported}
