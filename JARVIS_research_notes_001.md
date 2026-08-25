# JARVIS Research Notes — Strategy Edge Hypotheses

**Document:** JARVIS-RN-001
**Date:** 2026-08-25
**Author:** JARVIS (autonomous Quant CTO)
**Status:** Active research

---

## Executive Summary

Tested 10 strategies through the full JARVIS validation pipeline. **All 10 were rejected.** This is the correct answer — the system is working as designed. The rejections fall into two categories:

1. **Genuine losers** (6 strategies): Monte Carlo 5th-percentile Sharpe ≤ 0. These strategies lose money on synthetic data and would lose money on real data.

2. **Curve-fit suspects** (4 strategies): Red-team audit rejects for Sharpe > 3.0, Profit Factor > 3.0, or Return/DD > 5. These look profitable but are statistically suspicious — the "edge" is an artifact of synthetic data, not a real market inefficiency.

**No strategy is currently safe to deploy to live capital.**

---

## Strategy Validation Results (NIFTY, 180 days)

| Strategy | Trades | WR | Return % | Sharpe | MC p5 Sharpe | Verdict |
|----------|--------|-----|---------|--------|-------------|---------|
| STRADDLE_SELL | 17 | 24% | -513% | 1.76 | -3.70 | REJECTED (MC) |
| STRANGLE_SELL | 16 | 25% | -232% | 0.72 | -4.64 | REJECTED (MC) |
| STRADDLE_BUY | 21 | 71% | +452% | 4.86 | +8.82 | REJECTED (Red-team: Sharpe > 3) |
| IRON_CONDOR | 16 | 31% | -133% | 1.24 | -5.80 | REJECTED (MC) |
| IRON_BUTTERFLY | 16 | 31% | -246% | -2.16 | -3.97 | REJECTED (MC) |
| LONG_BUTTERFLY | 16 | 31% | -58% | -2.33 | -11.45 | REJECTED (MC) |
| CALENDAR_SPREAD | 8 | 88% | +58% | 3.23 | +19.01 | REJECTED (Red-team: Sharpe > 3, only 8 trades) |
| MOMENTUM_SCALPER | 24 | 63% | +187% | 3.89 | +8.87 | REJECTED (Red-team: Sharpe > 3) |
| OPENING_RANGE_BREAKOUT | 33 | 67% | +391% | 5.24 | +8.75 | REJECTED (Red-team: Sharpe > 5) |
| VRP_HARVEST | 9 | 22% | -119% | -0.91 | -8.92 | REJECTED (MC) |

---

## Edge Hypothesis Analysis

### 1. Volatility Risk Premium (VRP) — VRP_HARVEST

**Hypothesis:** Implied volatility systematically overestimates realized volatility by 2-4% annualized. Selling premium when IV is high (IV Rank > 70) and buying back when IV normalizes captures this premium.

**Theoretical basis:**
- Documented in academic literature (Carr & Wu 2009, Bollerslev et al. 2009)
- VRP is positive ~70% of trading days in equity indices
- Edge source: risk premium compensation for bearing volatility risk

**Why it failed on synthetic data:**
- Synthetic GBM data uses constant σ (e.g., 13% for NIFTY)
- Realized vol on synthetic data averages 27.2% (inflated by jump noise)
- This creates RV > IV — the OPPOSITE of real-world VRP
- The strategy correctly identifies that there's no VRP edge on this data

**What's needed to validate:**
- Real Zerodha historical data with actual IV from option chain
- IV should be computed from real option prices (not proxied from RV)
- Test on 2+ years of data including multiple volatility regimes

**Verdict:** Sound hypothesis, untestable on synthetic data. Priority: HIGH for real-data validation.

---

### 2. Theta Decay Harvesting — STRADDLE_SELL, STRANGLE_SELL, IRON_CONDOR

**Hypothesis:** Short option positions benefit from time decay (theta). Sell premium, hold to expiry or until theta captures X% of premium.

**Why it failed:**
- Entry condition (ATR < average) doesn't predict range-bound markets
- Premium model shows that 2% spot move causes 50%+ premium expansion on short-dated options
- SL of 25% on premium is too tight for the actual volatility of premium
- The "edge" (theta) is smaller than the "risk" (gamma) on synthetic data

**What's needed:**
- Regime filter: only enter when ADX < 20 (confirmed ranging) + IV Rank > 50
- Wider SL: 2x ATR instead of 25% of premium
- Shorter hold time: exit after 2 bars (capture theta, limit gamma exposure)
- Real IV data (synthetic data has constant vol, no IV crush dynamics)

**Verdict:** Marginal hypothesis. Theta edge is real but small. Needs regime filter + real IV data. Priority: MEDIUM.

---

### 3. Volatility Breakout — STRADDLE_BUY, MOMENTUM_SCALPER, OPENING_RANGE_BREAKOUT

**Hypothesis:** Volatility expansion predicts continued movement. Buy options when range expands, profit from continuation.

**Why it "works" on synthetic data (but is curve-fit):**
- Synthetic GBM has mean-reverting volatility (by construction)
- Entry on vol expansion → catches the predictable reversion
- This is NOT a real edge — real markets have vol clustering (persistence), not mean reversion
- Sharpe > 3.0 is the red flag: real edge strategies rarely exceed Sharpe 1.5-2.0

**What's needed:**
- Test on real data where vol clustering exists
- Add regime filter: only trade breakout in TRENDING regime (ADX > 25)
- Remove TP at 100% of premium (hindsight bias — you can't know the optimal exit in advance)
- Use trailing stop instead of fixed TP

**Verdict:** Likely curve-fit on synthetic data. Needs real data validation. Priority: MEDIUM.

---

### 4. Calendar Spread

**Hypothesis:** Near-week options decay faster than far-week options at same strike. Sell near, buy far, profit from differential theta.

**Why it "works" but is suspicious:**
- 88% win rate with only 8 trades → statistically insignificant
- Sharpe 3.23 → red-team threshold
- MC p5 Sharpe of 19 → unrealistically high
- The "edge" may be real (front-month theta acceleration is mathematically guaranteed) but the magnitude is wrong

**What's needed:**
- More trades (need 30+ for significance)
- Real expiry calendar (synthetic data doesn't model weekly vs monthly expiry)
- Real IV term structure (synthetic data has flat term structure)

**Verdict:** Sound hypothesis, untestable on synthetic data. Priority: HIGH for real-data validation.

---

## Root Cause: Synthetic Data Limitations

The fundamental issue is that synthetic GBM data cannot properly validate options strategies because:

1. **Constant volatility**: Real IV varies day-to-day; synthetic σ is fixed per instrument
2. **No IV term structure**: Real near-week IV differs from far-week; synthetic has flat structure
3. **No IV skew/smile**: Real OTM puts have higher IV than ATM; synthetic is flat
4. **Mean-reverting vol**: Synthetic GBM with jumps has mean-reverting vol; real markets have vol clustering
5. **No event risk**: Real markets have earnings, RBI, budget events that spike IV; synthetic doesn't
6. **No OI dynamics**: Real option chains have OI buildup/unwinding; synthetic doesn't model this

**Recommendation:** Connect real Zerodha historical data (2+ years) to properly validate strategies. The current synthetic data is useful for testing the ENGINE (no bugs, correct math) but NOT for validating EDGE.

---

## Next Research Directions

### Priority 1: Real Data Integration
- Connect Zerodha Kite historical API for NIFTY/BANKNIFTY
- Fetch 2 years of daily option chain data with IV
- Store in SQLite for offline backtesting
- Re-run all 10 strategies on real data

### Priority 2: Improved Strategy Design
- Add regime filter to all strategies (only trade in compatible regime)
- Add IV Rank condition to all premium-selling strategies
- Remove fixed TP (use trailing stop or time-based exit)
- Add OI analysis for confirmation

### Priority 3: Walk-Forward Optimization
- Implement proper walk-forward with parameter optimization
- Optimize SL/TP on train window, test on out-of-sample window
- Report OOS degradation explicitly

### Priority 4: Multi-Asset Portfolio
- Test strategy correlation across NIFTY/BANKNIFTY/GOLD/NATGAS
- Build portfolio-level allocation (not just single-strategy backtest)
- Monitor net delta/theta at portfolio level

---

## Conclusion

The JARVIS validation pipeline is working correctly. It rejects all 10 strategies because:
- 6 genuinely lose money on synthetic data
- 4 look too good to be true (curve-fit suspicion)

The system refuses to promote any strategy to paper trading without:
1. Passing all red-team checks (no curve-fit indicators)
2. Monte Carlo 5th-percentile Sharpe > 0 (robust to trade order randomization)
3. Human approval (final gate before live capital)

**This is the disciplined behavior required for long-term survival in markets.**

The next critical step is connecting real market data — the synthetic data has served its purpose (engine validation) but cannot validate strategy edge.
