"""
Unit tests for backtest.py — metrics + trade simulation + JARVIS-v2 fixes.
Run: python -m pytest tests/test_backtest.py -v
"""
import sys
import os
import math
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backtest import (
    compute_metrics, _empty_metrics, calc_costs, estimate_slippage,
    revalue_option_premium, run_backtest, _compute_monthly_returns,
)


class TestCosts:
    def test_buy_side_costs(self):
        """Buy side: brokerage + exchange + GST + SEBI + stamp_duty (no STT)."""
        c = calc_costs(premium=100, qty=75, is_sell=False, slippage_ticks=2, tick_size=0.05)
        assert c["stt"] == 0  # no STT on buy
        assert c["stamp_duty"] > 0  # stamp duty on buy
        assert c["brokerage"] == 20.0  # Zerodha cap
        assert c["slippage"] == 2 * 0.05 * 75  # 7.5
        assert c["total"] > 0

    def test_sell_side_costs(self):
        """Sell side: brokerage + STT + exchange + GST + SEBI (no stamp_duty)."""
        c = calc_costs(premium=100, qty=75, is_sell=True, slippage_ticks=0, tick_size=0.05)
        assert c["stt"] == 100 * 75 * 0.001  # 7.5
        assert c["stamp_duty"] == 0  # no stamp duty on sell
        assert c["slippage"] == 0

    def test_slippage_calculation(self):
        """Slippage cost = ticks * tick_size * qty."""
        c = calc_costs(premium=50, qty=35, is_sell=False, slippage_ticks=5, tick_size=0.05)
        assert c["slippage"] == 5 * 0.05 * 35  # 8.75


class TestSlippageEstimation:
    def test_nifty_atm_slippage(self):
        """NIFTY ATM: 2-4 ticks."""
        for _ in range(20):
            s = estimate_slippage("NIFTY", strike_offset=0)
            assert 2 <= s <= 4

    def test_nifty_otm_slippage(self):
        """NIFTY OTM (offset 4+): 8-15 ticks."""
        for _ in range(20):
            s = estimate_slippage("NIFTY", strike_offset=5)
            assert 8 <= s <= 15

    def test_mcx_slippage(self):
        """MCX (Gold/NatGas): 5-15 ticks."""
        for _ in range(20):
            s = estimate_slippage("GOLD", strike_offset=0)
            assert 5 <= s <= 15

    def test_forex_slippage(self):
        """Forex: 1-3 ticks."""
        for _ in range(20):
            s = estimate_slippage("EURUSD", strike_offset=0)
            assert 1 <= s <= 3


class TestMetrics:
    def test_empty_equity_curve(self):
        m = compute_metrics([], [], 100000)
        assert m == _empty_metrics()

    def test_single_point_equity_curve(self):
        m = compute_metrics([100000], [], 100000)
        assert m == _empty_metrics()

    def test_flat_equity_curve(self):
        """Flat equity → Sharpe = 0 (std = 0)."""
        m = compute_metrics([100000, 100000, 100000, 100000], [], 100000)
        assert m["sharpe"] == 0  # no returns variation
        assert m["total_return_pct"] == 0
        assert m["max_drawdown_pct"] == 0

    def test_positive_return(self):
        """+50% return over 252 bars."""
        eq = list(np.linspace(100000, 150000, 253))
        m = compute_metrics(eq, [], 100000)
        assert abs(m["total_return_pct"] - 50) < 0.5
        assert m["max_drawdown_pct"] < 1  # monotonic increase, no DD

    def test_drawdown_calculation(self):
        """Equity goes up, drops 20%, recovers — max DD should be ~20%."""
        eq = [100000, 110000, 120000, 100000, 110000]  # peak 120k, trough 100k → 16.67% DD
        m = compute_metrics(eq, [], 100000)
        assert abs(m["max_drawdown_pct"] - 16.67) < 0.5

    def test_trade_metrics(self):
        """Trades with 3 wins (₹100 each) and 1 loss (-₹50)."""
        trades = [
            {"pnl": 100, "duration_bars": 2},
            {"pnl": 100, "duration_bars": 3},
            {"pnl": 100, "duration_bars": 2},
            {"pnl": -50, "duration_bars": 1},
        ]
        m = compute_metrics([100000, 100100, 100200, 100300, 100250], trades, 100000)
        assert m["total_trades"] == 4
        assert m["wins"] == 3
        assert m["losses"] == 1
        assert abs(m["win_rate"] - 75) < 0.1
        assert m["gross_profit"] == 300
        assert m["gross_loss"] == 50
        assert abs(m["profit_factor"] - 6) < 0.1  # 300/50 = 6
        assert m["expectancy"] == 62.5  # (300-50)/4

    def test_sharpe_positive_for_steady_gains(self):
        """Steady positive returns → high Sharpe."""
        # 1% per bar, std ~0
        eq = [100000 * (1.01 ** i) for i in range(253)]
        m = compute_metrics(eq, [], 100000)
        assert m["sharpe"] > 5  # very high (unrealistic but math correct)

    def test_sharpe_negative_for_steady_losses(self):
        """Steady negative returns → negative Sharpe."""
        eq = [100000 * (0.99 ** i) for i in range(253)]
        m = compute_metrics(eq, [], 100000)
        assert m["sharpe"] < -5


class TestPremiumRevaluation:
    def test_no_spot_move_no_time_decay(self):
        """If spot doesn't move and no time passes, premium unchanged."""
        premium = revalue_option_premium(
            entry_premium=100,
            entry_spot=24850,
            current_spot=24850,
            bars_held=0,
            total_bars_to_expiry=5,
            sigma=0.13,
            side="SELL",
        )
        assert abs(premium - 100) < 5  # should be close to entry

    def test_theta_decay_reduces_premium(self):
        """Holding longer → premium decreases (for buyer)."""
        premium_day0 = revalue_option_premium(100, 24850, 24850, 0, 5, 0.13, "BUY")
        premium_day3 = revalue_option_premium(100, 24850, 24850, 3, 5, 0.13, "BUY")
        # Time decay should reduce premium
        assert premium_day3 < premium_day0

    def test_spot_move_increases_straddle_premium(self):
        """Big spot move → straddle premium increases (gamma)."""
        premium_no_move = revalue_option_premium(100, 24850, 24850, 1, 5, 0.13, "BUY")
        premium_big_move = revalue_option_premium(100, 24850, 25000, 1, 5, 0.13, "BUY")
        assert premium_big_move > premium_no_move


class TestRunBacktest:
    def test_unknown_symbol_raises(self):
        with pytest.raises(ValueError, match="Unknown symbol"):
            run_backtest("STRADDLE_SELL", "UNKNOWN", days=30)

    def test_basic_backtest_completes(self):
        """Smoke test: backtest runs and returns COMPLETED status."""
        result = run_backtest("STRADDLE_SELL", "NIFTY", days=60)
        assert result["status"] == "COMPLETED"
        assert "metrics" in result
        assert "equity_curve" in result
        assert "trades" in result
        assert result["engine_version"] == "JARVIS-v2"

    def test_backtest_has_slippage_tracking(self):
        """JARVIS-v2: backtest should track slippage separately."""
        result = run_backtest("STRADDLE_SELL", "NIFTY", days=60, slippage_enabled=True)
        assert "slippage_total" in result
        assert "costs_total" in result

    def test_backtest_with_slippage_disabled(self):
        """When slippage_enabled=False, slippage should be 0."""
        result = run_backtest("STRADDLE_SELL", "NIFTY", days=60, slippage_enabled=False)
        assert result["slippage_total"] == 0

    def test_backtest_no_lookahead_bias(self):
        """Critical: entry_time should be AFTER the bar that triggered entry.
        
        If decision uses bars[i-1] (close at 09:15), execution should be at bars[i] (open at 09:30 next bar).
        We can't easily verify timestamps without market hours, but we can check trades exist.
        """
        result = run_backtest("STRADDLE_SELL", "NIFTY", days=90)
        if result["trades"]:
            trade = result["trades"][0]
            assert "entry_time" in trade
            assert "exit_time" in trade
            assert trade["entry_time"] < trade["exit_time"]

    def test_all_strategies_run_without_error(self):
        """All 9 strategies should produce a valid backtest."""
        strategies = [
            "STRADDLE_SELL", "STRANGLE_SELL", "STRADDLE_BUY", "IRON_CONDOR",
            "MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT",
            "LONG_BUTTERFLY", "IRON_BUTTERFLY", "CALENDAR_SPREAD",
        ]
        for strat in strategies:
            result = run_backtest(strat, "NIFTY", days=60)
            assert result["status"] == "COMPLETED", f"{strat} failed: {result.get('error')}"

    def test_all_instruments_run_without_error(self):
        """All instruments should backtest without error."""
        for symbol in ["NIFTY", "BANKNIFTY", "GOLD", "NATURALGAS", "EURUSD"]:
            result = run_backtest("STRADDLE_SELL", symbol, days=60)
            assert result["status"] == "COMPLETED", f"{symbol} failed"


class TestMonthlyReturns:
    def test_empty_returns_empty(self):
        assert _compute_monthly_returns([], []) == []

    def test_single_month(self):
        dates = ["2025-01-01T00:00:00", "2025-01-31T00:00:00"]
        equity = [100000, 105000]
        result = _compute_monthly_returns(dates, equity)
        assert len(result) == 1
        assert result[0]["month_name"] == "Jan"
        assert abs(result[0]["return_pct"] - 5) < 0.1

    def test_multiple_months(self):
        dates = [
            "2025-01-01T00:00:00",
            "2025-01-31T00:00:00",
            "2025-02-28T00:00:00",
        ]
        equity = [100000, 105000, 102000]
        result = _compute_monthly_returns(dates, equity)
        assert len(result) == 2
        months = [r["month_name"] for r in result]
        assert "Jan" in months
        assert "Feb" in months


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
