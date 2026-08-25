"""
Unit tests for strategies.py — signal generation logic.
Run: python -m pytest tests/test_strategies.py -v
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from strategies import STRATEGIES, generate_signal, generate_signals_feed


class TestStrategyDefinitions:
    def test_all_strategies_have_required_fields(self):
        for key, strat in STRATEGIES.items():
            for field in ["name", "type", "description", "direction", "edge_source", "typical_win_rate", "best_market", "entry_time", "exit_time"]:
                assert field in strat, f"Strategy {key} missing field {field}"

    def test_all_strategy_keys_are_unique(self):
        keys = list(STRATEGIES.keys())
        assert len(keys) == len(set(keys))

    def test_expected_strategies_present(self):
        """All 9 strategies must be defined."""
        expected = {
            "STRADDLE_SELL", "STRANGLE_SELL", "STRADDLE_BUY", "IRON_CONDOR",
            "MOMENTUM_SCALPER", "OPENING_RANGE_BREAKOUT",
            "LONG_BUTTERFLY", "IRON_BUTTERFLY", "CALENDAR_SPREAD",
        }
        assert expected.issubset(set(STRATEGIES.keys())), f"Missing: {expected - set(STRATEGIES.keys())}"


class TestSignalGeneration:
    def test_generate_straddle_sell_signal(self):
        sig = generate_signal("STRADDLE_SELL", "NIFTY")
        assert sig is not None
        assert sig["strategy_key"] == "STRADDLE_SELL"
        assert sig["symbol"] == "NIFTY"
        assert "legs" in sig
        assert len(sig["legs"]) == 2  # CE + PE
        # Both legs should be SELL
        for leg in sig["legs"]:
            assert leg["action"] == "SELL"
        # Should have CE and PE
        types = {leg["type"] for leg in sig["legs"]}
        assert types == {"CE", "PE"}
        # Same strike (ATM straddle)
        strikes = {leg["strike"] for leg in sig["legs"]}
        assert len(strikes) == 1
        # Required fields
        for field in ["entry_price", "stop_loss", "target", "confidence", "rationale"]:
            assert field in sig

    def test_generate_strangle_sell_signal(self):
        sig = generate_signal("STRANGLE_SELL", "NIFTY")
        assert sig is not None
        assert len(sig["legs"]) == 2
        # OTM strangle: CE strike > PE strike
        ce_leg = next(l for l in sig["legs"] if l["type"] == "CE")
        pe_leg = next(l for l in sig["legs"] if l["type"] == "PE")
        assert ce_leg["strike"] > pe_leg["strike"], "Strangle CE strike should be > PE strike"

    def test_generate_iron_condor_signal(self):
        sig = generate_signal("IRON_CONDOR", "NIFTY")
        assert sig is not None
        assert len(sig["legs"]) == 4  # 2 sells + 2 buys
        actions = [l["action"] for l in sig["legs"]]
        assert actions.count("SELL") == 2
        assert actions.count("BUY") == 2

    def test_generate_long_butterfly_signal(self):
        sig = generate_signal("LONG_BUTTERFLY", "NIFTY")
        assert sig is not None
        assert len(sig["legs"]) == 3
        # All CE
        for leg in sig["legs"]:
            assert leg["type"] == "CE"
        # Actions: BUY, SELL (qty 2), BUY
        actions = [l["action"] for l in sig["legs"]]
        assert actions == ["BUY", "SELL", "BUY"]
        # Strikes should be ITM < ATM < OTM
        strikes = [l["strike"] for l in sig["legs"]]
        assert strikes[0] < strikes[1] < strikes[2]

    def test_generate_iron_butterfly_signal(self):
        sig = generate_signal("IRON_BUTTERFLY", "NIFTY")
        assert sig is not None
        assert len(sig["legs"]) == 4
        # ATM straddle sold (CE + PE same strike)
        sell_legs = [l for l in sig["legs"] if l["action"] == "SELL"]
        assert len(sell_legs) == 2
        sell_strikes = {l["strike"] for l in sell_legs}
        assert len(sell_strikes) == 1  # same strike (ATM)
        # Wings bought at different strikes
        buy_legs = [l for l in sig["legs"] if l["action"] == "BUY"]
        assert len(buy_legs) == 2
        buy_strikes = {l["strike"] for l in buy_legs}
        assert len(buy_strikes) == 2  # different strikes

    def test_generate_calendar_spread_signal(self):
        sig = generate_signal("CALENDAR_SPREAD", "NIFTY")
        assert sig is not None
        assert len(sig["legs"]) == 2
        # Both same strike
        strikes = {l["strike"] for l in sig["legs"]}
        assert len(strikes) == 1
        # One SELL (near-week) + one BUY (far-week)
        actions = [l["action"] for l in sig["legs"]]
        assert "SELL" in actions
        assert "BUY" in actions
        # Should have expiry field
        for leg in sig["legs"]:
            assert "expiry" in leg

    def test_invalid_strategy_returns_none(self):
        sig = generate_signal("INVALID_STRATEGY", "NIFTY")
        assert sig is None

    def test_invalid_symbol_raises(self):
        with pytest.raises(ValueError):
            generate_signal("STRADDLE_SELL", "INVALID_SYMBOL")

    def test_confidence_in_valid_range(self):
        """Confidence must be between 50 and 92."""
        for strat_key in STRATEGIES.keys():
            for symbol in ["NIFTY", "BANKNIFTY", "GOLD"]:
                sig = generate_signal(strat_key, symbol)
                if sig:
                    assert 50 <= sig["confidence"] <= 92, f"{strat_key} confidence {sig['confidence']} out of range"

    def test_signal_has_unique_id(self):
        sig1 = generate_signal("STRADDLE_SELL", "NIFTY")
        sig2 = generate_signal("STRADDLE_SELL", "NIFTY")
        assert sig1["signal_id"] != sig2["signal_id"]

    def test_signal_has_breakevens_for_options_strategies(self):
        """Option strategies should have breakevens."""
        for strat_key in ["STRADDLE_SELL", "STRANGLE_SELL", "STRADDLE_BUY", "IRON_CONDOR", "IRON_BUTTERFLY", "LONG_BUTTERFLY", "CALENDAR_SPREAD"]:
            sig = generate_signal(strat_key, "NIFTY")
            if sig:
                assert "breakeven_upper" in sig or "breakeven_lower" in sig, f"{strat_key} missing breakevens"

    def test_signal_has_rationale(self):
        """Every signal must have a rationale explaining the trade."""
        for strat_key in STRATEGIES.keys():
            sig = generate_signal(strat_key, "NIFTY")
            if sig:
                assert "rationale" in sig
                assert len(sig["rationale"]) > 20, f"{strat_key} rationale too short"

    def test_stop_loss_and_target_present(self):
        for strat_key in STRATEGIES.keys():
            sig = generate_signal(strat_key, "NIFTY")
            if sig:
                assert "stop_loss" in sig
                assert "target" in sig
                assert sig["stop_loss"] > 0
                assert sig["target"] > 0


class TestSignalsFeed:
    def test_feed_returns_list(self):
        feed = generate_signals_feed(limit=5)
        assert isinstance(feed, list)
        assert len(feed) <= 5

    def test_feed_signals_have_required_fields(self):
        feed = generate_signals_feed(limit=3)
        for sig in feed:
            assert "signal_id" in sig
            assert "strategy_name" in sig
            assert "symbol" in sig
            assert "confidence" in sig
            assert "legs" in sig


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
