/**
 * Trading Engine API Client
 * Calls use same-origin paths. Caddy routes API paths to the Python engine.
 */

function apiUrl(path: string): string {
  return path;
}

export interface Quote {
  symbol: string;
  name: string;
  ltp: number;
  day_open: number;
  day_high: number;
  day_low: number;
  day_change: number;
  day_change_pct: number;
  is_market_open: boolean;
  sparkline: number[];
  timestamp: string;
  lot_size: number;
  volatility: number;
  exchange: string;
}

export interface Instrument {
  symbol: string;
  name: string;
  exchange: string;
  segment: string;
  asset_class: string;
  lot_size: number;
  tick_size: number;
  base_price: number;
  volatility: number;
  expiry_day: string | null;
}

export interface StrategyMeta {
  key: string;
  name: string;
  type: string;
  description: string;
  direction: string;
  edge_source: string;
  typical_win_rate: string;
  best_market: string;
  entry_time: string;
  exit_time: string;
}

export interface SignalLeg {
  action: string;
  type: string;
  strike: number;
  premium: number;
  delta?: number;
  theta?: number;
  vega?: number;
}

export interface TradingSignal {
  signal_id: string;
  strategy_key: string;
  strategy_name: string;
  strategy_type: string;
  symbol: string;
  exchange: string;
  spot_price: number;
  timestamp: string;
  confidence: number;
  direction: string;
  legs: SignalLeg[];
  entry_price: number;
  stop_loss: number;
  target: number;
  max_profit?: string | number;
  max_loss?: string | number;
  breakeven_upper?: number;
  breakeven_lower?: number;
  rationale: string;
  status?: string;
  data_source?: string;
  evidence_grade?: string;
  execution_eligible?: boolean;
  paper_execution_eligible?: boolean;
  execution_scope?: "REAL_MARKET" | "PAPER_RND" | "PAPER_MANUAL";
  paper_status?: "DETECTED" | "POSITION_OPENED" | "RISK_BLOCKED" | "MANUAL_GENERATED";
  paper_outcome?: { position_id?: string; reason?: string };
  notification?: { sent?: boolean; error?: string };
  validation_errors?: string[];
}

export interface Position {
  id: string;
  instrument: string;
  exchange: string;
  strategy: string;
  side: string;
  quantity: number;
  lot_size: number;
  lots: number;
  avg_price: number;
  ltp: number;
  stop_loss: number;
  target: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  opened_at: string;
  status: string;
}

export interface BacktestMetrics {
  initial_capital: number;
  final_capital: number;
  total_return_pct: number;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  max_drawdown_pct: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  expectancy: number;
  gross_profit: number;
  gross_loss: number;
}

export interface BacktestResult {
  status: string;
  strategy_key: string;
  symbol: string;
  timeframe: string;
  days: number;
  bars_processed: number;
  metrics: BacktestMetrics;
  equity_curve: { date: string; value: number }[];
  monthly_returns: { year: number; month: number; month_name: string; return_pct: number }[];
  trades: any[];
  trades_count_total: number;
  started_at: string;
  error?: string;
}

export interface DashboardData {
  stats: {
    today_pnl: number;
    today_pnl_pct: number;
    realized_pnl: number;
    unrealized_pnl: number;
    open_positions: number;
    active_signals: number;
    win_rate_30d: number;
    total_trades_30d: number;
    capital_used: number;
    capital_available: number;
  };
  quotes: {
    symbol: string;
    name: string;
    ltp: number;
    day_change_pct: number;
    day_change: number;
    is_market_open: boolean;
    sparkline: number[];
    exchange: string;
  }[];
  equity_curve: { date: string; value: number }[];
  signals: TradingSignal[];
  signals_are_actionable: boolean;
  research_policy: ResearchPolicy;
  positions: Position[];
  timestamp: string;
}

export interface ResearchPolicy {
  mode: string;
  paper_only: boolean;
  data_source: string;
  evidence_grade: string;
  live_eligible: boolean;
  live_execution_enabled: boolean;
  research_active: boolean;
  paper_trading_active: boolean;
  approved_count: number;
  generated_at?: string | null;
}

export interface BrokerStatus {
  id: string;
  name: string;
  type: string;
  is_configured: boolean;
  is_connected: boolean;
  package_installed: boolean;
  paper_mode: boolean;
  segments: string[];
  last_sync: string | null;
  message: string;
  user?: string;
  balance?: number;
  currency?: string;
}

export interface BrokersStatusResponse {
  brokers: BrokerStatus[];
  telegram: {
    is_configured: boolean;
    message: string;
  };
}

export interface TradingModeStatus {
  mode: "PAPER" | "LIVE";
  broker: string;
  live_allowed: boolean;
  autonomous_live_allowed: boolean;
}

export interface ResearchRepo {
  name: string;
  url: string;
  stars: string;
  lang: string;
  license: string;
  description: string;
  best_for: string;
  rating: number;
}

export interface BacktestParams {
  strategy_key?: string;
  symbol?: string;
  days?: number;
  timeframe?: string;
  initial_capital?: number;
  lot_size?: number;
  sl_pct?: number;
  tp_pct?: number;
  max_positions?: number;
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${res.status}: ${err}`);
  }
  return res.json();
}

export const tradingApi = {
  health: () => fetchJson<{ status: string }>(apiUrl("/health")),

  getInstruments: () => fetchJson<Instrument[]>(apiUrl("/api/instruments")),

  getQuote: (symbol: string) =>
    fetchJson<Quote>(apiUrl(`/api/quote/${symbol}`)),

  getOptionChain: (symbol: string, n = 11) =>
    fetchJson<any>(apiUrl(`/api/option-chain/${symbol}?n_strikes=${n}`)),

  getStrategies: () => fetchJson<StrategyMeta[]>(apiUrl("/api/strategies")),

  getSignals: (limit = 12) =>
    fetchJson<TradingSignal[]>(apiUrl(`/api/signals?limit=${limit}`)),

  generateSignal: (strategy_key: string, symbol: string) =>
    fetchJson<TradingSignal>(apiUrl("/api/signals/generate"), {
      method: "POST",
      body: JSON.stringify({ strategy_key, symbol }),
    }),

  getPositions: () => fetchJson<Position[]>(apiUrl("/api/positions")),

  runBacktest: (params: BacktestParams) =>
    fetchJson<BacktestResult>(apiUrl("/api/backtest"), {
      method: "POST",
      body: JSON.stringify(params),
    }),

  getDashboard: () => fetchJson<DashboardData>(apiUrl("/api/dashboard")),

  getResearchPolicy: () =>
    fetchJson<ResearchPolicy>(apiUrl("/api/jarvis/research-policy")),

  getBrokersStatus: () =>
    fetchJson<BrokersStatusResponse>(apiUrl("/api/brokers/status")),

  getTradingMode: () =>
    fetchJson<TradingModeStatus>(apiUrl("/api/trading/mode")),

  setTradingMode: (mode: "PAPER" | "LIVE", broker = "", confirmation = "") =>
    fetchJson<TradingModeStatus>(apiUrl("/api/trading/mode"), {
      method: "POST",
      body: JSON.stringify({ mode, broker, confirmation }),
    }),

  getResearch: () =>
    fetchJson<{
      repos: ResearchRepo[];
      recommended_stack: Record<string, string>;
      key_insights: string[];
    }>(apiUrl("/api/research")),
};
