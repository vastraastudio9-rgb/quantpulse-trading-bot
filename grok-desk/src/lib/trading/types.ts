export type TradeMode = "PAPER" | "LIVE";

export type PositionKind = "LONG_UNDERLYING" | "SHORT_UNDERLYING" | "SHORT_PREMIUM" | "LONG_PREMIUM";

export interface Instrument {
  symbol: string;
  name: string;
  exchange: string;
  segment: string;
  assetClass: string;
  lotSize: number;
  tickSize: number;
  basePrice: number;
  volatility: number;
  expiryDay: string | null;
}

export interface Quote {
  symbol: string;
  name: string;
  exchange: string;
  ltp: number;
  dayOpen: number;
  dayHigh: number;
  dayLow: number;
  dayChange: number;
  dayChangePct: number;
  isMarketOpen: boolean;
  sparkline: number[];
  timestamp: string;
  lotSize: number;
  volatility: number;
}

export interface StrategyMeta {
  key: string;
  name: string;
  type: string;
  description: string;
  direction: string;
  edgeSource: string;
  typicalWinRate: string;
  bestMarket: string;
  entryTime: string;
  exitTime: string;
}

export interface SignalLeg {
  action: "BUY" | "SELL";
  type: string;
  strike: number;
  premium: number;
  delta?: number;
  theta?: number;
  vega?: number;
  qty?: number;
}

export interface TradingSignal {
  signalId: string;
  strategyKey: string;
  strategyName: string;
  strategyType: string;
  symbol: string;
  exchange: string;
  spotPrice: number;
  timestamp: string;
  confidence: number;
  direction: string;
  legs: SignalLeg[];
  entryPrice: number;
  stopLoss: number;
  target: number;
  maxProfit?: string | number;
  maxLoss?: string | number;
  breakevenUpper?: number;
  breakevenLower?: number;
  rationale: string;
  status: "ACTIVE" | "TRIGGERED" | "FILLED";
}

export interface Position {
  id: string;
  mode: TradeMode;
  kind: PositionKind;
  instrument: string;
  exchange: string;
  strategy: string;
  strategyKey: string;
  side: "LONG" | "SHORT";
  quantity: number;
  lotSize: number;
  lots: number;
  avgPrice: number;
  entrySpot: number;
  ltp: number;
  stopLoss: number;
  target: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  openedAt: string;
  status: "OPEN";
  broker?: string;
  signalId?: string;
  legs: SignalLeg[];
}

export interface ClosedTrade {
  id: string;
  mode: TradeMode;
  instrument: string;
  exchange: string;
  strategy: string;
  side: "LONG" | "SHORT";
  quantity: number;
  lots: number;
  avgPrice: number;
  exitPrice: number;
  pnl: number;
  pnlPct: number;
  openedAt: string;
  closedAt: string;
  reason: "MANUAL" | "TP_HIT" | "SL_HIT" | "KILL" | "DAY_END" | "REGIME" | "TIME";
  broker?: string;
}

export interface DeskOrder {
  id: string;
  mode: TradeMode;
  signalId: string;
  instrument: string;
  strategy: string;
  side: "BUY" | "SELL";
  quantity: number;
  lots: number;
  price: number;
  status: "FILLED" | "REJECTED" | "ROUTED";
  broker?: string;
  brokerOrderId?: string;
  createdAt: string;
  note?: string;
}

export interface DeskAlert {
  id: string;
  at: string;
  kind: "SIGNAL" | "FILL" | "CLOSE" | "RISK" | "TELEGRAM" | "BROKER";
  title: string;
  body: string;
  mode?: TradeMode;
  read: boolean;
}

export interface TelegramConfig {
  botToken: string;
  chatId: string;
  enabled: boolean;
  sendSignals: boolean;
  sendFills: boolean;
  sendCloses: boolean;
  sendCycles: boolean;
}

export interface BookSnapshot {
  mode: TradeMode;
  capital: number;
  realizedPnl: number;
  unrealizedPnl: number;
  equity: number;
  openCount: number;
  winCount: number;
  lossCount: number;
  winRate: number;
  todayPnl: number;
}

export interface BacktestMetrics {
  initialCapital: number;
  finalCapital: number;
  totalReturnPct: number;
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  maxDrawdownPct: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  expectancy: number;
  grossProfit: number;
  grossLoss: number;
}

export interface BacktestTrade {
  entryTime: string;
  exitTime: string;
  side: "BUY" | "SELL";
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  pnlPct: number;
  exitReason: "TP_HIT" | "SL_HIT" | "TIME_EXIT";
}

export interface BacktestResult {
  status: "COMPLETED" | "FAILED";
  strategyKey: string;
  symbol: string;
  timeframe: string;
  days: number;
  barsProcessed: number;
  metrics: BacktestMetrics;
  equityCurve: { date: string; value: number }[];
  monthlyReturns: { year: number; month: number; monthName: string; returnPct: number }[];
  trades: BacktestTrade[];
  tradesCountTotal: number;
  startedAt: string;
  error?: string;
}

export interface DashboardData {
  stats: {
    todayPnl: number;
    todayPnlPct: number;
    realizedPnl: number;
    unrealizedPnl: number;
    openPositions: number;
    activeSignals: number;
    winRate30d: number;
    totalTrades30d: number;
    capitalUsed: number;
    capitalAvailable: number;
  };
  quotes: Quote[];
  equityCurve: { date: string; value: number }[];
  signals: TradingSignal[];
  positions: Position[];
  timestamp: string;
}

export interface BrokerStatus {
  id: string;
  name: string;
  type: string;
  isConfigured: boolean;
  isConnected: boolean;
  packageInstalled: boolean;
  paperMode: boolean;
  segments: string[];
  lastSync: string | null;
  message: string;
  user?: string;
  balance?: number;
  currency?: string;
}

export interface ResearchRepo {
  name: string;
  url: string;
  stars: string;
  lang: string;
  license: string;
  description: string;
  bestFor: string;
  rating: number;
}

export interface BacktestParams {
  strategyKey?: string;
  symbol?: string;
  days?: number;
  timeframe?: string;
  initialCapital?: number;
  lotSize?: number;
  slPct?: number;
  tpPct?: number;
}

export interface RegimeSnapshot {
  symbol: string;
  trendRegime: string;
  volatilityRegime: string;
  rangeRegime: string;
  liquidityRegime: string;
  riskRegime: string;
  compositeRegime: string;
  confidence: number;
  metrics: {
    adx: number;
    atrPct: number;
    bollingerWidthPct: number;
    hurst: number;
    rsi: number;
    volumeTrendPct: number;
  };
  recommendedStrategies: string[];
  avoidStrategies: string[];
  shouldTrade: boolean;
  reason: string;
}

export interface LeaderboardEntry {
  rank: number;
  strategyKey: string;
  strategyName: string;
  type: string;
  sharpe: number;
  totalReturnPct: number;
  winRate: number;
  profitFactor: number;
  maxDrawdownPct: number;
  totalTrades: number;
  expectancy: number;
  typicalWinRate: string;
}

export interface ValidationResult {
  strategyKey: string;
  symbol: string;
  validatedAt: string;
  finalVerdict: string;
  inSampleMetrics: BacktestMetrics;
  oosSplit: { trainBars: number; testBars: number; splitDate: string };
  walkForward: { nWindows: number; trainWindowBars: number; testWindowBars: number; stepBars: number };
  monteCarlo: {
    status: string;
    nRuns: number;
    probabilityOfProfit: number;
    probabilityOfRuin20pct: number;
    sharpe: { p5: number; p50: number };
    finalCapital: { p5: number; p50: number };
    maxDrawdownPct: { p50: number; p95: number };
  };
  regimePerformance: Record<string, { trades: number; winRate: number; totalPnl: number }>;
  redTeam: {
    verdict: string;
    checks: { name: string; passed: boolean; evidence: string; severity: "HIGH" | "MED" }[];
  };
  promotionPath: Record<string, string>;
}

export type JarvisLogKind = "CYCLE" | "FILL" | "SKIP" | "RISK" | "AI" | "HOLD" | "EXIT";

export interface JarvisLogEntry {
  id: string;
  at: string;
  kind: JarvisLogKind;
  text: string;
}
