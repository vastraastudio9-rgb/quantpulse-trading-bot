# Comprehensive Research Report: Open-Source Trading Bots for Indian F&O, Multi-Asset & Forex Trading

**Research Date:** August 2026
**Prepared for:** Retail algo trader targeting NIFTY/BANKNIFTY options straddle/strangle strategies + Forex (MT5) + MCX commodities
**Platform constraint:** Windows, Python-based, with backtesting capability

---

## Table of Contents

1. [Executive Summary & Recommended Stack](#1-executive-summary--recommended-stack)
2. [Top Indian F&O / Zerodha-Focused Repos (Ranked)](#2-top-indian-fo--zerodha-focused-repos-ranked)
3. [Multi-Asset & General-Purpose Python Trading Frameworks (Ranked)](#3-multi-asset--general-purpose-python-trading-frameworks-ranked)
4. [MetaTrader 5 / Forex Repos](#4-metatrader-5--forex-repos)
5. [Supporting Indian-Market Libraries](#5-supporting-indian-market-libraries)
6. [Backtesting Libraries — Detailed Comparison](#6-backtesting-libraries--detailed-comparison)
7. [Technical Analysis Libraries](#7-technical-analysis-libraries)
8. [Options Strategy & Greeks Calculation Libraries](#8-options-strategy--greeks-calculation-libraries)
9. [Real-Time Data Feed Options](#9-real-time-data-feed-options)
10. [Curated "Awesome" Lists Worth Bookmarking](#10-curated-awesome-lists-worth-bookmarking)
11. [Commercial Open-Source Alternatives to AlgoBulls / IntelligenceTrade](#11-commercial-open-source-alternatives-to-algobulls--intelligencetrade)
12. [Common Pitfalls in Retail Algo Trading in India](#12-common-pitfalls-in-retail-algo-trading-in-india)
13. [Final Recommendations & Suggested Architecture](#13-final-recommendations--suggested-architecture)

---

## 1. Executive Summary & Recommended Stack

After surveying 40+ search results across GitHub topics, Reddit (r/IndianQuants, r/IndiaAlgoTrading, r/algotrading), Medium articles, and the official Kite Connect forum, the following **recommended stack** emerges for a retail trader on Windows who needs Zerodha (Indian F&O) + MT5 (Forex) + options straddle/strangle backtesting:

| Need | Best Open-Source Choice | Why |
|------|------------------------|-----|
| **Indian broker connectivity (Zerodha + 34 others)** | **OpenAlgo** (marketcalls/openalgo) | Self-hosted unified API across 34+ Indian brokers, actively maintained, Windows-compatible |
| **Official Zerodha low-level API** | **zerodha/pykiteconnect** | The canonical Python client for Kite Connect REST + KiteTicker WebSocket |
| **Multi-broker India library (code-level)** | **Fenix** (PyPI `fenix`) | Unified Python API across 15+ Indian brokers |
| **Backtesting engine (fast/vectorized)** | **VectorBT** | Numba/Rust-accelerated, handles 6+ months of tick/minute data easily |
| **Backtesting engine (event-driven, readable)** | **Backtrader** + `openalgo-backtrader` store | Mature, integrates with OpenAlgo/Zerodha via community store |
| **MT5 / Forex** | **MetaTrader5** (official PyPI package) + **aiomql** | Official MT5-Python bridge + async wrapper |
| **Multi-asset production engine** | **NautilusTrader** | Rust-native core, Python API, supports options/futures/forex/crypto, deterministic backtest→live parity |
| **Options Greeks** | **mibian** + **CarloLepelaars/blackscholes** | Black-Scholes Greeks (delta/gamma/vega/theta/rho) for NSE options |
| **NSE data scraping** | **aeron7/nsepython** | Unofficial NSE wrapper for option chain, Greeks, India VIX |
| **Options-strategy reference code** | **buzzsubash/algo_trading_strategies_india** | Ready-made NIFTY/BANKNIFTY option-selling strategies |

**Key finding:** No single open-source repo simultaneously (a) supports Zerodha Kite for Indian F&O, (b) supports MT5 for forex, (c) has built-in options-straddle backtesting, and (d) is actively maintained. The realistic approach is **a composable stack** (OpenAlgo + pykiteconnect + MetaTrader5 + VectorBT/Backtrader + mibian), optionally fronted by NautilusTrader for a unified engine.

---

## 2. Top Indian F&O / Zerodha-Focused Repos (Ranked)

### 🥇 #1 — OpenAlgo  ⭐ THE TOP PICK FOR INDIAN MARKETS
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/marketcalls/openalgo |
| **Stars** | ~3,500+ (fast-growing; ~2.5k in early 2026, 3.5k+ by mid-2026) |
| **Last update** | Very active — commits weekly; v1.x releases throughout 2026 |
| **What it does** | Self-hosted, open-source, full-stack algo trading platform providing a **unified API layer across 34+ Indian brokers**. Built on Python Flask + React 19. Not just a broker bridge — a complete design/host/execute environment. |
| **Tech stack** | Python (Flask backend), React 19 (frontend), REST API, Docker image available |
| **Broker integrations** | **35+ Indian brokers**: Zerodha, Angel One, AliceBlue, Upstox, Dhan, Fyers, Kotak, 5paisa (Standard + XTS), KotakNeo, ICICI Direct, and many more via plugins |
| **Backtesting** | No native engine (designed as execution/analytics layer); integrates with Backtrader via `p2c2e/openalgo-backtrader` store. Has its own strategy templates (e.g. intraday rolling straddles). |
| **Strategy / options support** | Options analytics built in; sample strategies include **intraday rolling short straddle for NIFTY index options** (ATM straddle sell + rolling). Greeks calculation via Mibian integration. |
| **License** | AGPL-3.0 (copyleft — note for commercial use) |
| **Why it's good** | Single API across all major Indian brokers (write once, trade anywhere); Windows/Mac/Linux/VPS deployment; self-hosted (no SaaS lock-in); TradingView + Excel + MCP integration; strong community (FOSS United partner project); very actively maintained by marketcalls.in (Rajandran R). |
| **Limitations** | India-only broker support (no MT5/forex); AGPL license may restrict commercial redistribution; no built-in backtesting engine (pair with Backtrader/VectorBT). |

### 🥈 #2 — Zerodha Official pykiteconnect (foundational library)
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/zerodha/pykiteconnect |
| **Stars** | ~1,100+ |
| **Last update** | Actively maintained (official Zerodha repo) |
| **What it does** | The official Python client for Kite Connect REST APIs + KiteTicker WebSocket. Foundational library that nearly every Indian algo repo builds on. |
| **Tech stack** | Pure Python; `pip install kiteconnect` |
| **Broker integrations** | Zerodha only (it IS the Zerodha API client) |
| **Backtesting** | None (data/execution layer only) |
| **Strategy / options support** | Full API access: place multi-leg options orders, fetch option chain, historical candles, live ticks. Supports AMO, GTT, bracket/cover orders. |
| **License** | MIT |
| **Why it's good** | Official, battle-tested, well-documented, exposes KiteTicker WebSocket for real-time tick data, historical data API for backtesting data sourcing. Required building block. |
| **Limitations** | Low-level (you build everything on top); Kite Connect costs ₹500/month (₹2,000/month post-SEBI Aug 2025 changes for higher limits). |

### 🥉 #3 — buzzsubash/algo_trading_strategies_india
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/buzzsubash/algo_trading_strategies_india |
| **Stars** | ~300-500 (top result under `zerodha` topic sorted by stars) |
| **Last update** | Updated 2026; actively maintained |
| **What it does** | Open-source Python repo of **algorithmic trading strategies for NSE/BSE, focused on option selling** in NIFTY 50, BANK NIFTY, FIN NIFTY, MIDCAP NIFTY, and SENSEX. |
| **Tech stack** | Python; uses Zerodha Kite Connect (currently Zerodha, with planned multi-broker integration) |
| **Broker integrations** | Zerodha (primary); multi-broker planned |
| **Backtesting** | Strategy code includes backtest logic; pairs well with external backtesters |
| **Strategy / options support** | **Excellent for the user's exact use case** — option-selling strategies including straddle/strangle setups on NIFTY/BANKNIFTY/FINNIFTY/MIDCAPNIFTY/SENSEX |
| **License** | Not specified in search results (verify before use) |
| **Why it's good** | Ready-made, India-specific option strategies; directly targets the straddle/strangle requirement; frequently updated. |
| **Limitations** | Strategy recipe repo, not a full framework; limited documentation; broker coupling to Zerodha. |

### #4 — debanshur/algotrading
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/debanshur/algotrading |
| **Stars** | ~200+ |
| **Last update** | Active in 2025-2026 |
| **What it does** | Python-based algorithmic trading platform integrating with Zerodha for automated trading strategies. Comprehensive set of tools. |
| **Tech stack** | Python, Zerodha Kite Connect |
| **Broker integrations** | Zerodha |
| **Backtesting** | Yes (in-built backtest utilities) |
| **Strategy / options support** | Multiple strategies; Indian market focused |
| **License** | Check repo |
| **Why it's good** | End-to-end platform approach with Zerodha integration. |
| **Limitations** | Single-author project; smaller community than OpenAlgo. |

### #5 — aaryansinha16/AI-trader (NSE F&O Research System)
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/aaryansinha16/AI-trader |
| **Stars** | Growing (featured in nse-india topic) |
| **Last update** | Active 2025-2026 |
| **What it does** | Full-stack **intraday options trading research platform for NIFTY** — tick-level replay backtest engine, XGBoost + RL ML models, dynamic risk management, live execution. |
| **Tech stack** | Python, XGBoost, Reinforcement Learning, TimescaleDB |
| **Broker integrations** | NSE F&O (Indian brokers) |
| **Backtesting** | **Tick-level replay engine** (superior granularity for options) |
| **Strategy / options support** | NIFTY F&O options; ML-driven |
| **License** | Research/educational |
| **Why it's good** | Tick-level backtest is rare and valuable for options where intrabar behavior matters; ML integration. |
| **Limitations** Research-oriented; complex setup (TimescaleDB); ML models need significant data/compute. |

### #6 — umeshpalai/Algorithmic-Trading---Backtesting---Banknifty-Straddle-using-Python
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/umeshpalai/Algorithmic-Trading---Backtesting---Banknifty-Straddle-using-Python |
| **Stars** | Small but targeted |
| **Last update** | Reference implementation |
| **What it does** | **Complete backtest of BankNifty Option Straddle** in pure Python. |
| **Why it's good** | Directly matches the straddle requirement; clear reference code. |
| **Limitations** | Single-strategy reference repo, not a framework. |

### #7 — VarunS2002/Python-NSE-Option-Chain-Analyzer
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer |
| **Stars** | ~400+ |
| **Last update** | Maintained |
| **What it does** | Retrieves near-real-time option chain data from NSE website and performs analysis (PCR, max pain, strike concentration). |
| **Why it's good** | Free option-chain data without paid API; useful input for straddle/strangle strikes selection. |
| **Limitations** | Web-scraping NSE (fragile, may break on NSE site changes); not a trading bot itself. |

### #8 — althk/zerobha
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/althk/zerobha |
| **Stars** | Small/niche |
| **What it does** | High-performance algorithmic trading bot for Indian Equity markets (NSE), emphasizing emotional discipline. |
| **Why it's good** | Clean, focused NSE equity bot. |
| **Limitations** | Equity-focused, limited F&O options support. |

### #9 — Jayraj2304/zerodha-tradebot (AI-Powered)
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/Jayraj2304/zerodha-tradebot |
| **Stars** | Newer project |
| **What it does** | AI-powered trading assistant bridging conversational AI with real-world Zerodha trading operations. |
| **Why it's good** | Modern LLM-agent architecture; interesting for AI-assisted trading. |
| **Limitations** | Experimental; relies on LLM decision-making (risky for live capital). |

### #10 — aeron7/Mastering-AlgoTrading-A-Beginners-Guide-using-KiteConnect-API
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/aeron7/Mastering-AlgoTrading-A-Beginners-Guide-using-KiteConnect-API |
| **Stars** | ~500+ |
| **What it does** | Educational repo accompanying the popular "Mastering AlgoTrading" book/course by aeron7 (same author as nsepython). Includes Guppy indicator bot, OHLC→candlestick plotting, historical data fetching. |
| **Why it's good** | Excellent learning resource; well-documented Zerodha integration patterns. |
| **Limitations** | Tutorial code, not production. |

### #11 — arshadakl/intraday-trading-bot
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/arshadakl/intraday-trading-bot |
| **Stars** | Featured in nse-india topic |
| **What it does** | Institutional-grade automated trading bot for Indian stock market (NSE) using enhanced VWAP + RSI strategy with multi-layer confirmation. |
| **Why it's good** | Claims high win-rate strategy; multi-indicator confirmation. |
| **Limitations** | Equity intraday focused, not options. |

### #12 — marketcalls/openbull (OpenAlgo sibling for options)
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/marketcalls/openbull |
| **Stars** | Newer (2026) |
| **What it does** | Self-hosted **options trading platform** for Indian markets. Multi-user, multi-broker, with typed external API mirroring OpenAlgo. |
| **Why it's good** | Purpose-built for options (vs. OpenAlgo's general scope); same maintainer. |
| **Limitations** | Very new; smaller community than OpenAlgo. |

---

## 3. Multi-Asset & General-Purpose Python Trading Frameworks (Ranked)

### 🥇 #1 — NautilusTrader  ⭐ BEST FOR MULTI-ASSET PRODUCTION
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/nautechsystems/nautilus_trader |
| **Stars** | ~3,500+ (rapidly growing, heavily promoted in 2026) |
| **Last update** | Extremely active — releases every few weeks (v1.x in Aug 2026) |
| **What it does** | Open-source, **production-grade, Rust-native engine for multi-asset, multi-venue trading systems**. Spans research, deterministic backtesting, and live deployment. |
| **Tech stack** | Rust core + Python API (also pure-Rust possible) |
| **Broker integrations** | Binance, OKX, Interactive Brokers (equities, ETFs, equity options), Betfair; community adapters growing |
| **Backtesting** | **Deterministic backtest→live parity** (same code, same results) — a standout feature |
| **Strategy / options support** | Supports equities, futures, **options**, forex, crypto, betting instruments |
| **License** | LGPL-3.0 (core); check integrations |
| **Why it's good** | Fastest Python-accessible engine (Rust core); true backtest/live parity; multi-asset/multi-venue; serious production quality. |
| **Limitations** | Steeper learning curve; no native Indian broker adapter (would need custom adapter via OpenAlgo or IB); Windows support improving but Rust toolchain setup needed. |

### 🥈 #2 — Freqtrade  ⭐ MOST POPULAR OPEN-SOURCE BOT
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/freqtrade/freqtrade |
| **Stars** | **~40,000** (39.9k per Jun 2025 Medium) |
| **Last update** | Very active (continuous releases) |
| **What it does** | Free, open-source crypto trading bot with backtesting, plotting, money management, and ML-based strategy optimization. |
| **Tech stack** | Python; Telegram + WebUI control |
| **Broker integrations** | Crypto exchanges (Binance, Kraken, etc.) — **NOT Indian brokers, NOT MT5** |
| **Backtesting** | Full backtesting + dry-run (paper trading) + hyperopt optimization |
| **Strategy / options support** | Crypto spot/futures; **no options support** |
| **License** | GPL-3.0 |
| **Why it's good** | Most mature, best-documented open-source bot; huge community; excellent paper-trading and optimization. Great reference architecture. |
| **Limitations** | Crypto-only; cannot directly trade Indian F&O or forex via MT5. Useful as architecture reference or for crypto diversification. |

### 🥉 #3 — VectorBT  ⭐ BEST FOR FAST BACKTESTING
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/polakowo/vectorbt |
| **Stars** | ~4,500+ |
| **Last update** | Active (PRO version is the focus; OSS version maintained) |
| **What it does** | Vectorized backtesting engine built on pandas/NumPy/Numba with optional **Rust engine** for precompiled speed. |
| **Tech stack** | Python, NumPy, Numba, Rust (optional) |
| **Broker integrations** | Data-agnostic; works with any OHLCV data (fetch via pykiteconnect/nsepython) |
| **Backtesting** | **Ultra-fast** — vectorized, handles large parameter grids; perfect for 6+ month historical data |
| **Strategy / options support** | Primarily directional; options payoff modeling possible but not first-class |
| **License** | Apache-2.0 (OSS); VectorBT PRO is paid |
| **Why it's good** | Orders of magnitude faster than event-driven backtesters; great for parameter sweeps; excellent visualization. |
| **Limitations** | Vectorized paradigm less intuitive for multi-leg options timing; no live trading in OSS (PRO has it); PRO is paid. |

### #4 — Backtrader  ⭐ MOST READABLE / INDIAN INTEGRATIONS EXIST
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/mementum/backtrader |
| **Stars** | **~22,900** |
| **Last update** | Core development slowed after 2020; **community still active** with forks and stores |
| **What it does** | Feature-rich Python framework for backtesting and live trading. Event-driven, readable strategy classes. |
| **Tech stack** | Pure Python |
| **Broker integrations** | IB, OANDA, Alpaca built-in; **Zerodha via community stores** (`openalgo-backtrader`, Medium guides for Zerodha API integration) |
| **Backtesting** | Full event-driven backtesting with analyzers, sizers, commission models |
| **Strategy / options support** | Multi-asset; community has built options strategies |
| **License** | GPL-3.0 |
| **Why it's good** | Most readable strategy code; huge knowledge base; explicit Zerodha integration tutorials; `openalgo-backtrader` store bridges to OpenAlgo. |
| **Limitations** | Core unmaintained since ~2020; slower than VectorBT; no native options Greeks. |

### #5 — Jesse  ⭐ CLEAN CRYPTO/FOREX FRAMEWORK
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/jesse-ai/jesse |
| **Stars** | **~8,400** (per TrendingBots Aug 2026) |
| **Last update** | Active |
| **What it does** | Advanced crypto trading framework — research, define, backtest, optimize, live-trade your own strategies. |
| **Tech stack** | Python; web dashboard |
| **Broker integrations** | Crypto exchanges; **live trading requires Jesse Pro (~$700/year)** |
| **Backtesting** | Excellent backtesting + optimization; clean strategy DSL |
| **Strategy / options support** | Crypto-focused; no options |
| **License** | MIT (framework); Jesse Pro is paid |
| **Why it's good** | Cleanest strategy syntax; great docs; good for crypto side of portfolio. |
| **Limitations** | Crypto-focused; live trading paywalled; no Indian broker/MT5 support. |

### #6 — QuantConnect LEAN  ⭐ INSTITUTIONAL-GRADE, MULTI-ASSET
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/QuantConnect/Lean |
| **Stars** | ~9,500+ |
| **Last update** | Very active (QuantConnect is a funded company) |
| **What it does** | Event-driven, professional-caliber algorithmic trading engine. Multi-asset: equities, forex, CFDs, futures, options, crypto. |
| **Tech stack** | C# core with Python algorithm support (via PythonNet) |
| **Broker integrations** | IB, Alpaca, Coinbase, Binance, Tradier, OANDA, Bitfinex — **20+ brokers**. **No direct Indian broker** (IB India possible indirectly). |
| **Backtesting** | World-class; free cloud backtesting with QuantConnect data |
| **Strategy / options support** | **Full options support** including multi-leg strategies |
| **License** | Apache-2.0 |
| **Why it's good** | Institutional quality; free cloud backtesting with curated data; Python + C#; options support is first-class. |
| **Limitations** | No native Zerodha/MT5; C#-centric (Python is second-class); cloud-oriented. |

### #7 — StockSharp (S#)  ⭐ BROAD EXCHANGE SUPPORT (C#)
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/StockSharp/StockSharp |
| **Stars** | ~7,000+ |
| **Last update** | Active |
| **What it does** | Full-featured C# library for trading robots. Supports HFT, arbitrage, DMA; **70-90+ exchanges/brokers**. |
| **Tech stack** | C# (.NET) — **not Python** |
| **Broker integrations** | 90+ connectors including forex, crypto, futures, options, stocks |
| **Backtesting** | Built-in backtesting + S#.Studio GUI |
| **Strategy / options support** | Options supported; visual strategy designer |
| **License** | Freeware (S#.API free; S#.Studio free) |
| **Why it's good** | Widest exchange coverage of any open-source platform; supports MT4/MT5 bridges; Windows-native (.NET). |
| **Limitations** | **C#, not Python** (conflicts with user's Python preference); steep learning curve; documentation heavily Russian. |

### #8 — PyAlgoTrade
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/gbeced/pyalgotrade |
| **Stars** | ~2,200 |
| **Last update** | Last commit ~Nov 2023 (low activity) |
| **What it does** | Event-driven Python algorithmic trading library with paper/live trading. |
| **Tech stack** | Python (2 & 3) |
| **Broker integrations** | Bitstamp, Talib; CSV/Yahoo/Google data |
| **Backtesting** | Event-driven backtesting |
| **Strategy / options support** | Limited |
| **License** | Apache-2.0 |
| **Why it's good** | Mature, fully documented, simple. |
| **Limitations** | Effectively unmaintained; superseded by Backtrader/VectorBT for most use cases. |

### #9 — Backtesting.py
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/kernc/backtesting.py |
| **Stars** | ~5,000+ |
| **Last update** | Active |
| **What it does** | Fast, simple Python framework for backtesting on historical candlestick data. Stocks, forex, crypto, futures compatible. |
| **Tech stack** | Pure Python; SAMBO optimizer |
| **Broker integrations** | None (backtesting only) |
| **Backtesting** | Single-strategy backtest with optimization |
| **License** | AGPL-3.0 |
| **Why it's good** | Simplest API; great for quick strategy validation. |
| **Limitations** | Backtesting only (no live); single-strategy focus; AGPL. |

### #10 — Hummingbot
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/hummingbot/hummingbot |
| **Stars** | ~9,000+ |
| **What it does** | Open-source Python framework for crypto market making / agentic strategies on CEX + DEX. |
| **Why it's good** | Best for market-making strategies. |
| **Limitations** | Crypto-only; not relevant to Indian F&O or MT5 forex. |

### #11 — OctoBot
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/Drakkar-Software/OctoBot |
| **Stars** | ~3,500+ |
| **What it does** | Open-source crypto trading bot with web UI. |
| **Why it's good** | User-friendly; good community. |
| **Limitations** | Crypto-only. |

### #12 — TensorTrade
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/tensortrade-org/tensortrade |
| **Stars** | ~4,600+ |
| **What it does** | RL-based trading framework (deep reinforcement learning). |
| **Why it's good** | Best for ML/RL research. |
| **Limitations** | Research-oriented; RL strategies unstable in production. |

---

## 4. MetaTrader 5 / Forex Repos

### 🥇 #1 — Official MetaTrader5 Python Package
| Field | Detail |
|-------|--------|
| **URL** | https://pypi.org/project/MetaTrader5/ (docs: https://www.mql5.com/en/docs/python_metatrader5) |
| **Stars** | N/A (official MetaQuotes package) |
| **Last update** | Maintained by MetaQuotes |
| **What it does** | Official Python integration — request bars/ticks, send orders, manage positions directly from MT5 terminal. |
| **Tech stack** | Python; requires MT5 terminal installed (Windows native; Wine on Linux via `mt5linux`) |
| **Broker integrations** | Any MT5 broker (hundreds of forex brokers) |
| **Backtesting** | Pulls historical data for external backtesters; MT5's own Strategy Tester is separate |
| **Strategy support** | Full order management; forex, CFDs, futures |
| **License** | Free (proprietary) |
| **Why it's good** | Official, reliable, the canonical MT5↔Python bridge. **Windows-native (perfect for user's Windows requirement).** |
| **Limitations** | Requires MT5 terminal running; Windows-only natively (Linux needs Wine + `mt5linux`); no built-in backtesting (use MT5 Strategy Tester or external). |

### #2 — Ichinga-Samuel/aiomql
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/Ichinga-Samuel/aiomql |
| **Stars** | Growing |
| **What it does** | Asynchronous Python framework for building algo trading bots on MT5. Wraps every MT5 API call in async-friendly interface. |
| **Tech stack** | Python (asyncio) |
| **Why it's good** | Async MT5 trading; cleaner than raw `MetaTrader5` package. |
| **Limitations** | Smaller community; MT5-only. |

### #3 — Maxiviper117/PyTrader-python-mt4-mt5
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/Maxiviper117/PyTrader-python-mt4-mt5 |
| **Stars** | ~500+ |
| **What it does** | Drag-and-drop EA connecting MT4 **and** MT5 to Python — end-to-end solution. |
| **Why it's good** | Supports both MT4 and MT5; simple EA-based setup. |
| **Limitations** | EA-based (heavier than pure Python package). |

### #4 — lucas-campagna/mt5linux
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/lucas-campagna/mt5linux |
| **What it does** | Runs MetaTrader5 on Linux via Wine + RPyC + standalone `mt5server.exe`. |
| **Why it's good** | Enables MT5 Python on Linux. |
| **Limitations** | Not needed on Windows (user is on Windows). |

### #5 — MetaApi (cloud MT5)
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/metaapi/metaapi-python-sdk |
| **What it does** | Cloud forex trading API for MT4/MT5; free usage tier. |
| **Why it's good** | No local MT5 terminal needed; cloud-accessible. |
| **Limitations** | Cloud dependency; latency; free tier limits. |

---

## 5. Supporting Indian-Market Libraries

### Fenix (Multi-Broker India Library)
| Field | Detail |
|-------|--------|
| **URL** | https://pypi.org/project/fenix/ (Reddit r/IndiaAlgoTrading) |
| **Stars** | PyPI package (~60+ stars on PyPI per author) |
| **What it does** | Unified Python API across **15+ Indian stock brokers**: Zerodha, AliceBlue, KotakNeo, Dhan, Angel One, Fyers, Upstox, and more. |
| **Why it's good** | Code-level multi-broker abstraction (vs OpenAlgo's platform approach); recent (2026); solves "rewrite broker integration every time." |
| **Limitations** | Newer, smaller community; execution-focused (no backtesting). |

### aeron7/nsepython
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/aeron7/nsepython |
| **Stars** | ~600+ |
| **What it does** | Unofficial Python wrapper for NSE India website — stock quotes, live indices, **option chain, option Greeks, India VIX**, historical data, Bhavcopy. |
| **Why it's good** | Free NSE data + Greeks calculation; well-documented by Unofficed community; same author as the Mastering AlgoTrading course. |
| **Limitations** | Scraping-based (may break on NSE changes); not for execution. |

### p2c2e/openalgo-backtrader
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/p2c2e/openalgo-backtrader |
| **What it does** | Backtrader integration for OpenAlgo — stores, feeds, brokers. Tested with Zerodha backend at OpenAlgo. |
| **Why it's good** | Bridges the two most recommended tools (Backtrader + OpenAlgo) for Indian-market backtesting. |

---

## 6. Backtesting Libraries — Detailed Comparison

| Library | Stars | Paradigm | Speed | Live Trading | Indian Mkt Fit | Options | License | Status |
|---------|-------|----------|-------|--------------|-----------------|---------|---------|--------|
| **VectorBT** | ~4.5k | Vectorized | ⚡⚡⚡ (Numba/Rust) | PRO only | Excellent (data-agnostic) | Limited | Apache-2.0 | Active |
| **Backtrader** | ~22.9k | Event-driven | ⚡ (slow) | Yes (IB/OANDA/Zerodha via stores) | Excellent (Zerodha stores exist) | Community | GPL-3.0 | Core frozen, community alive |
| **Freqtrade** | ~40k | Event-driven | ⚡ | Yes (crypto) | N/A (crypto) | No | GPL-3.0 | Very active |
| **NautilusTrader** | ~3.5k | Event-driven (Rust) | ⚡⚡⚡ | Yes (IB/Binance) | Good (via IB) | Yes | LGPL-3.0 | Very active |
| **QuantConnect LEAN** | ~9.5k | Event-driven | ⚡⚡ | Yes (20+ brokers) | Indirect (IB India) | Yes (first-class) | Apache-2.0 | Very active |
| **Backtesting.py** | ~5k | Event-driven | ⚡ | No | Data-agnostic | Limited | AGPL-3.0 | Active |
| **PyAlgoTrade** | ~2.2k | Event-driven | ⚡ | Yes (limited) | Data-agnostic | Limited | Apache-2.0 | Unmaintained |
| **Jesse** | ~8.4k | Event-driven | ⚡⚡ | Pro only | Crypto-only | No | MIT (Pro paid) | Active |

**Recommendation for Indian F&O options backtesting:**
- Use **VectorBT** for fast parameter sweeps on straddle/strangle payoff models (after sourcing historical option premiums via Kite historical API / nsepython).
- Use **Backtrader** (+ `openalgo-backtrader` store) for event-driven multi-leg option strategy logic with realistic fills/slippage.
- For tick-level options replay, study **aaryansinha16/AI-trader**'s tick-replay engine.

---

## 7. Technical Analysis Libraries

| Library | URL | Stars | Notes |
|---------|-----|-------|-------|
| **TA-Lib** | https://ta-lib.org / `pip install TA-Lib` | ~10k+ (wrappers) | Industry standard: **200+ indicators** (ADX, MACD, RSI, Bollinger), candlestick patterns. C/C++ core with Python wrapper. ⚠️ Windows install historically tricky (use `ta-lib-binary` or prebuilt wheels). |
| **pandas-ta** | https://github.com/aarigs/pandas-ta (now `pandas-ta-classic` fork) | ~5k+ | **130+ indicators**, easy Pandas extension. ⚠️ Original repo went private/paid in 2025 — use `xgboosted/pandas-ta-classic` (224 indicators, 62 candlestick patterns). |
| **ta** (bukosabino) | https://github.com/bukosabino/ta | ~4.7k+ | Clean Pandas/NumPy TA library; feature-engineering oriented. |
| **stockstats** | (awesome-quant listed) | — | Drop-in Pandas replacement for trading stats/indicators. |
| **tulipy** | — | — | C-based, fast, Python bindings. |

**Recommendation:** Install **TA-Lib** (with prebuilt Windows wheel from `ta-lib.org`) as the primary, supplemented by **pandas-ta-classic** for convenience. For options, TA matters less than Greeks/IV (see next section).

---

## 8. Options Strategy & Greeks Calculation Libraries

### mibian
| Field | Detail |
|-------|--------|
| **URL** | https://pypi.org/project/mibian/ |
| **What it does** | Black-Scholes option pricing + **Greeks (delta, gamma, theta, vega, rho)** + implied volatility. The de-facto standard for Indian retail options Greeks. |
| **Integration** | Used by OpenAlgo and marketcalls.in tutorials for NSE option Greeks computation. |
| **Why it's good** | Simple, lightweight, widely used in Indian tutorials. |

### CarloLepelaars/blackscholes
| Field | Detail |
|-------|--------|
| **URL** | https://github.com/CarloLepelaars/blackscholes |
| **What it does** | Black-Scholes calculator with **up to third-order Greeks**. Supports Black-Scholes-Merton and Black-76 models + option structures. |
| **Why it's good** | More advanced than mibian (third-order Greeks); pure Python/NumPy. |

### greeks-package (PyPI)
| Field | Detail |
|-------|--------|
| **URL** | https://pypi.org/project/greeks-package/ |
| **What it does** | Comprehensive first-, second-, **and third-order Greeks** for European options using pure NumPy/SciPy. |
| **Why it's good** | Academic-grade Greeks; no C dependency. |

### QuantLib
| Field | Detail |
|-------|--------|
| **URL** | https://www.quantlib.org / `pip install QuantLib` |
| **What it does** | Comprehensive C++ quantitative finance library (Python bindings): option pricing, Greeks, yield curves, vol surfaces, exotic options. |
| **Why it's good** | Industry-standard; most complete options pricing toolkit. |
| **Limitations** | Steep learning curve; C++ SWIG bindings can be finicky on Windows. |

### vollib
| Field | Detail |
|-------|--------|
| **URL** | https://vollib.org |
| **What it does** | Option pricing, implied volatility, Greek calculation. |
| **Status** | Older; less maintained. |

### Prof. Jayanth R. Varma's option combos package
| Field | Detail |
|-------|--------|
| **URL** | https://www.jrvarma.in/software.html |
| **What it does** | Black-Scholes values and Greeks for options **and option combos** (straddles, strangles, spreads). Python. |
| **Why it's good** | From IIM Ahmedabad professor; combo-level Greeks directly. |

### Options strategy reference implementations
- **codearmo.com tutorial**: Plot straddles, butterflies, iron condors payoffs in Python (Pandas + Matplotlib).
- **ldt9/PyOptionTrader**: Option strategies for Interactive Brokers including Iron Condor and Short Straddle.
- **lambdaclass/options_portfolio_backtester**: Options portfolio backtester with strategy sweeps and tail-risk hedge analysis.
- **Alpaca Level 3 options API** (2025): Multi-leg options (straddle, iron condor) via API — not India but good reference.

---

## 9. Real-Time Data Feed Options

### For Indian Markets (NSE/BSE/MCX)

| Source | Type | Cost | Latency | Notes |
|--------|------|------|---------|-------|
| **Zerodha Kite Connect (KiteTicker WebSocket)** | Official broker API | ₹500/mo (₹2,000/mo post-SEBI Aug 2025) | Tick-level (real-time) | **Best for user.** Full suite: REST + WebSocket + historical candles. pioneered developer APIs in India. |
| **Kite Connect historical data** | REST API | Included | EOD/intraday | Up to 60 days intraday, 2000-day daily. Sufficient for 6+ month backtests. |
| **NSE website (via nsepython)** | Web scraping | Free | ~3-30s polling | Option chain, India VIX. Fragile; not for execution. |
| **NSE Bhavcopy** | EOD files | Free | EOD | Free historical; useful for backtest data sourcing. |
| **Dhan API** | Broker API | Free (with account) | Real-time | Alternative to Zerodha; OpenAlgo supports it. |
| **Global Datafeeds** | Commercial | Paid | Tick-level | Professional Indian market data; MCX (Gold, Natural Gas) supported. |
| **GDFL / Truedata** | Commercial | Paid | Tick | Low-latency feeds for serious algo. |

### For Forex (MT5)

| Source | Type | Cost | Notes |
|--------|------|------|-------|
| **MT5 terminal tick data** | Broker-provided | Free (with broker account) | Real-time + historical via `MetaTrader5` Python package. **Best for user.** |
| **MetaApi** | Cloud | Free tier + paid | Cloud MT5 data without local terminal. |

### For MCX Commodities (Gold, Natural Gas)
- **Zerodha Kite** offers MCX (Gold, Silver, Crude, Natural Gas) — same KiteTicker WebSocket.
- **Global Datafeeds** for dedicated low-latency MCX data.
- For backtesting MCX, Kite historical API covers commodity futures.

---

## 10. Curated "Awesome" Lists Worth Bookmarking

| List | URL | Value |
|------|-----|-------|
| **wilsonfreitas/awesome-quant** | https://github.com/wilsonfreitas/awesome-quant | The canonical curated list of quant libraries — numerical, data, backtesting, TA, risk, etc. |
| **leoncuhk/awesome-quant-ai** | https://github.com/leoncuhk/awesome-quant-ai | AI/ML-focused quant resources. |
| **grananqvist/Awesome-Quant-Machine-Learning-Trading** | https://github.com/grananqvist/Awesome-Quant-Machine-Learning-Trading | ML trading projects incl. QTradeX, marketneutral pairs trading. |
| **merovinh/best-of-algorithmic-trading** | https://github.com/merovinh/best-of-algorithmic-trading | 43 ranked open-source projects across 7 categories. |
| **wangzhe3224/awesome-systematic-trading** | https://github.com/wangzhe3224/awesome-systematic-trading | Systematic trading resources incl. Freqtrade. |
| **botcrypto-io/awesome-crypto-trading-bots** | https://github.com/botcrypto-io/awesome-crypto-trading-bots | Crypto bot ecosystem. |
| **Reddit r/IndianQuants "Best GitHub Repositories for Indian Quants"** | https://www.reddit.com/r/IndianQuants/comments/1ifqg2k/ | Community-curated India-specific list (Fenix, uniBroker, etc.). |

---

## 11. Commercial Open-Source Alternatives to AlgoBulls / IntelligenceTrade

The user asked about open-source alternatives to **AlgoBulls**, **IntelligenceTrade**, and **Trade-Vibes** (proprietary Indian algo platforms):

| Proprietary Platform | Best Open-Source Alternative |
|----------------------|------------------------------|
| **AlgoBulls** (paid strategy marketplace) | **OpenAlgo** (self-hosted, free, 35+ brokers) + **buzzsubash/algo_trading_strategies_india** (free strategy recipes) |
| **IntelligenceTrade / Streak** (Zerodha's backtest-on-charts) | **Backtrader** + `openalgo-backtrader` store; or **VectorBT** for speed |
| **AlgoTest.in** (no-code India backtest/paper/live) | **OpenAlgo** (full-stack) + **AlgoTest free tier** (freemium, no-code options backtest — worth using alongside OSS) |
| **Sensibull** (options analytics) | **nsepython** (option chain) + **mibian/blackscholes** (Greeks) + custom payoff plots |

> **Note on AlgoTest.in:** While commercial, it has a **free options backtesting tier** for NIFTY/BANKNIFTY with leg-wise SL, auto lock-profit, AI reports (Max DD, Success Rate). Worth using alongside OSS for quick validation — it's the closest "no-code" India options backtester and free for basic use.

---

## 12. Common Pitfalls in Retail Algo Trading in India

### ⚠️ Regulatory (SEBI) — CRITICAL, RAPIDLY CHANGING

1. **SEBI's August 2025 retail algo framework** mandates:
   - Every algo used by a retail investor must be **approved/registered** with a unique algo ID at the exchange.
   - All orders must go through a **SEBI-registered broker's approved API** (no open/unregulated APIs).
   - **Static IP whitelist** required by brokers (Zerodha, Angel One, Alice Blue, Finvasia all require IP whitelisting before API order placement). Use a VPS with static IP (e.g., staticip.in providers, AWS, GCP).
   - **Order rate limits** enforced (varies by broker; Zerodha ~3 orders/sec historically, tightening).
   - **Kill switch** mandatory.
   - Compliance deadlines: phased through **April–May 2026**; higher API tiers cost ~₹2,000/month.
2. **April 2026 SEBI changes**: Static IPs mandatory, strategy registration enforced, broker-approved APIs only. Plan for compliance overhead.

### ⚠️ Technical Pitfalls

3. **Kite Connect API rate limits**: 3 orders/sec, 200 orders/min historically (verify current). Straddle/strangle adjustments (4-leg modifications) can hit limits during volatility spikes.
4. **WebSocket reliability**: KiteTicker can deliver stale/wrong tick data (documented Reddit cases of wrong NIFTY spot price May 2026). Always cross-check via REST `kite.ltp()`.
5. **Token expiry**: Kite access tokens expire daily at 7:30 AM IST — automate re-login flow.
6. **Instrument token mapping**: NIFTY weekly options change tokens every Thursday expiry — must dynamically fetch fresh instrument list daily.
7. **Margin requirements**: Short straddle/strangle need ~₹1L+ per lot (NIFTY), ~₹2L+ (BANKNIFTY). SEBI margins changed post-Aug 2025 (peak margin rules). Iron condor reduces margin ~80% vs. naked strangle — prefer defined-risk strategies.
8. **Slippage in backtests**: Options illiquidity (especially OTM strikes) causes real fills far worse than backtest assumes. Use realistic spread/slippage assumptions.
9. **Survivorship bias in option data**: Past expired contracts must be fetched correctly; Kite historical has limited expired-contract depth.
10. **Windows-specific issues**: TA-Lib C-extension build issues on Windows (use prebuilt wheels); MT5 terminal must run as background process; antivirus may block broker API calls.

### ⚠️ Strategy Pitfalls

11. **Straddle/strangle theta decay vs. gap risk**: Short straddle profits most in last week but gamma explosion on expiry day can wipe weeks of gains. Backtest must include expiry-day behavior.
12. **Black-Scholes assumes European exercise** — Indian index options are European (OK), but stock options were American until 2024 (now European). Verify underlying.
13. **India VIX ≠ implied vol of your strike**: Use strike-specific IV from option chain, not India VIX, for Greeks.
14. **Overfitting**: Easy to curve-fit straddle parameters to historical regime. Use walk-forward / out-of-sample testing (VectorBT's strength).
15. **No guaranteed fill in fast markets**: Limit orders on options during crashes may not fill; market orders suffer huge slippage. Use limit + trigger logic.

---

## 13. Final Recommendations & Suggested Architecture

### Tier 1 — Immediate Setup (covers all user requirements)

```
┌─────────────────────────────────────────────────────────┐
│  STRATEGY LAYER                                         │
│  • Backtrader (event-driven, readable) +                │
│    openalgo-backtrader store (Zerodha execution)        │
│  • VectorBT (fast parameter sweeps on straddle payoffs) │
├─────────────────────────────────────────────────────────┤
│  OPTIONS/GREEKS LAYER                                   │
│  • mibian + CarloLepelaars/blackscholes (Greeks)        │
│  • nsepython (option chain, India VIX)                  │
├─────────────────────────────────────────────────────────┤
│  EXECUTION LAYER                                        │
│  • OpenAlgo (unified API: Zerodha + 34 Indian brokers)  │
│  • zerodha/pykiteconnect (low-level Zerodha)            │
│  • MetaTrader5 Python package (forex via MT5)           │
├─────────────────────────────────────────────────────────┤
│  DATA LAYER                                             │
│  • KiteTicker WebSocket (NSE/BSE/MCX real-time)         │
│  • Kite historical API (6+ month backtests)             │
│  • MT5 terminal ticks (forex)                           │
├─────────────────────────────────────────────────────────┤
│  ANALYSIS LAYER                                         │
│  • TA-Lib + pandas-ta-classic (indicators)              │
│  •buzzsubash/algo_trading_strategies_india (recipes)    │
└─────────────────────────────────────────────────────────┘
```

### Tier 2 — Production-Grade Upgrade (if scaling)

Replace Tier 1 strategy layer with **NautilusTrader** (Rust-native, deterministic backtest→live parity, multi-asset). Write a custom OpenAlgo adapter or use Interactive Brokers India for unified Indian + global access.

### Tier 3 — Institutional-Grade

**QuantConnect LEAN** (C#/Python) with IB India — full options support, cloud backtesting with curated data, 20+ brokers. Trade-off: heavier setup, Python is second-class.

### Concrete Next Actions

1. **Week 1**: Install OpenAlgo on Windows (Docker or native), connect Zerodha Kite, run the built-in intraday rolling straddle sample strategy in paper mode.
2. **Week 2**: Install `pykiteconnect`, `nsepython`, `mibian`, `Backtrader` + `openalgo-backtrader`. Backtest a BANKNIFTY short straddle on 6 months of Kite historical data.
3. **Week 3**: Install `MetaTrader5` Python package + MT5 terminal (demo forex account). Validate tick data fetch and order placement.
4. **Week 4**: Install VectorBT; run parameter sweeps on straddle entry/exit thresholds. Add iron-condor variant for defined-risk comparison.
5. **Week 5**: Set up static-IP VPS (SEBI compliance), register strategy for unique algo ID with broker, migrate paper → small-capital live.
6. **Ongoing**: Monitor SEBI regulation updates (deadlines rolling through 2026); subscribe to marketcalls.in/blog.openalgo.in for OpenAlgo updates.

### Compliance Checklist Before Going Live

- [ ] SEBI-registered broker with approved API
- [ ] Static IP (VPS or static ISP) whitelisted with broker
- [ ] Strategy registered with unique algo ID at exchange
- [ ] Kill switch implemented (OpenAlgo has this)
- [ ] Order rate limits respected (≤3/sec typical)
- [ ] Access-token auto-refresh before 7:30 AM IST daily expiry
- [ ] Daily instrument-list refresh (especially expiry days)
- [ ] Realistic slippage/margin in backtests
- [ ] Out-of-sample / walk-forward validation
- [ ] Start with paper trading → small capital → scale

---

## Appendix: Quick-Reference Star/Activity Table

| Repo | Stars | Activity | Windows | Zerodha | MT5 | Options | Backtest |
|------|-------|----------|---------|---------|-----|---------|----------|
| OpenAlgo | ~3.5k | 🔥🔥🔥 | ✅ | ✅ (35+ brokers) | ❌ | ✅ (analytics) | ❌ (pair w/ Backtrader) |
| pykiteconnect | ~1.1k | 🔥🔥 | ✅ | ✅ | ❌ | ✅ (API) | ❌ |
| buzzsubash/algo_strategies_india | ~300-500 | 🔥🔥 | ✅ | ✅ | ❌ | ✅✅ (straddle/strangle) | ✅ (in-strategy) |
| NautilusTrader | ~3.5k | 🔥🔥🔥 | ✅ (improving) | ❌ (needs adapter) | ❌ | ✅ | ✅✅✅ |
| Freqtrade | ~40k | 🔥🔥🔥 | ✅ | ❌ | ❌ | ❌ | ✅✅ |
| VectorBT | ~4.5k | 🔥🔥 | ✅ | (data-agnostic) | (data-agnostic) | ⚠️ | ✅✅✅ |
| Backtrader | ~22.9k | 🔥 (community) | ✅ | ✅ (stores) | ❌ | ✅ (community) | ✅✅ |
| Jesse | ~8.4k | 🔥🔥 | ✅ | ❌ | ❌ | ❌ | ✅✅ |
| QuantConnect LEAN | ~9.5k | 🔥🔥🔥 | ✅ | ❌ (IB India) | ❌ | ✅✅ | ✅✅✅ |
| StockSharp | ~7k | 🔥🔥 | ✅ (.NET native) | ⚠️ (custom) | ✅ (bridge) | ✅ | ✅✅ |
| MetaTrader5 (PyPI) | official | 🔥🔥 | ✅✅ (native) | ❌ | ✅✅ | ❌ | ⚠️ (MT5 Tester) |
| nsepython | ~600 | 🔥 | ✅ | (data source) | ❌ | ✅ (chain/Greeks) | ❌ |
| aaryansinha16/AI-trader | growing | 🔥🔥 | ✅ | ✅ (NSE) | ❌ | ✅✅ | ✅✅ (tick replay) |

Legend: ✅✅✅ = excellent | ✅✅ = good | ✅ = supported | ⚠️ = partial/limited | ❌ = not supported

---

*Report compiled from 44 web searches across GitHub topics, Reddit communities (r/IndianQuants, r/IndiaAlgoTrading, r/algotrading), Medium, Kite Connect forum, and official documentation. Star counts are approximate as of August 2026 and grow continuously — verify on GitHub before committing. All recommendations favor the user's constraints: Windows, Python, Zerodha Kite, MT5 forex, options straddle/strangle, backtesting.*
