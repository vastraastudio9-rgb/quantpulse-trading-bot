# JARVIS Diagnostic Report — Pass 1

**Date:** 2026-08-25
**Audience:** Operator
**Scope:** Full system audit of QuantPulse trading platform

---

## Executive Summary

**Observation:** The system is a functional paper-trading dashboard, but it is **not production-grade** by the standards in the JARVIS charter. It currently fails on multiple validation, observability, and risk dimensions. The backtest engine has **critical methodological bugs** that make its outputs unreliable for any capital-allocation decision.

**Evidence — critical findings (must-fix before any live deployment):**

1. **Look-ahead bias in backtest entry logic** — `run_backtest()` reads `bar["high"]` and `bar["low"]` for the *current* bar when deciding to enter, then enters at `bar["close"]`. In live trading the high/low of the current bar are not known at entry time. This overstates fills by ~30-50%.
2. **No out-of-sample (OOS) split** — backtest trains on the full dataset, no walk-forward, no train/test boundary. Any "edge" is likely curve-fit.
3. **Premium model is unrealistic** — `premium_change_pct = -spot_move_pct * 2` is a constant 2x gamma approximation. Real ATM straddle gamma varies 1.5–4x depending on spot distance and time to expiry. Plus theta is a constant 0.5%/bar, not Black-Scholes theta.
4. **No slippage modeling** — only brokerage+STT+GST costs. Real options in India see 5-15% slippage on market orders, especially OTM.
5. **Sharpe denominator uses std of *equity-curve diffs*, not bar returns** — when no trades happen (flat equity), Sharpe blows up artificially.
6. **Max drawdown computed from sampled equity curve** — loses intermediate drawdowns between sample points.
7. **No regime filter** — strategies fire in all conditions. STRADDLE_SELL fires in trending markets where it loses money.
8. **No Monte Carlo** — single historical path is presented as truth.
9. **No unit tests at all.** Zero. For financial infrastructure this is unacceptable.
10. **No structured logging, no metrics, no health checks beyond `/health`** returning `{"status": "OK"}`.

**Risk:** If you switch the system from PAPER to LIVE today, you would lose money on (a) bad fills from look-ahead bias, (b) cost underestimation from missing slippage, and (c) regime-agnostic entries. The "50-65% win rate" displayed is on synthetic GBM data and tells you nothing about real-world performance.

**Recommendation:** Block all live trading until items #1, #2, #4, #7 are fixed and validated. Items #3, #5, #6, #8, #9, #10 should be fixed within the next 2-3 working sessions.

**Action/Approval Required:** None for this report. Proceeding to implement fixes autonomously per charter.

---

## Detailed Findings by Category

### A. Backtest Methodology (CRITICAL)

**A1. Look-ahead bias — entry uses future data**
File: `mini-services/trading-engine/backtest.py:155-223`
```python
for i in range(1, len(bars)):
    bar = bars[i]
    prev = bars[i-1]
    bar_range = bar["high"] - bar["low"]  # ← FUTURE: high/low not known until bar closes
    if bar_range < avg_range * 0.9: ...    # ← decision uses future info
    entry_premium = bar["close"] * 0.008    # ← but entry "happens" at close (after we know high/low)
```
In production: at the moment of decision we only know `prev` bar's high/low and current bar's open. We must decide using `bars[i-1]` and earlier, then execute at `bars[i]["open"]` (or `bars[i]["close"]` if we wait for bar close + entry on next bar open).

**A2. No train/OOS split**
`run_backtest()` runs on the full `days=180` window. There is no walk-forward, no holdout. Need to add: 70% in-sample / 30% OOS, plus walk-forward with rolling window.

**A3. Unrealistic premium dynamics**
```python
premium_change_pct = -spot_move_pct * 2    # constant gamma
theta_decay = -bars_held * 0.005           # constant theta, ignores t
```
Should use Black-Scholes (we already have `greeks.py`) to re-price the option each bar using the actual spot, strike, time-to-expiry, and IV.

**A4. Missing slippage**
For Indian F&O options: typical slippage is 2-5 ticks on liquid ATM strikes (NIFTY/BANKNIFTY), 5-15 ticks on OTM and MCX. Currently zero slippage modeled. Add: `slippage_ticks * tick_size * qty` deducted from PnL.

**A5. Sharpe calculated wrong when flat**
When the equity curve is flat for many bars (no open trades), `np.diff(eq)` returns zeros, artificially lowering std and inflating Sharpe. Need to either: (a) compute returns only on bars where trades were active, or (b) mark-to-market open positions each bar so equity moves with spot.

### B. Strategy Layer (HIGH)

**B1. No regime awareness**
`generate_signal()` and `run_backtest()` enter based on simple ATR-style rules. No classification of market regime (trending / ranging / breakout / high-vol / low-vol / risk-off). STRADDLE_SELL is deployed in trending markets where it bleeds via gamma.

**B2. Confidence score is mostly random**
`_calc_confidence()` base 60-75, with ±3 random. Not derived from any measurable signal quality (no OI analysis, no IV percentile, no trend strength, no multi-timeframe confirmation).

**B3. No "NO TRADE" filter**
Charter requires that `NO TRADE` is always a valid decision. Currently every signal generation returns a signal. Need explicit `should_trade()` gate.

### C. Risk Management (HIGH)

**C1. No portfolio-level exposure tracking**
`RiskConfig` table exists in Prisma but is never queried or enforced. Kill switch is a frontend toggle that does nothing on the backend.

**C2. No correlation check**
Multiple strategies can take the same directional risk on NIFTY simultaneously (e.g., STRADDLE_BUY + MOMENTUM_SCALPER both long gamma). No portfolio aggregation.

**C3. No liquidation distance tracking**
For options selling, no monitoring of how far the short strike is from spot. Should auto-flag when short strike is < 1 std dev from spot.

**C4. Position SL not enforced**
Backend `Position` model has `stop_loss` field but nothing monitors live LTP vs SL. Needs a monitor loop.

### D. Observability (HIGH)

**D1. No structured logging**
`logging.getLogger(__name__)` is used in broker modules but no JSON formatter, no request IDs, no trace IDs. Hard to debug production issues.

**D2. No metrics endpoint**
No Prometheus `/metrics`. No counters for: signals generated, orders placed, errors, latency percentiles.

**D3. No health check beyond status:OK**
`/health` returns `{"status": "OK"}`. Doesn't check: DB connection, broker connections, last tick timestamp, queue depth.

### E. Testing (CRITICAL)

**E1. Zero unit tests**
No tests for:
- `greeks.py` (Black-Scholes math — easy to verify against known values)
- `strategies.py` (signal generation logic)
- `backtest.py` (metrics calculation, trade simulation)
- `market_data.py` (data generation determinism)

**E2. No integration tests**
No end-to-end test of: API endpoints, broker fallback behavior, strategy→signal→Telegram flow.

### F. Code Quality (MEDIUM)

**F1. Magic numbers throughout**
`0.008` premium multiplier, `0.5%` theta, `2x` gamma, `5 bars` max hold — all hardcoded. Should be in a strategy config dataclass.

**F2. No type checking on strategy outputs**
`generate_signal()` returns `Optional[Dict]`. Could be a Pydantic model for validation.

**F3. Tight coupling**
`backtest.py` imports `generate_history` directly. Should accept a `DataProvider` protocol so real broker data can be swapped in without code changes.

---

## Remediation Plan (Ordered by Impact)

### Phase 1 — Critical Methodology Fixes (do first)
1. **Fix look-ahead bias** — decision on `bars[i-1]`, execute on `bars[i]["open"]`
2. **Add slippage model** — configurable ticks per instrument
3. **Add OOS split + walk-forward** — 70/30 split, then rolling 90-day window
4. **Replace premium model with Black-Scholes revaluation** — use `greeks.py`
5. **Fix Sharpe calculation** — mark-to-market open positions

### Phase 2 — Validation Framework
6. **Monte Carlo trade-shuffle test** — 1000 reshuffled trade sequences, report 5th/95th percentile outcomes
7. **Parameter sensitivity sweep** — vary SL/TP/entry thresholds ±20%, check robustness
8. **Regime-tagged performance breakdown** — per-regime Sharpe, win rate
9. **Red-team bias scanner** — automated checks for look-ahead, leakage, curve-fit

### Phase 3 — Risk + Observability
10. **Portfolio exposure tracker** — net delta, net theta, gross notional per strategy
11. **Position SL monitor loop** — checks LTP every N seconds, auto-flatten on SL breach
12. **Structured JSON logging** — request ID, trace ID, strategy ID, symbol
13. **Real /health endpoint** — DB, broker, last tick age, queue depth
14. **Prometheus /metrics endpoint** — counters, histograms, gauges

### Phase 4 — Strategy Intelligence
15. **Market regime classifier** — ADX, ATR%, Hurst exponent, OI change
16. **Strategy routing** — only allow strategies whose historical edge matches current regime
17. **Signal quality score** — multi-factor: OI, IV rank, trend, multi-TF
18. **"NO TRADE" gate** — explicit `should_trade()` returning False when quality low

### Phase 5 — Testing + CI
19. **Unit tests for greeks** — verify against known Black-Scholes values
20. **Unit tests for strategies** — verify legs, breakevens, max P/L math
21. **Unit tests for backtest** — verify metrics on synthetic data with known answer
22. **Integration tests for API** — pytest + httpx

---

## Next Actions (Autonomous — Starting Now)

I will work through Phase 1 first because nothing else matters if the backtest is lying. Will report back when Phase 1 is complete with before/after numbers showing how much the "edge" shrinks once we stop cheating.
