"use client";

import { useState, useEffect } from "react";
import { Play, Loader2, TrendingUp, TrendingDown, Activity, Target, Percent, DollarSign } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { tradingApi, type BacktestResult, type StrategyMeta, type Instrument } from "@/lib/trading-api";
import { EquityChart } from "./charts";
import { cn } from "@/lib/utils";

export function BacktestView() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [strategy, setStrategy] = useState("STRADDLE_SELL");
  const [symbol, setSymbol] = useState("NIFTY");
  const [days, setDays] = useState(180);
  const [timeframe, setTimeframe] = useState("1d");
  const [capital, setCapital] = useState(100000);
  const [lotSize, setLotSize] = useState(1);
  const [slPct, setSlPct] = useState(25);
  const [tpPct, setTpPct] = useState(50);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const { toast } = useToast();

  // Load options on mount
  useEffect(() => {
    (async () => {
      try {
        const [s, i] = await Promise.all([tradingApi.getStrategies(), tradingApi.getInstruments()]);
        setStrategies(s);
        setInstruments(i);
      } catch (e: any) {
        toast({ title: "Failed to load options", description: e.message, variant: "destructive" });
      }
    })();
  }, [toast]);

  const runBacktest = async () => {
    setLoading(true);
    setResult(null);
    try {
      const r = await tradingApi.runBacktest({
        strategy_key: strategy,
        symbol,
        days,
        timeframe,
        initial_capital: capital,
        lot_size: lotSize,
        sl_pct: slPct,
        tp_pct: tpPct,
      });
      setResult(r);
      if (r.status === "COMPLETED") {
        toast({
          title: "Backtest completed",
          description: `${r.trades_count_total} trades • ${r.metrics.total_return_pct}% return • Sharpe ${r.metrics.sharpe}`,
        });
      } else {
        toast({ title: "Backtest failed", description: r.error || "Unknown error", variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Backtest failed", description: e.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Config panel */}
      <Card className="p-4 lg:col-span-1 space-y-3 h-fit lg:sticky lg:top-20">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-semibold">Backtest Configuration</h3>
          <Badge variant="outline" className="text-[10px]">6 months default</Badge>
        </div>

        <div className="space-y-2">
          <Label className="text-xs">Strategy</Label>
          <Select value={strategy} onValueChange={setStrategy}>
            <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {strategies.map((s) => (
                <SelectItem key={s.key} value={s.key} className="text-xs">
                  <div className="flex flex-col">
                    <span>{s.name}</span>
                    <span className="text-[10px] text-muted-foreground">{s.typical_win_rate}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label className="text-xs">Instrument</Label>
          <Select value={symbol} onValueChange={setSymbol}>
            <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {instruments.map((i) => (
                <SelectItem key={i.symbol} value={i.symbol} className="text-xs">
                  {i.symbol} ({i.exchange})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5">
            <Label className="text-xs">Days</Label>
            <Input type="number" value={days} onChange={(e) => setDays(parseInt(e.target.value) || 180)} className="h-9 text-xs tabular-nums" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Timeframe</Label>
            <Select value={timeframe} onValueChange={setTimeframe}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {["5m", "15m", "1h", "1d"].map((tf) => (
                  <SelectItem key={tf} value={tf} className="text-xs">{tf}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5">
            <Label className="text-xs">Capital (₹)</Label>
            <Input type="number" value={capital} onChange={(e) => setCapital(parseInt(e.target.value) || 100000)} className="h-9 text-xs tabular-nums" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Lots</Label>
            <Input type="number" value={lotSize} onChange={(e) => setLotSize(parseInt(e.target.value) || 1)} className="h-9 text-xs tabular-nums" min={1} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5">
            <Label className="text-xs">SL %</Label>
            <Input type="number" value={slPct} onChange={(e) => setSlPct(parseFloat(e.target.value) || 25)} className="h-9 text-xs tabular-nums" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Target %</Label>
            <Input type="number" value={tpPct} onChange={(e) => setTpPct(parseFloat(e.target.value) || 50)} className="h-9 text-xs tabular-nums" />
          </div>
        </div>

        <Button onClick={runBacktest} disabled={loading} className="w-full h-9">
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              Running...
            </>
          ) : (
            <>
              <Play className="w-4 h-4 mr-1.5" />
              Run Backtest
            </>
          )}
        </Button>

        <div className="text-[10px] text-muted-foreground leading-relaxed pt-2 border-t border-border">
          Backtest uses synthetic GBM-modeled data for {days} days. To use real Zerodha historical data, connect broker in Brokers tab.
        </div>
      </Card>

      {/* Results panel */}
      <div className="lg:col-span-2 space-y-4">
        {!result && !loading && (
          <Card className="p-12 text-center text-muted-foreground">
            <Activity className="w-8 h-8 mx-auto mb-3 opacity-40" />
            <p className="text-sm">Configure parameters and run a backtest to see results.</p>
            <p className="text-xs mt-1 opacity-70">Default: 6 months / NIFTY / Straddle Sell</p>
          </Card>
        )}

        {loading && (
          <Card className="p-12 text-center">
            <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin text-emerald-400" />
            <p className="text-sm">Running backtest on {days} days of {symbol} data...</p>
            <p className="text-xs text-muted-foreground mt-1">Processing {days} bars</p>
          </Card>
        )}

        {result && result.status === "COMPLETED" && <BacktestResults result={result} />}
      </div>
    </div>
  );
}

function BacktestResults({ result }: { result: BacktestResult }) {
  const m = result.metrics;
  const isProfit = m.total_return_pct >= 0;
  const isGoodSharpe = m.sharpe >= 1.0;

  return (
    <>
      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label="Total Return"
          value={`${isProfit ? "+" : ""}${m.total_return_pct}%`}
          subValue={`₹${(m.final_capital - m.initial_capital).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
          icon={isProfit ? TrendingUp : TrendingDown}
          positive={isProfit}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={m.sharpe.toFixed(3)}
          subValue={`Sortino ${m.sortino.toFixed(3)}`}
          icon={Activity}
          positive={isGoodSharpe}
        />
        <MetricCard
          label="Max Drawdown"
          value={`-${m.max_drawdown_pct}%`}
          subValue={`Calmar ${m.calmar.toFixed(3)}`}
          icon={TrendingDown}
          positive={m.max_drawdown_pct < 15}
        />
        <MetricCard
          label="Win Rate"
          value={`${m.win_rate}%`}
          subValue={`${m.wins}W / ${m.losses}L`}
          icon={Target}
          positive={m.win_rate >= 55}
        />
      </div>

      {/* Equity curve */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold">Equity Curve</h3>
            <p className="text-[10px] text-muted-foreground">{result.bars_processed} bars processed • {result.timeframe} timeframe</p>
          </div>
          <Badge variant="outline" className="text-[10px]">
            ₹{m.initial_capital.toLocaleString("en-IN")} → ₹{m.final_capital.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          </Badge>
        </div>
        <EquityChart data={result.equity_curve} height={280} />
      </Card>

      {/* Detailed metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3">Performance Metrics</h3>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <Metric label="Initial Capital" value={`₹${m.initial_capital.toLocaleString("en-IN")}`} />
            <Metric label="Final Capital" value={`₹${m.final_capital.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} />
            <Metric label="Total Trades" value={`${m.total_trades}`} />
            <Metric label="Profit Factor" value={m.profit_factor.toFixed(2)} positive={m.profit_factor >= 1} />
            <Metric label="Avg Win" value={`₹${m.avg_win.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} positive />
            <Metric label="Avg Loss" value={`₹${m.avg_loss.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} negative />
            <Metric label="Gross Profit" value={`₹${m.gross_profit.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} positive />
            <Metric label="Gross Loss" value={`₹${m.gross_loss.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} negative />
            <Metric label="Expectancy" value={`₹${m.expectancy.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`} positive={m.expectancy >= 0} />
            <Metric label="Calmar" value={m.calmar.toFixed(3)} positive={m.calmar >= 1} />
          </div>
        </Card>

        {/* Monthly returns heatmap */}
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3">Monthly Returns</h3>
          {result.monthly_returns.length === 0 ? (
            <div className="text-xs text-muted-foreground">No monthly data</div>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              {result.monthly_returns.map((mr, i) => {
                const isPositive = mr.return_pct >= 0;
                const intensity = Math.min(Math.abs(mr.return_pct) / 5, 1);
                return (
                  <div
                    key={i}
                    className={cn(
                      "p-2 rounded text-center border",
                      isPositive
                        ? "border-emerald-500/30 bg-emerald-500/5"
                        : "border-red-500/30 bg-red-500/5"
                    )}
                    style={{ opacity: 0.5 + intensity * 0.5 }}
                  >
                    <div className="text-[10px] text-muted-foreground">{mr.month_name}</div>
                    <div className={cn("text-xs font-mono tabular-nums font-medium", isPositive ? "text-emerald-400" : "text-red-400")}>
                      {isPositive ? "+" : ""}{mr.return_pct}%
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      {/* Trades table */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Trade History</h3>
          <Badge variant="outline" className="text-[10px]">Last {result.trades.length} of {result.trades_count_total}</Badge>
        </div>
        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card">
              <tr className="text-left text-muted-foreground border-b border-border">
                <th className="py-2 pr-3 font-medium">Entry</th>
                <th className="py-2 pr-3 font-medium">Exit</th>
                <th className="py-2 pr-3 font-medium">Side</th>
                <th className="py-2 pr-3 font-medium text-right">Entry ₹</th>
                <th className="py-2 pr-3 font-medium text-right">Exit ₹</th>
                <th className="py-2 pr-3 font-medium text-right">P&L</th>
                <th className="py-2 pr-3 font-medium text-right">P&L %</th>
                <th className="py-2 font-medium">Exit Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {result.trades.slice().reverse().map((t: any, i: number) => {
                const pnlPos = t.pnl >= 0;
                return (
                  <tr key={i} className="hover:bg-muted/20">
                    <td className="py-1.5 pr-3 text-muted-foreground tabular-nums">
                      {new Date(t.entry_time).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}
                    </td>
                    <td className="py-1.5 pr-3 text-muted-foreground tabular-nums">
                      {new Date(t.exit_time).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}
                    </td>
                    <td className="py-1.5 pr-3">
                      <Badge variant="outline" className={cn("text-[9px] px-1", t.side === "BUY" ? "border-emerald-500/40 text-emerald-400" : "border-red-500/40 text-red-400")}>
                        {t.side}
                      </Badge>
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{t.entry_price}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{t.exit_price}</td>
                    <td className={cn("py-1.5 pr-3 text-right tabular-nums font-medium", pnlPos ? "text-emerald-400" : "text-red-400")}>
                      {pnlPos ? "+" : ""}₹{t.pnl}
                    </td>
                    <td className={cn("py-1.5 pr-3 text-right tabular-nums", pnlPos ? "text-emerald-400" : "text-red-400")}>
                      {pnlPos ? "+" : ""}{t.pnl_pct}%
                    </td>
                    <td className="py-1.5">
                      <Badge variant="outline" className={cn("text-[9px] px-1", t.exit_reason === "TP_HIT" ? "border-emerald-500/40 text-emerald-400" : t.exit_reason === "SL_HIT" ? "border-red-500/40 text-red-400" : "border-amber-500/40 text-amber-400")}>
                        {t.exit_reason.replace("_", " ")}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function MetricCard({
  label, value, subValue, icon: Icon, positive,
}: { label: string; value: string; subValue?: string; icon: any; positive?: boolean }) {
  return (
    <Card className="p-3.5">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</span>
        <Icon className={cn("w-3.5 h-3.5", positive === false ? "text-red-400" : positive === true ? "text-emerald-400" : "text-muted-foreground")} />
      </div>
      <div className={cn("text-lg font-semibold tabular-nums", positive === false ? "text-red-400" : positive === true ? "text-emerald-400" : "")}>
        {value}
      </div>
      {subValue && <div className="text-[10px] text-muted-foreground tabular-nums mt-0.5">{subValue}</div>}
    </Card>
  );
}

function Metric({ label, value, positive, negative }: { label: string; value: string; positive?: boolean; negative?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono tabular-nums font-medium", positive && "text-emerald-400", negative && "text-red-400")}>
        {value}
      </span>
    </div>
  );
}
