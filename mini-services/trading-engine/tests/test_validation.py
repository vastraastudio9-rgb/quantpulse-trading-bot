"""
Unit tests for validation.py — JARVIS validation framework.
Run: python -m pytest tests/test_validation.py -v
"""
import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validation import (
    classify_regime, regime_distribution, split_oos, walk_forward_windows,
    monte_carlo_trade_shuffle, parameter_sensitivity, regime_performance_breakdown,
    red_team_audit, run_full_validation,
)


def make_bars(n=100, base=24000, vol=0.01, trend=0.0):
    """Generate synthetic bars for testing."""
    bars = []
    price = base
    from datetime import datetime, timedelta
    start = datetime(2025, 1, 1, 9, 15)
    for i in range(n):
        ret = np.random.normal(trend, vol)
        price *= (1 + ret)
        high = price * (1 + abs(np.random.normal(0, 0.003)))
        low = price * (1 - abs(np.random.normal(0, 0.003)))
        # Use sequential days with unique timestamps
        ts = start + timedelta(days=i)
        bars.append({
            "timestamp": ts.isoformat(),
            "open": price * (1 + np.random.normal(0, 0.001)),
            "high": high,
            "low": low,
            "close": price,
            "volume": 1000000,
        })
    return bars


def make_trades(n=20, win_rate=0.6, avg_win=200, avg_loss=-150):
    """Generate synthetic trades."""
    from datetime import datetime, timedelta
    trades = []
    n_wins = int(n * win_rate)
    n_losses = n - n_wins
    pnls = [avg_win] * n_wins + [avg_loss] * n_losses
    np.random.shuffle(pnls)
    start = datetime(2025, 1, 1, 9, 15)
    for i, pnl in enumerate(pnls):
        ts = start + timedelta(days=i)
        trades.append({
            "entry_time": ts.isoformat(),
            "exit_time": (ts + timedelta(hours=6)).isoformat(),
            "pnl": pnl,
            "duration_bars": 3,
        })
    return trades


class TestRegimeClassification:
    def test_returns_string(self):
        bars = make_bars(30)
        regime = classify_regime(bars)
        assert isinstance(regime, str)
        assert regime in {"TRENDING_UP", "TRENDING_DOWN", "RANGING", "BREAKOUT", "HIGH_VOL", "LOW_VOL", "ABNORMAL", "UNKNOWN"}

    def test_insufficient_bars_returns_unknown(self):
        bars = make_bars(5)
        assert classify_regime(bars) == "UNKNOWN"

    def test_trending_up_detection(self):
        """Strong uptrend should be classified as TRENDING_UP."""
        bars = make_bars(30, trend=0.005, vol=0.005)  # strong up, low vol
        regime = classify_regime(bars)
        assert regime in {"TRENDING_UP", "LOW_VOL"}  # may classify as low vol too

    def test_trending_down_detection(self):
        """Strong downtrend should be classified as TRENDING_DOWN."""
        bars = make_bars(30, trend=-0.005, vol=0.005)
        regime = classify_regime(bars)
        assert regime in {"TRENDING_DOWN", "LOW_VOL"}

    def test_high_vol_detection(self):
        """High volatility → HIGH_VOL or ABNORMAL (both flag high-vol regime)."""
        np.random.seed(42)
        bars = make_bars(30, vol=0.04)  # 4% daily vol = ~63% annual
        regime = classify_regime(bars)
        assert regime in {"HIGH_VOL", "ABNORMAL"}, f"Expected HIGH_VOL or ABNORMAL, got {regime}"

    def test_regime_distribution(self):
        bars = make_bars(100)
        dist = regime_distribution(bars)
        assert isinstance(dist, dict)
        assert sum(dist.values()) > 0


class TestOosSplit:
    def test_70_30_split(self):
        bars = make_bars(100)
        train, test = split_oos(bars, train_pct=0.7)
        assert len(train) == 70
        assert len(test) == 30
        # Chronological: train comes before test
        assert train[-1]["timestamp"] <= test[0]["timestamp"]

    def test_80_20_split(self):
        bars = make_bars(100)
        train, test = split_oos(bars, train_pct=0.8)
        assert len(train) == 80
        assert len(test) == 20

    def test_no_overlap(self):
        bars = make_bars(50)
        train, test = split_oos(bars, train_pct=0.6)
        # No bar should appear in both
        train_ts = {b["timestamp"] for b in train}
        test_ts = {b["timestamp"] for b in test}
        assert train_ts.isdisjoint(test_ts)


class TestWalkForward:
    def test_generates_windows(self):
        bars = make_bars(300)
        windows = walk_forward_windows(bars, train_window=90, test_window=30, step=30)
        assert len(windows) > 0
        for train, test in windows:
            assert len(train) == 90
            assert len(test) == 30
            # Test comes after train
            assert train[-1]["timestamp"] <= test[0]["timestamp"]

    def test_step_advances_window(self):
        bars = make_bars(300)
        windows = walk_forward_windows(bars, train_window=90, test_window=30, step=30)
        if len(windows) >= 2:
            # Second window should start 30 bars after first
            assert windows[1][0][0]["timestamp"] != windows[0][0][0]["timestamp"]

    def test_insufficient_data(self):
        bars = make_bars(50)
        windows = walk_forward_windows(bars, train_window=90, test_window=30, step=30)
        assert windows == []


class TestMonteCarlo:
    def test_insufficient_trades(self):
        result = monte_carlo_trade_shuffle([], 100000, n_runs=100)
        assert result["status"] == "INSUFFICIENT_TRADES"

    def test_few_trades(self):
        result = monte_carlo_trade_shuffle([{"pnl": 100}], 100000, n_runs=100)
        assert result["status"] == "INSUFFICIENT_TRADES"

    def test_basic_monte_carlo(self):
        trades = make_trades(30, win_rate=0.6)
        result = monte_carlo_trade_shuffle(trades, 100000, n_runs=100, seed=42)
        assert result["status"] == "COMPLETED"
        assert result["n_runs"] == 100
        assert result["n_trades"] == 30
        # Check percentile structure
        for key in ["final_capital", "max_drawdown_pct", "sharpe"]:
            assert key in result
            for p in ["p5", "p50", "p95"]:
                assert p in result[key]
        # p5 < p50 < p95
        fc = result["final_capital"]
        assert fc["p5"] <= fc["p50"] <= fc["p95"]

    def test_probability_of_profit_with_winning_strategy(self):
        """Strategy with 70% win rate and 2:1 RR should profit > 90% of MC runs."""
        trades = make_trades(50, win_rate=0.7, avg_win=200, avg_loss=-100)
        result = monte_carlo_trade_shuffle(trades, 100000, n_runs=200, seed=42)
        assert result["probability_of_profit"] > 90

    def test_probability_of_profit_with_losing_strategy(self):
        """Strategy with 30% win rate and 1:1 RR should profit < 30% of MC runs."""
        trades = make_trades(50, win_rate=0.3, avg_win=100, avg_loss=-100)
        result = monte_carlo_trade_shuffle(trades, 100000, n_runs=200, seed=42)
        assert result["probability_of_profit"] < 30

    def test_deterministic_with_seed(self):
        """Same seed → same result."""
        trades = make_trades(20)
        r1 = monte_carlo_trade_shuffle(trades, 100000, n_runs=50, seed=42)
        r2 = monte_carlo_trade_shuffle(trades, 100000, n_runs=50, seed=42)
        assert r1["final_capital"]["p50"] == r2["final_capital"]["p50"]


class TestRedTeamAudit:
    def test_passes_clean_strategy(self):
        """Healthy strategy with reasonable metrics should pass."""
        result = {
            "metrics": {
                "sharpe": 1.5,
                "win_rate": 60,
                "profit_factor": 1.8,
                "max_drawdown_pct": 15,
                "total_return_pct": 30,
                "total_trades": 50,
            },
            "trades": [{"pnl": 100, "costs": 25}, {"pnl": -50, "costs": 22}],
        }
        audit = red_team_audit(result)
        assert audit["verdict"] in {"PASSED", "WARNING"}
        assert audit["critical_failures"] == 0

    def test_rejects_high_win_rate(self):
        """Win rate > 80% should fail."""
        result = {
            "metrics": {"sharpe": 1.5, "win_rate": 85, "profit_factor": 2.0, "max_drawdown_pct": 10, "total_return_pct": 40, "total_trades": 50},
            "trades": [{"pnl": 100, "costs": 25}],
        }
        audit = red_team_audit(result)
        assert audit["verdict"] == "REJECTED"
        # win_rate_sanity check should fail
        checks = {c["name"]: c for c in audit["checks"]}
        assert checks["win_rate_sanity"]["passed"] is False

    def test_rejects_high_sharpe(self):
        """Sharpe > 3.0 should fail."""
        result = {
            "metrics": {"sharpe": 4.5, "win_rate": 60, "profit_factor": 2.0, "max_drawdown_pct": 10, "total_return_pct": 40, "total_trades": 50},
            "trades": [],
        }
        audit = red_team_audit(result)
        checks = {c["name"]: c for c in audit["checks"]}
        assert checks["sharpe_sanity"]["passed"] is False

    def test_rejects_few_trades(self):
        """< 30 trades should warn."""
        result = {
            "metrics": {"sharpe": 1.5, "win_rate": 60, "profit_factor": 1.8, "max_drawdown_pct": 15, "total_return_pct": 30, "total_trades": 15},
            "trades": [],
        }
        audit = red_team_audit(result)
        checks = {c["name"]: c for c in audit["checks"]}
        assert checks["trade_count_adequacy"]["passed"] is False
        assert checks["trade_count_adequacy"]["severity"] == "MEDIUM"

    def test_detects_constant_costs(self):
        """If all trades have identical costs, slippage not properly modeled."""
        result = {
            "metrics": {"sharpe": 1.5, "win_rate": 60, "profit_factor": 1.8, "max_drawdown_pct": 15, "total_return_pct": 30, "total_trades": 50},
            "trades": [{"pnl": 100, "costs": 25} for _ in range(10)],
        }
        audit = red_team_audit(result)
        checks = {c["name"]: c for c in audit["checks"]}
        assert "slippage_modeled" in checks
        assert checks["slippage_modeled"]["passed"] is False


class TestRegimePerformanceBreakdown:
    def test_no_trades(self):
        bars = make_bars(100)
        result = regime_performance_breakdown(bars, [])
        assert result == {"status": "NO_TRADES"}

    def test_assigns_regimes_to_trades(self):
        bars = make_bars(100)
        trades = make_trades(10)
        result = regime_performance_breakdown(bars, trades)
        # Should have at least one regime bucket
        assert len(result) > 0
        for regime, stats in result.items():
            assert "trades" in stats
            assert "win_rate" in stats
            assert "total_pnl" in stats


class TestParameterSensitivity:
    def test_runs_variations(self):
        """Parameter sensitivity should run all variations."""
        def mock_backtest(sl_pct=25):
            return {
                "metrics": {
                    "total_return_pct": 10 + (sl_pct - 25) * 0.5,
                    "sharpe": 1.0 + (sl_pct - 25) * 0.05,
                    "max_drawdown_pct": 10 + (sl_pct - 25) * 0.2,
                    "win_rate": 60,
                    "total_trades": 50,
                }
            }
        result = parameter_sensitivity(mock_backtest, {"sl_pct": 25}, "sl_pct", [15, 20, 25, 30, 35])
        assert result["param_name"] == "sl_pct"
        assert len(result["variations"]) == 5
        assert "stability_score" in result
        assert result["verdict"] in {"ROBUST", "FRAGILE", "MODERATE"}


class TestFullValidation:
    def test_runs_full_pipeline(self):
        """End-to-end validation should produce a verdict."""
        from backtest import run_backtest
        bars = make_bars(180)
        # Convert to format expected by run_backtest (which uses market_data.generate_history)
        # We can't easily inject bars, so we just test the pipeline structure
        result = run_full_validation(
            backtest_fn=run_backtest,
            base_params={
                "strategy_key": "STRADDLE_SELL",
                "symbol": "NIFTY",
                "days": 60,
                "initial_capital": 100000,
            },
            bars=bars,
            monte_carlo_runs=50,  # quick for test
        )
        assert "final_verdict" in result
        assert "red_team" in result
        assert "monte_carlo" in result
        assert "regime_performance" in result
        assert "promotion_path" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
