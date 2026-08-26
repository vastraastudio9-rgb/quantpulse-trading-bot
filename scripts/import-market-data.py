"""Import normalized NSE or broker candle CSV data into JARVIS."""
import argparse
import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "mini-services" / "trading-engine"
sys.path.insert(0, str(ENGINE))

from market_data_store import get_market_data_store


def main() -> int:
    parser = argparse.ArgumentParser(description="Import candles with provenance and quality validation")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--source", default="NSE_ARCHIVE")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--timeframe", default="1d", choices=["1m", "5m", "15m", "1h", "1d"])
    parser.add_argument("--instrument-token", default="")
    parser.add_argument("--export-parquet", action="store_true")
    args = parser.parse_args()
    store = get_market_data_store()
    result = store.import_csv(args.csv, args.source, args.symbol, args.exchange,
                              args.timeframe, args.instrument_token)
    if args.export_parquet:
        result["parquet"] = store.export_parquet()
    print(json.dumps(result, indent=2))
    return 0 if result["rows_accepted"] and result["quality"]["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
