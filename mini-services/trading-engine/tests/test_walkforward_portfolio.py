"""
Unit tests for walk-forward optimization + portfolio backtest.
Run: python -m pytest tests/test_walkforward_portfolio.py -v
"""
import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validation import walk_forward_optimize, portfolio_backtest, walk_forward_windows
from market_data import generate_history


def make_bars(n=100, base=24000, vol=0.02):
    """Generate synthetic bars."""
    from datetime import datetime, timedelta
    bars = []
    price = base
    start = datetime(2025, 1, 1, 9, 15)
    for i in range(n):
        ret = np.random.normal(0, vol)
        price *= (1 + ret)
        ts = start + timedelta(days=i)
        bars.append({
            "timestamp": ts.isoformat(),
            "open": price,
            "high": price * 1.01,
            "low": price * 0.99,
            "close": price,
            "volume": 1000000,
        })
    return bars


class TestWalkForwardOptimize:
    def test_returns_dict_with_required_fields(self):
        from backtest import run_backtest
        bars = make_bars(180)
        base_params = {"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "days": 180}
        result = walk_forward_optimize(
            backtest_fn=run_backtest,
            base_params=base_params,
            bars=bars,
            param_name="sl_pct",
            param_values=[20, 25, 30],
            train_window=60,
            test_window=20,
            step=20,
        )
        assert "param_name" in result
        assert "param_values_tested" in result
        assert "n_windows" in result
        assert "windows" in result
        assert "aggregate" in result

    def test_aggregate_has_verdict(self):
        from backtest import run_backtest
        bars = make_bars(180)
        result = walk_forward_optimize(
            backtest_fn=run_backtest,
            base_params={"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "days": 180},
            bars=bars,
            param_name="sl_pct",
            param_values=[20, 25, 30],
            train_window=60,
            test_window=20,
            step=20,
        )
        assert result["aggregate"]["verdict"] in ("ROBUST", "OVERFIT", "MODERATE")

    def test_overfit_detection(self):
        """Walk-forward should flag overfit windows via degradation metric."""
        from backtest import run_backtest
        bars = make_bars(180)
        result = walk_forward_optimize(
            backtest_fn=run_backtest,
            base_params={"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "days": 180},
            bars=bars,
            param_name="sl_pct",
            param_values=[15, 20, 25, 30, 35],
            train_window=60,
            test_window=20,
            step=20,
        )
        # Each window should have degradation_pct and overfit_flag
        for w in result["windows"]:
            if "degradation_pct" in w:
                assert "overfit_flag" in w
                assert isinstance(w["overfit_flag"], bool)

    def test_insufficient_data(self):
        """With too few bars, should return empty windows."""
        from backtest import run_backtest
        bars = make_bars(50)  # too short for 90+30 window
        result = walk_forward_optimize(
            backtest_fn=run_backtest,
            base_params={"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "days": 50},
            bars=bars,
            param_name="sl_pct",
            param_values=[20, 25, 30],
            train_window=90,
            test_window=30,
            step=30,
        )
        assert result["n_windows"] == 0


class TestPortfolioBacktest:
    def test_single_strategy(self):
        from backtest import run_backtest
        result = portfolio_backtest(
            backtest_fn=run_backtest,
            strategies=[{"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "allocation_pct": 100}],
            days=90,
            initial_capital=100000,
        )
        assert result["n_strategies"] == 1
        assert "portfolio_metrics" in result
        assert "per_strategy" in result
        assert len(result["per_strategy"]) == 1

    def test_multi_strategy(self):
        from backtest import run_backtest
        result = portfolio_backtest(
            backtest_fn=run_backtest,
            strategies=[
                {"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "allocation_pct": 50},
                {"strategy_key": "MOMENTUM_SCALPER", "symbol": "GOLD", "allocation_pct": 50},
            ],
            days=90,
            initial_capital=100000,
        )
        assert result["n_strategies"] == 2
        assert len(result["per_strategy"]) == 2
        # Should have correlation matrix
        assert "correlation_matrix" in result
        # Should have diversification ratio
        assert "diversification_ratio" in result["portfolio_metrics"]

    def test_correlation_matrix_structure(self):
        from backtest import run_backtest
        result = portfolio_backtest(
            backtest_fn=run_backtest,
            strategies=[
                {"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "allocation_pct": 33},
                {"strategy_key": "MOMENTUM_SCALPER", "symbol": "GOLD", "allocation_pct": 33},
                {"strategy_key": "VRP_HARVEST", "symbol": "BANKNIFTY", "allocation_pct": 34},
            ],
            days=90,
        )
        cm = result["correlation_matrix"]
        # Should have 3 keys
        assert len(cm) == 3
        # Each key should have correlation to all 3 (including itself = 1.0)
        for k, row in cm.items():
            assert len(row) == 3
            assert row[k] == 1.0  # self-correlation = 1

    def test_diversification_verdict(self):
        from backtest import run_backtest
        result = portfolio_backtest(
            backtest_fn=run_backtest,
            strategies=[
                {"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "allocation_pct": 50},
                {"strategy_key": "MOMENTUM_SCALPER", "symbol": "GOLD", "allocation_pct": 50},
            ],
            days=90,
        )
        assert result["verdict"] in ("WELL_DIVERSIFIED", "POORLY_DIVERSIFIED", "MODERATE")

    def test_allocation_as_percentage(self):
        """allocation_pct=40 should mean 40%, not 4000%."""
        from backtest import run_backtest
        result = portfolio_backtest(
            backtest_fn=run_backtest,
            strategies=[
                {"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "allocation_pct": 40},
                {"strategy_key": "MOMENTUM_SCALPER", "symbol": "GOLD", "allocation_pct": 60},
            ],
            days=60,
        )
        for s in result["per_strategy"]:
            assert s["allocation_pct"] <= 100  # should be percentage, not > 100

    def test_weighted_return_calculation(self):
        """Weighted return should be sum of (return * allocation)."""
        from backtest import run_backtest
        result = portfolio_backtest(
            backtest_fn=run_backtest,
            strategies=[
                {"strategy_key": "STRADDLE_SELL", "symbol": "NIFTY", "allocation_pct": 50},
                {"strategy_key": "MOMENTUM_SCALPER", "symbol": "GOLD", "allocation_pct": 50},
            ],
            days=90,
        )
        # Verify weighted return = sum of (return * allocation/100)
        expected = sum(
            s.get("metrics", {}).get("total_return_pct", 0) * s["allocation_pct"] / 100
            for s in result["per_strategy"]
        )
        assert abs(result["portfolio_metrics"]["weighted_return_pct"] - round(expected, 2)) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
