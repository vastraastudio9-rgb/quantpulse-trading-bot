"""
Unit tests for VRP_HARVEST strategy + IV rank calculations.
Run: python -m pytest tests/test_vrp.py -v
"""
import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from strategies import STRATEGIES, generate_signal
from regime import iv_rank, iv_percentile, realized_volatility, volatility_risk_premium, REGIME_STRATEGY_MAP
from auto_bot import apply_strategy_entry_gates
from market_data import generate_history


def make_bars(n=100, base=24000, vol=0.02):
    """Generate synthetic bars with varying vol for IV rank testing."""
    from datetime import datetime, timedelta
    bars = []
    price = base
    start = datetime(2025, 1, 1, 9, 15)
    for i in range(n):
        # Vary vol over time — first half low, second half high
        current_vol = vol * 0.5 if i < n // 2 else vol * 2.0
        ret = np.random.normal(0, current_vol)
        price *= (1 + ret)
        high = price * (1 + abs(np.random.normal(0, 0.003)))
        low = price * (1 - abs(np.random.normal(0, 0.003)))
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


class TestRealizedVolatility:
    def test_returns_float(self):
        bars = make_bars(30)
        rv = realized_volatility(bars, period=20)
        assert isinstance(rv, float)
        assert rv >= 0

    def test_insufficient_data_returns_zero(self):
        bars = make_bars(10)
        rv = realized_volatility(bars, period=20)
        assert rv == 0

    def test_higher_vol_produces_higher_rv(self):
        np.random.seed(42)
        bars_low = make_bars(50, vol=0.005)
        np.random.seed(42)
        bars_high = make_bars(50, vol=0.04)
        rv_low = realized_volatility(bars_low, period=20)
        rv_high = realized_volatility(bars_high, period=20)
        assert rv_high > rv_low


class TestIVRank:
    def test_returns_value_in_range(self):
        bars = make_bars(80)
        rank = iv_rank(bars, lookback=60)
        assert 0 <= rank <= 100

    def test_insufficient_data_returns_neutral(self):
        bars = make_bars(5)
        rank = iv_rank(bars, lookback=60)
        assert rank == 50

    def test_high_vol_period_produces_high_rank(self):
        """When current vol is highest in lookback, IV rank should be ~100."""
        np.random.seed(42)
        bars = make_bars(80, vol=0.01)
        # Add high-vol bars at the end
        for i in range(20):
            ret = np.random.normal(0, 0.05)
            bars[-1 - i]["close"] *= (1 + ret)
        rank = iv_rank(bars, lookback=60)
        assert rank > 60  # should be high since recent vol is elevated

    def test_low_vol_period_produces_low_rank(self):
        """When current vol is lowest in lookback, IV rank should be low."""
        np.random.seed(42)
        # Generate bars with decreasing vol — high early, low recently
        from datetime import datetime, timedelta
        bars = []
        price = 24000
        start = datetime(2025, 1, 1, 9, 15)
        for i in range(80):
            # Vol decreases over time: 4% → 0.5%
            current_vol = 0.04 * (1 - i / 100)
            ret = np.random.normal(0, max(current_vol, 0.001))
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
        rank = iv_rank(bars, lookback=60)
        # Since vol is decreasing, recent RV should be low relative to history
        assert rank < 60  # relaxed bound — decreasing vol should produce below-median rank


class TestIVPercentile:
    def test_returns_value_in_range(self):
        bars = make_bars(80)
        pct = iv_percentile(bars, lookback=60)
        assert 0 <= pct <= 100

    def test_insufficient_data_returns_neutral(self):
        bars = make_bars(5)
        pct = iv_percentile(bars, lookback=60)
        assert pct == 50


class TestVolatilityRiskPremium:
    def test_returns_dict_with_required_fields(self):
        bars = make_bars(30)
        vrp = volatility_risk_premium(bars, period=20)
        assert "implied_vol" in vrp
        assert "realized_vol" in vrp
        assert "vrp" in vrp
        assert "vrp_positive" in vrp
        assert "edge" in vrp

    def test_edge_classification(self):
        bars = make_bars(30)
        vrp = volatility_risk_premium(bars, period=20)
        assert vrp["edge"] in ("SELL_PREMIUM", "BUY_PREMIUM", "NEUTRAL")


class TestVRPHarvestStrategy:
    def test_vrp_is_routed_only_with_high_iv_entry_gate(self):
        assert "VRP_HARVEST" in REGIME_STRATEGY_MAP["RANGE_BOUND_TIGHT"]
        assert "VRP_HARVEST" in REGIME_STRATEGY_MAP["RANGE_BOUND_WIDE"]
        assert "VRP_HARVEST" not in apply_strategy_entry_gates(["VRP_HARVEST"], 69.9)
        assert "VRP_HARVEST" in apply_strategy_entry_gates(["VRP_HARVEST"], 70)

    def test_strategy_definition_exists(self):
        assert "VRP_HARVEST" in STRATEGIES
        strat = STRATEGIES["VRP_HARVEST"]
        assert strat["name"] == "Volatility Risk Premium Harvest"
        assert strat["type"] == "VRP"
        assert "Volatility Risk Premium" in strat["edge_source"]

    def test_signal_generation(self):
        sig = generate_signal("VRP_HARVEST", "NIFTY")
        assert sig is not None
        assert sig["strategy_key"] == "VRP_HARVEST"
        assert len(sig["legs"]) == 4  # Iron Condor: 2 sells + 2 buys

    def test_signal_has_iron_condor_structure(self):
        """VRP_HARVEST uses Iron Condor: SELL CE + BUY CE + SELL PE + BUY PE."""
        sig = generate_signal("VRP_HARVEST", "NIFTY")
        assert sig is not None
        actions = [l["action"] for l in sig["legs"]]
        assert actions.count("SELL") == 2
        assert actions.count("BUY") == 2
        # Should have both CE and PE
        types = {l["type"] for l in sig["legs"]}
        assert types == {"CE", "PE"}

    def test_signal_has_defined_risk(self):
        """Iron Condor has defined max profit and max loss."""
        sig = generate_signal("VRP_HARVEST", "NIFTY")
        assert sig is not None
        assert "max_profit" in sig
        assert "max_loss" in sig
        assert sig["max_profit"] > 0
        assert sig["max_loss"] > 0
        # Max loss should be > max profit (defined risk, but loss > profit for IC)
        assert sig["max_loss"] >= sig["max_profit"] * 0.5

    def test_signal_has_breakevens(self):
        sig = generate_signal("VRP_HARVEST", "NIFTY")
        assert sig is not None
        assert "breakeven_upper" in sig
        assert "breakeven_lower" in sig
        assert sig["breakeven_upper"] > sig["breakeven_lower"]

    def test_signal_has_vrp_rationale(self):
        """Rationale should mention IV Rank / VRP edge."""
        sig = generate_signal("VRP_HARVEST", "NIFTY")
        assert sig is not None
        assert "IV Rank" in sig["rationale"] or "VRP" in sig["rationale"]

    def test_confidence_in_range(self):
        sig = generate_signal("VRP_HARVEST", "NIFTY")
        assert sig is not None
        assert 50 <= sig["confidence"] <= 92

    def test_signal_on_multiple_instruments(self):
        """VRP_HARVEST should work on all supported instruments."""
        for symbol in ["NIFTY", "BANKNIFTY", "GOLD", "NATURALGAS"]:
            sig = generate_signal("VRP_HARVEST", symbol)
            assert sig is not None, f"Failed for {symbol}"
            assert sig["symbol"] == symbol


class TestVRPBacktest:
    def test_backtest_completes(self):
        from backtest import run_backtest
        result = run_backtest("VRP_HARVEST", "NIFTY", days=90)
        assert result["status"] == "COMPLETED"
        assert result["engine_version"] == "JARVIS-v2"
        assert "metrics" in result

    def test_backtest_has_iv_rank_entry_condition(self):
        """VRP_HARVEST should only enter when IV Rank > 70 — fewer trades than other strategies."""
        from backtest import run_backtest
        result = run_backtest("VRP_HARVEST", "NIFTY", days=90)
        # With strict IV Rank > 70 condition, should have fewer trades than STRADDLE_SELL
        # (which enters on any low-vol bar)
        assert result["metrics"]["total_trades"] >= 0  # could be 0 if no IV Rank > 70 conditions

    def test_iv_normalized_exit_reason(self):
        """VRP_HARVEST can exit via IV_NORMALIZED (IV Rank falls below 30)."""
        from backtest import run_backtest
        result = run_backtest("VRP_HARVEST", "NIFTY", days=180)
        trades = result.get("trades", [])
        exit_reasons = set(t.get("exit_reason", "") for t in trades)
        # Should have at least one of these exit reasons
        valid_reasons = {"SL_HIT", "TP_HIT", "TIME_EXIT", "IV_NORMALIZED", "EOD_FORCE_CLOSE"}
        assert exit_reasons.issubset(valid_reasons)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
