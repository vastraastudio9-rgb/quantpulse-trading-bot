"""
Unit tests for greeks.py — Black-Scholes option pricing + Greeks.
Run: python -m pytest tests/test_greeks.py -v
"""
import sys
import os
import math
import pytest

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from greeks import (
    option_price, delta, gamma, theta, vega, greeks_bundle,
    _norm_cdf, _norm_pdf, _d1, _d2
)


class TestNormalDistribution:
    def test_norm_cdf_at_zero(self):
        assert abs(_norm_cdf(0) - 0.5) < 1e-10

    def test_norm_cdf_symmetry(self):
        """N(x) + N(-x) = 1"""
        for x in [-3, -1, -0.5, 0, 0.5, 1, 3]:
            assert abs(_norm_cdf(x) + _norm_cdf(-x) - 1) < 1e-10

    def test_norm_cdf_at_1sd(self):
        """N(1) ≈ 0.8413, N(-1) ≈ 0.1587"""
        assert abs(_norm_cdf(1) - 0.8413) < 1e-4
        assert abs(_norm_cdf(-1) - 0.1587) < 1e-4

    def test_norm_pdf_at_zero(self):
        """PDF at 0 = 1/sqrt(2π) ≈ 0.3989"""
        assert abs(_norm_pdf(0) - 0.3989) < 1e-4


class TestOptionPricing:
    """Verify Black-Scholes against known textbook values.
    Reference: Hull, Options Futures and Other Derivatives, 10th Ed.
    
    Example: S=42, K=40, r=10%, σ=20%, T=0.5 years
    Expected: Call = 4.76, Put = 0.81
    """
    def test_call_price_hull_example(self):
        S, K, T, r, sigma = 42, 40, 0.5, 0.10, 0.20
        price = option_price(S, K, T, r, sigma, "CE")
        assert abs(price - 4.76) < 0.05, f"Expected ~4.76, got {price}"

    def test_put_price_hull_example(self):
        S, K, T, r, sigma = 42, 40, 0.5, 0.10, 0.20
        price = option_price(S, K, T, r, sigma, "PE")
        assert abs(price - 0.81) < 0.05, f"Expected ~0.81, got {price}"

    def test_put_call_parity(self):
        """S + P = C + K*e^(-rT) — fundamental no-arbitrage relation."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        call = option_price(S, K, T, r, sigma, "CE")
        put = option_price(S, K, T, r, sigma, "PE")
        lhs = S + put
        rhs = call + K * math.exp(-r * T)
        assert abs(lhs - rhs) < 1e-6, f"Put-call parity violated: {lhs} != {rhs}"

    def test_intrinsic_value_at_expiry(self):
        """At T=0, option value = intrinsic value."""
        # Call ITM
        assert abs(option_price(105, 100, 0, 0.05, 0.2, "CE") - 5) < 1e-6
        # Call OTM
        assert abs(option_price(95, 100, 0, 0.05, 0.2, "CE") - 0) < 1e-6
        # Put ITM
        assert abs(option_price(95, 100, 0, 0.05, 0.2, "PE") - 5) < 1e-6
        # Put OTM
        assert abs(option_price(105, 100, 0, 0.05, 0.2, "PE") - 0) < 1e-6

    def test_deep_itm_call_approaches_intrinsic(self):
        """Deep ITM call → S - K*e^(-rT)."""
        S, K, T, r, sigma = 200, 100, 0.5, 0.05, 0.30
        price = option_price(S, K, T, r, sigma, "CE")
        intrinsic = S - K * math.exp(-r * T)
        assert abs(price - intrinsic) < 0.5

    def test_volatility_zero_call_itm(self):
        """σ=0, call ITM → S - K*e^(-rT) (forward)."""
        S, K, T, r = 105, 100, 0.25, 0.05
        price = option_price(S, K, T, r, 0, "CE")
        expected = S - K * math.exp(-r * T)
        assert abs(price - expected) < 1e-6

    def test_volatility_zero_call_otm(self):
        """σ=0, call OTM → 0."""
        price = option_price(95, 100, 0.25, 0.05, 0, "CE")
        assert price == 0


class TestGreeks:
    """Verify Greeks against known values."""
    def test_call_delta_atm(self):
        """ATM call delta ≈ 0.5 + small time value adjustment."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        d = delta(S, K, T, r, sigma, "CE")
        assert 0.5 < d < 0.60, f"ATM call delta should be ~0.5-0.6, got {d}"

    def test_put_delta_atm(self):
        """ATM put delta ≈ -0.4 to -0.5 (less than -0.5 due to cost of carry with r>0)."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        d = delta(S, K, T, r, sigma, "PE")
        assert -0.55 < d < -0.40, f"ATM put delta should be ~-0.4 to -0.5, got {d}"

    def test_call_delta_deep_itm(self):
        """Deep ITM call delta → 1."""
        S, K, T, r, sigma = 200, 100, 0.25, 0.05, 0.30
        d = delta(S, K, T, r, sigma, "CE")
        assert d > 0.95, f"Deep ITM call delta should be ~1, got {d}"

    def test_call_delta_deep_otm(self):
        """Deep OTM call delta → 0."""
        S, K, T, r, sigma = 50, 100, 0.25, 0.05, 0.30
        d = delta(S, K, T, r, sigma, "CE")
        assert d < 0.05, f"Deep OTM call delta should be ~0, got {d}"

    def test_put_call_delta_parity(self):
        """Δ_put = Δ_call - 1 (European options)."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        d_call = delta(S, K, T, r, sigma, "CE")
        d_put = delta(S, K, T, r, sigma, "PE")
        assert abs(d_put - (d_call - 1)) < 1e-6

    def test_gamma_positive(self):
        """Gamma is always positive for long options."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        g = gamma(S, K, T, r, sigma)
        assert g > 0

    def test_gamma_highest_atm(self):
        """Gamma is highest at-the-money."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        g_atm = gamma(S, K, T, r, sigma)
        g_itm = gamma(120, K, T, r, sigma)
        g_otm = gamma(80, K, T, r, sigma)
        assert g_atm > g_itm
        assert g_atm > g_otm

    def test_theta_negative_for_long_call(self):
        """Long call theta is negative (loses value over time)."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        t = theta(S, K, T, r, sigma, "CE")
        assert t < 0, f"Long call theta should be negative, got {t}"

    def test_vega_positive(self):
        """Vega is always positive for long options."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        v = vega(S, K, T, r, sigma)
        assert v > 0

    def test_vega_highest_atm(self):
        """Vega is highest at-the-money."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        v_atm = vega(S, K, T, r, sigma)
        v_itm = vega(120, K, T, r, sigma)
        v_otm = vega(80, K, T, r, sigma)
        assert v_atm > v_itm
        assert v_atm > v_otm


class TestGreeksBundle:
    def test_bundle_returns_all_keys(self):
        result = greeks_bundle(100, 100, 0.25, 0.05, 0.30, "CE")
        for key in ["price", "delta", "gamma", "theta", "vega"]:
            assert key in result, f"Missing key: {key}"

    def test_bundle_price_matches_standalone(self):
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.30
        bundle = greeks_bundle(S, K, T, r, sigma, "CE")
        standalone = option_price(S, K, T, r, sigma, "CE")
        # bundle price is rounded to 2 decimals; raw should match exactly
        assert abs(bundle["price_raw"] - standalone) < 1e-6
        assert abs(bundle["price"] - round(standalone, 2)) < 1e-6


class TestEdgeCases:
    def test_zero_time_to_expiry(self):
        """T=0 → intrinsic value."""
        # ATM at expiry = 0
        assert option_price(100, 100, 0, 0.05, 0.3, "CE") == 0
        # ITM call at expiry = S - K
        assert abs(option_price(110, 100, 0, 0.05, 0.3, "CE") - 10) < 1e-6

    def test_zero_volatility(self):
        """σ=0 → option price = max(forward - K, 0) for call."""
        S, K, T, r = 100, 95, 0.25, 0.05
        # ITM call with σ=0
        expected = S - K * math.exp(-r * T)
        assert abs(option_price(S, K, T, r, 0, "CE") - expected) < 1e-6

    def test_negative_time_raises_or_returns_zero(self):
        """T<0 → treat as 0 (intrinsic)."""
        # Should not crash
        result = option_price(100, 100, -1, 0.05, 0.3, "CE")
        assert result >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
