# JARVIS Research Policy

## Current paper policy

The corrected 1,095-day synthetic research run tested 90 strategy/instrument
combinations, each with nine stop/target configurations and non-overlapping
60% training, 20% validation, and 20% untouched holdout periods.

The resulting mode is `BALANCED`. Three instrument routes passed all gates:

| Instrument | Strategy | Stop | Target | Holdout trades | Holdout Sharpe | Profit factor | Max drawdown |
|---|---|---:|---:|---:|---:|---:|---:|
| FINNIFTY | Calendar Spread | 40% | 40% | 15 | 2.029 | 3.62 | 11.00% |
| CRUDEOIL | Long Straddle | 40% | 25% | 26 | 2.901 | 4.63 | 13.36% |
| XAUUSD | Calendar Spread | 30% | 40% | 15 | 0.962 | 2.74 | 1.87% |

NIFTY and BANKNIFTY were rejected because their simulated drawdown and Monte
Carlo ruin risk exceeded the policy limits. Perfect-win Forex results were also
rejected as non-credible.

## Important limitation

These results use deterministic synthetic GARCH candles. They validate the
software and selection process, not real-market profitability. JARVIS therefore
keeps this policy in paper mode. Broker historical candles, realistic option
chains, and a sufficient paper-fill record are required before human live review.
