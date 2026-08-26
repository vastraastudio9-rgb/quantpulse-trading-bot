"""Composable JARVIS runtime contracts and fail-closed provider selection.

Optional research frameworks are deliberately kept outside the execution path.
This module reports capabilities without importing, configuring, or activating a
broker. It never reads or returns credential values.
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Dict, List, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    open_interest: float = 0.0


@dataclass(frozen=True)
class ResearchRun:
    strategy: str
    symbol: str
    parameters: Dict
    provenance: Dict


@runtime_checkable
class MarketDataProvider(Protocol):
    def candles(self, instrument: str, interval: str, start: str, end: str) -> Sequence[Candle]: ...


@runtime_checkable
class ResearchEngine(Protocol):
    def run(self, request: ResearchRun, candles: Sequence[Candle]) -> Dict: ...


@runtime_checkable
class ExecutionProvider(Protocol):
    def submit(self, order: Dict) -> Dict: ...


@runtime_checkable
class GreeksProvider(Protocol):
    def calculate(self, inputs: Dict) -> Dict: ...


def _choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().upper()
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return value


def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


@dataclass(frozen=True)
class StackConfig:
    market_data_provider: str
    fast_research_engine: str
    validation_engine: str
    execution_provider: str
    greeks_provider: str
    forex_gateway: str
    scale_up_engine: str
    live_allowed: bool

    @classmethod
    def from_environment(cls) -> "StackConfig":
        live_allowed = os.getenv("ALLOW_LIVE_TRADING", "false").lower() == "true"
        execution = _choice("EXECUTION_PROVIDER", "PAPER", {"PAPER", "KITE", "OPENALGO"})
        # Selecting a live-capable adapter is not permission to use it. Keep the
        # effective route paper-only until the existing live approval flow passes.
        if not live_allowed:
            execution = "PAPER"
        return cls(
            market_data_provider=_choice("MARKET_DATA_PROVIDER", "KITE", {"KITE", "UPSTOX"}),
            fast_research_engine=_choice("FAST_RESEARCH_ENGINE", "DISABLED", {"DISABLED", "VECTORBT"}),
            validation_engine=_choice("VALIDATION_ENGINE", "EVENT_REPLAY", {"EVENT_REPLAY"}),
            execution_provider=execution,
            greeks_provider=_choice("GREEKS_PROVIDER", "INTERNAL", {"INTERNAL", "MIBIAN_CROSSCHECK"}),
            forex_gateway=_choice("FOREX_GATEWAY", "DISABLED", {"DISABLED", "MT5_ISOLATED"}),
            scale_up_engine=_choice("SCALE_UP_ENGINE", "DISABLED", {"DISABLED", "NAUTILUS_EVALUATION"}),
            live_allowed=live_allowed,
        )

    def manifest(self) -> Dict:
        components: List[Dict] = [
            {"role": "market_data", "selected": self.market_data_provider, "status": "ACTIVE"},
            {"role": "canonical_store", "selected": "DUCKDB_PARQUET", "status": "ACTIVE",
             "installed": _installed("duckdb")},
            {"role": "fast_research", "selected": self.fast_research_engine,
             "status": "AVAILABLE" if self.fast_research_engine == "VECTORBT" and _installed("vectorbt")
             else "MISSING_OPTIONAL_DEPENDENCY" if self.fast_research_engine == "VECTORBT" else "DISABLED",
             "installed": _installed("vectorbt")},
            {"role": "final_validation", "selected": self.validation_engine, "status": "ACTIVE"},
            {"role": "execution", "selected": self.execution_provider, "status": "PAPER_ONLY"
             if self.execution_provider == "PAPER" else "CONFIGURED_NOT_AUTHORIZED"},
            {"role": "greeks", "selected": self.greeks_provider, "status": "ACTIVE"},
            {"role": "forex", "selected": self.forex_gateway, "status": "DISABLED"
             if self.forex_gateway == "DISABLED" else "ISOLATED_ADVISORY"},
            {"role": "scale_up", "selected": self.scale_up_engine, "status": "DISABLED"
             if self.scale_up_engine == "DISABLED" else "EVALUATION_ONLY"},
        ]
        return {
            "architecture": "COMPOSABLE_PORTS_AND_ADAPTERS",
            "components": components,
            "execution_provider_count": 1,
            "duplicate_execution_routes_blocked": True,
            "research_can_place_orders": False,
            "paper_only": self.execution_provider == "PAPER",
            "live_allowed": self.live_allowed,
            "credentials_exposed": False,
        }


def get_stack_manifest() -> Dict:
    return StackConfig.from_environment().manifest()
