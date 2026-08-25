import type { ResearchRepo } from "./types";

export const RESEARCH_STACK: Record<string, string> = {
  execution: "Broker adapters (Kite / MT5) behind a paper-first router",
  data: "Synthetic GBM here · swap for Kite historical + MT5 CopyRates live",
  strategies: "Defined-risk options + momentum overlays, regime-gated",
  risk: "Daily loss cap, kill switch, per-trade % of capital",
  validation: "OOS + walk-forward + Monte Carlo + red-team before size",
  alerts: "Local toasts · Telegram optional, never required to trade",
};

export const RESEARCH_INSIGHTS: string[] = [
  "No serious desk advertises 80%+ win rate. Target 55–60% with positive expectancy.",
  "Options selling has theoretically unlimited risk. Always pair with a hard stop.",
  "Backtests on synthetic GBM understate regime shifts. Forward-test 4+ weeks in paper.",
  "IV systematically overestimates realized vol — that is the VRP harvest, not a free lunch.",
  "SEBI algo rules (static IP, unique algo IDs, kill switch) apply before live Indian F&O.",
  "One GitHub repo will not cover Kite + MT5 + options greeks + validation. Compose layers.",
];

export const RESEARCH_REPOS: ResearchRepo[] = [
  { name: "freqtrade/freqtrade", url: "https://github.com/freqtrade/freqtrade", stars: "40k+", lang: "Python", license: "GPL-3", description: "Mature crypto bot with backtesting, hyperopt, and dry-run. Strong ops, not Indian F&O.", bestFor: "Bot ops patterns, dry-run discipline", rating: 5 },
  { name: "quantopian/zipline", url: "https://github.com/quantopian/zipline", stars: "19k+", lang: "Python", license: "Apache-2", description: "Event-driven US equity backtester. Pipeline API is the mental model for point-in-time data.", bestFor: "Point-in-time backtest design", rating: 4 },
  { name: "mementum/backtrader", url: "https://github.com/mementum/backtrader", stars: "17k+", lang: "Python", license: "GPL-3", description: "Flexible strategy framework with analyzers. Still a common teaching stack.", bestFor: "Strategy prototyping", rating: 4 },
  { name: "vnpy/vnpy", url: "https://github.com/vnpy/vnpy", stars: "32k+", lang: "Python", license: "MIT", description: "China-origin event engine with many gateways. Useful architecture, not Kite-native.", bestFor: "Event-driven gateway layout", rating: 4 },
  { name: "QuantConnect/Lean", url: "https://github.com/QuantConnect/Lean", stars: "16k+", lang: "C#", license: "Apache-2", description: "Institutional-grade engine used by QuantConnect cloud. Heavy, complete.", bestFor: "Multi-asset engine design", rating: 5 },
  { name: "nautechsystems/nautilus_trader", url: "https://github.com/nautechsystems/nautilus_trader", stars: "7k+", lang: "Python/Rust", license: "LGPL", description: "High-performance event-driven trader with Rust core. Production-minded.", bestFor: "Low-latency event core", rating: 5 },
  { name: "jesse-ai/jesse", url: "https://github.com/jesse-ai/jesse", stars: "7k+", lang: "Python", license: "MIT", description: "Crypto-focused with clean strategy classes and candle-accurate backtests.", bestFor: "Readable strategy API", rating: 4 },
  { name: "polakowo/vectorbt", url: "https://github.com/polakowo/vectorbt", stars: "6k+", lang: "Python", license: "Apache-2", description: "Vectorized research. Fast parameter sweeps, not live execution.", bestFor: "Research / walk-forward grids", rating: 5 },
];
