# JARVIS Research Policy

## Current paper policy

JARVIS now has 1,400 official NSE NIFTY 50 daily candles from 2021-01-01
through 2026-08-25. All rows passed the normalized-data quality gate and the
research run is labeled `NSE_INDEX` / `REAL_MARKET`.

The resulting mode is `RISK_OFF`. No strategy passed the full train,
validation, untouched holdout, drawdown, and Monte Carlo gates. JARVIS will
therefore place no autonomous trades from this policy. This rejection is the
correct safe outcome; it must not be overridden by selecting the best-looking
in-sample result.

## Important limitation

Daily index OHLC cannot accurately replay intraday ORB fills or option
strategies. Genuine five-minute broker candles, historical option chains with
bid/ask data, costs, and a sufficient forward paper-fill record are still
required. Live trading remains disabled and requires a separate human review.
