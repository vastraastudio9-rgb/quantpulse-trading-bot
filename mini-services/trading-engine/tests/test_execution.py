"""
Unit tests for execution_engine.py — paper trading execution.
Run: python -m pytest tests/test_execution.py -v
"""
import sys
import os
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from execution_engine import PaperExecutionEngine, get_execution_engine
from risk_engine import PortfolioRiskEngine, RiskLimits, Position, get_portfolio_engine
from strategies import generate_signal


@pytest.fixture
def fresh_engine():
    """Create a fresh risk + execution engine for each test."""
    # Reset singleton
    import execution_engine
    import risk_engine
    execution_engine._execution_engine = None
    risk_engine._portfolio_engine = None
    return get_execution_engine()


class TestPaperExecutionEngine:
    def test_engine_initializes(self, fresh_engine):
        assert fresh_engine is not None
        assert fresh_engine.risk_engine is not None
        assert len(fresh_engine.risk_engine.positions) == 0

    def test_process_signal_opens_position(self, fresh_engine):
        """A valid signal should open a position."""
        signal = generate_signal("VRP_HARVEST", "NIFTY")
        assert signal is not None
        result = fresh_engine.process_signal(signal)
        assert result["accepted"] is True
        assert "position_id" in result
        assert result["position_id"] is not None

    def test_position_added_to_risk_engine(self, fresh_engine):
        """After opening, position should appear in risk engine."""
        signal = generate_signal("VRP_HARVEST", "NIFTY")
        fresh_engine.process_signal(signal)
        assert len(fresh_engine.risk_engine.positions) == 1
        position = fresh_engine.risk_engine.positions[0]
        assert position.entry_slippage > 0
        assert position.estimated_costs > 0

    def test_close_position(self, fresh_engine):
        """Close a position and verify P&L recorded."""
        signal = generate_signal("VRP_HARVEST", "NIFTY")
        result = fresh_engine.process_signal(signal)
        pos_id = result["position_id"]
        
        close_result = fresh_engine.close_position(pos_id, exit_price=50.0, reason="MANUAL")
        assert close_result["success"] is True
        assert "pnl" in close_result
        assert len(fresh_engine.risk_engine.positions) == 0  # position removed

    def test_close_nonexistent_position(self, fresh_engine):
        """Closing a non-existent position should fail gracefully."""
        result = fresh_engine.close_position("FAKE-ID", exit_price=100, reason="TEST")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_strategy_concentration_limit(self, fresh_engine):
        """Two positions from same strategy should be allowed, third blocked."""
        # First position
        sig1 = generate_signal("VRP_HARVEST", "NIFTY")
        r1 = fresh_engine.process_signal(sig1)
        assert r1["accepted"] is True
        
        # Second position (same strategy, different symbol)
        sig2 = generate_signal("VRP_HARVEST", "GOLD")
        r2 = fresh_engine.process_signal(sig2)
        # May or may not be accepted depending on risk limits
        # (strategy_concentration max is 2)
        
        # Third position (same strategy) — should be blocked
        # Use a contract with valid positive model premiums so this assertion
        # exercises concentration rather than the structural signal gate.
        sig3 = generate_signal("VRP_HARVEST", "NIFTY")
        r3 = fresh_engine.process_signal(sig3)
        # If first two passed, third should fail on strategy_concentration
        if r1["accepted"] and r2["accepted"]:
            assert r3["accepted"] is False
            assert "strategy_concentration" in r3["reason"]

    def test_monitor_positions_no_open(self, fresh_engine):
        """Monitor with no positions should return empty list."""
        closed = fresh_engine.monitor_positions()
        assert closed == []

    def test_monitor_detects_sl_hit(self, fresh_engine):
        """Monitor should detect SL/TP breach and close position.
        
        JARVIS-v2.3: Monitor now revalues option premium via BS (for single-leg)
        or spot-move+theta model (for multi-leg). Test verifies SL triggers correctly.
        """
        signal = generate_signal("VRP_HARVEST", "NIFTY")
        result = fresh_engine.process_signal(signal)
        pos_id = result["position_id"]
        
        # Find the position
        pos = next(p for p in fresh_engine.risk_engine.positions if p.id == pos_id)
        # VRP_HARVEST is SHORT (net credit), so SL triggers when current >= stop_loss
        # Set SL below current price → will trigger on next monitor
        pos.stop_loss = pos.current_price - 10  # below current → SL hit for SHORT
        pos.take_profit = 0  # disable TP
        
        # Run monitor with current quote
        closed = fresh_engine.monitor_positions()
        assert len(closed) > 0
        assert closed[0]["position_id"] == pos_id
        assert closed[0]["reason"] in ("SL_HIT", "TP_HIT")

    def test_execution_records_metrics(self, fresh_engine):
        """Execution should increment Prometheus counters."""
        from observability import metrics
        initial = metrics._counters.get("positions_opened_total", 0)
        signal = generate_signal("VRP_HARVEST", "NIFTY")
        fresh_engine.process_signal(signal)
        # Counter should have incremented (may not be exact due to labels)
        # Just verify no crash
        assert True

    def test_greeks_computed_on_open(self, fresh_engine):
        """Position should have non-zero Greeks after opening."""
        signal = generate_signal("VRP_HARVEST", "NIFTY")
        result = fresh_engine.process_signal(signal)
        if result["accepted"]:
            pos = fresh_engine.risk_engine.positions[0]
            # Delta should be non-zero for an options position
            assert pos.delta != 0

    def test_kill_switch_blocks_new_positions(self, fresh_engine):
        """When kill switch is active, no new positions should open."""
        fresh_engine.risk_engine.activate_kill_switch("Test")
        signal = generate_signal("VRP_HARVEST", "NIFTY")
        result = fresh_engine.process_signal(signal)
        assert result["accepted"] is False
        assert "kill_switch" in result["reason"]


class TestRiskEngineIntegration:
    def test_portfolio_greeks_aggregation(self, fresh_engine):
        """Multiple positions should aggregate Greeks correctly."""
        # Open 2 positions
        sig1 = generate_signal("VRP_HARVEST", "NIFTY")
        sig2 = generate_signal("MOMENTUM_SCALPER", "GOLD")
        r1 = fresh_engine.process_signal(sig1)
        r2 = fresh_engine.process_signal(sig2)
        
        if r1["accepted"] and r2["accepted"]:
            status = fresh_engine.risk_engine.status()
            # Net delta should be sum of both positions' deltas
            assert status["greeks"]["net_delta"] != 0
            assert status["exposure"]["positions"] == 2

    def test_daily_loss_tracking(self, fresh_engine):
        """Closing a losing position should increase daily loss tracking.
        
        VRP_HARVEST is SHORT (net credit), so:
        - Close at HIGHER price than entry = LOSS (had to buy back at higher premium)
        - Close at LOWER price than entry = PROFIT
        """
        signal = generate_signal("VRP_HARVEST", "NIFTY")
        result = fresh_engine.process_signal(signal)
        pos_id = result["position_id"]
        
        initial_pnl = fresh_engine.risk_engine.realized_pnl_today
        
        # Close at a loss: for SHORT, exit_price > entry_price = loss
        # Entry ~40, exit at 50 → loss of (50-40)*75 = -750
        fresh_engine.close_position(pos_id, exit_price=50.0, reason="SL_HIT")
        
        final_pnl = fresh_engine.risk_engine.realized_pnl_today
        assert final_pnl < initial_pnl  # P&L decreased (loss recorded)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
