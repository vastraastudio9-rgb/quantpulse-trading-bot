import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backtest import run_backtest
from market_data import generate_history
from research_optimizer import load_policy, run_research
from risk_engine import PortfolioRiskEngine, Position


def test_backtest_accepts_chronological_bar_override():
    bars = generate_history("NIFTY", days=365, timeframe="1d")
    segment = bars[-80:]
    result = run_backtest("MOMENTUM_SCALPER", "NIFTY", bars_override=segment)
    assert result["bars_processed"] == len(segment)
    assert result["status"] == "COMPLETED"
    assert all(trade["duration_bars"] >= 1 for trade in result["all_trades"])


def test_research_policy_is_always_paper_only(tmp_path):
    path = tmp_path / "policy.json"
    policy = run_research(symbols=["NIFTY"], strategies=["MOMENTUM_SCALPER"], days=365, output_path=path)
    restored = load_policy(path)
    assert policy["paper_only"] is True
    assert policy["live_eligible"] is False
    assert policy["live_execution_enabled"] is False
    assert policy["research_active"] is True
    assert policy["paper_trading_active"] is True
    # The source depends on whether the local normalized store has approved
    # real candles. The safety invariant must hold for either evidence path.
    assert restored["data_source"] == policy["data_source"]
    assert restored["evidence_grade"] in {"REAL_MARKET", "ENGINEERING_ONLY"}
    assert policy["candidates_tested"] == 1


def test_paper_reset_clears_simulated_account(tmp_path):
    engine = PortfolioRiskEngine(initial_capital=100000, persist_path=tmp_path / "risk.json")
    engine.current_capital = 95000
    engine.realized_pnl_today = -5000
    engine._daily_loss_lock = True
    engine.limits.kill_switch = True
    result = engine.reset_paper_account()
    assert result["paper_only"] is True
    assert engine.current_capital == 100000
    assert engine.realized_pnl_today == 0
    assert engine._daily_loss_lock is False
    assert engine.limits.kill_switch is False
