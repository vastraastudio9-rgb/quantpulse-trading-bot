"use client";

import { useEffect, useState } from "react";
import { Trophy, Loader2, TrendingUp, TrendingDown, Target, Zap } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { tradingApi, type Instrument } from "@/lib/trading-api";
import { cn } from "@/lib/utils";

interface LeaderboardEntry {
  rank: number;
  strategy_key: string;
  strategy_name: string;
  type: string;
  sharpe: number;
  total_return_pct: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown_pct: number;
  total_trades: number;
  expectancy: number;
  typical_win_rate: string;
}

export function LeaderboardView() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [symbol, setSymbol] = useState("NIFTY");
  const [days, setDays] = useState(90);
  const [rankings, setRankings] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [bestStrategy, setBestStrategy] = useState<LeaderboardEntry | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    (async () => {
      try {
        const insts = await tradingApi.getInstruments();
        setInstruments(insts);
      } catch (e: any) {
        toast({ title: "Failed to load instruments", description: e.message, variant: "destructive" });
      }
    })();
  }, [toast]);

  const loadLeaderboard = async () => {
    setLoading(true);
    try {
      const url = `/api/jarvis/leaderboard?symbol=${symbol}&days=${days}&XTransformPort=3030`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setRankings(d.rankings || []);
      setBestStrategy(d.best_strategy || null);
    } catch (e: any) {
      toast({ title: "Failed to load leaderboard", description: e.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const request = window.setTimeout(() => void loadLeaderboard(), 0);
    return () => window.clearTimeout(request);
  }, [symbol, days]);

  return (
    <div className="space-y-4">
      {/* Config */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Instrument</Label>
            <Select value={symbol} onValueChange={setSymbol}>
              <SelectTrigger className="w-[160px] h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {instruments.map((i) => (
                  <SelectItem key={i.symbol} value={i.symbol} className="text-xs">
                    {i.symbol} ({i.exchange})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Days</Label>
            <Select value={String(days)} onValueChange={(v) => setDays(parseInt(v))}>
              <SelectTrigger className="w-[100px] h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[60, 90, 180].map((d) => (
                  <SelectItem key={d} value={String(d)} className="text-xs">{d}d</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={loadLeaderboard} disabled={loading} size="sm" className="h-9">
            {loading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Trophy className="w-4 h-4 mr-1" />}
            Refresh
          </Button>
          {bestStrategy && (
            <div className="ml-auto flex items-center gap-2 text-xs">
              <Trophy className="w-4 h-4 text-amber-400" />
              <span className="text-muted-foreground">Best:</span>
              <span className="font-semibold text-amber-400">{bestStrategy.strategy_name}</span>
              <Badge variant="outline" className="text-[10px]">Sharpe {bestStrategy.sharpe}</Badge>
            </div>
          )}
        </div>
      </Card>

      {/* Leaderboard table */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Trophy className="w-4 h-4 text-amber-400" />
          Strategy Leaderboard — {symbol} ({days}d)
        </h3>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
            <span className="ml-2 text-xs text-muted-foreground">Running backtests for all strategies...</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="pb-2 pr-2 font-medium">Rank</th>
                  <th className="pb-2 pr-2 font-medium">Strategy</th>
                  <th className="pb-2 pr-2 font-medium text-right">Sharpe</th>
                  <th className="pb-2 pr-2 font-medium text-right">Return %</th>
                  <th className="pb-2 pr-2 font-medium text-right">Win Rate</th>
                  <th className="pb-2 pr-2 font-medium text-right">Profit Factor</th>
                  <th className="pb-2 pr-2 font-medium text-right">Max DD %</th>
                  <th className="pb-2 pr-2 font-medium text-right">Trades</th>
                  <th className="pb-2 pr-2 font-medium text-right">Expectancy</th>
                  <th className="pb-2 font-medium">Typical WR</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rankings.map((r) => (
                  <tr key={r.strategy_key} className={cn("hover:bg-muted/20", r.rank === 1 && "bg-amber-500/5")}>
                    <td className="py-2 pr-2">
                      {r.rank <= 3 ? (
                        <span className={cn(
                          "font-bold text-sm",
                          r.rank === 1 ? "text-amber-400" : r.rank === 2 ? "text-zinc-400" : "text-orange-600"
                        )}>
                          {r.rank === 1 ? "🥇" : r.rank === 2 ? "🥈" : "🥉"}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">#{r.rank}</span>
                      )}
                    </td>
                    <td className="py-2 pr-2">
                      <div className="font-medium">{r.strategy_name}</div>
                      <div className="text-[10px] text-muted-foreground">{r.type}</div>
                    </td>
                    <td className={cn("py-2 pr-2 text-right tabular-nums font-medium",
                      r.sharpe >= 1 ? "text-emerald-400" : r.sharpe >= 0 ? "text-amber-400" : "text-red-400")}>
                      {r.sharpe}
                    </td>
                    <td className={cn("py-2 pr-2 text-right tabular-nums",
                      r.total_return_pct >= 0 ? "text-emerald-400" : "text-red-400")}>
                      {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct}%
                    </td>
                    <td className="py-2 pr-2 text-right tabular-nums">{r.win_rate}%</td>
                    <td className={cn("py-2 pr-2 text-right tabular-nums",
                      r.profit_factor >= 1.5 ? "text-emerald-400" : r.profit_factor >= 1 ? "text-amber-400" : "text-red-400")}>
                      {r.profit_factor}
                    </td>
                    <td className="py-2 pr-2 text-right tabular-nums text-red-400">{r.max_drawdown_pct}%</td>
                    <td className="py-2 pr-2 text-right tabular-nums">{r.total_trades}</td>
                    <td className={cn("py-2 pr-2 text-right tabular-nums",
                      r.expectancy >= 0 ? "text-emerald-400" : "text-red-400")}>
                      ₹{r.expectancy}
                    </td>
                    <td className="py-2 text-[10px] text-muted-foreground">{r.typical_win_rate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Summary cards */}
      {!loading && rankings.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <SummaryCard
            icon={Trophy}
            label="Best by Sharpe"
            value={rankings[0]?.strategy_name || "—"}
            subValue={`Sharpe ${rankings[0]?.sharpe || 0}`}
            color="text-amber-400"
          />
          <SummaryCard
            icon={TrendingUp}
            label="Best Return"
            value={rankings.reduce((max, r) => r.total_return_pct > max.total_return_pct ? r : max, rankings[0])?.strategy_name || "—"}
            subValue={`${rankings.reduce((max, r) => r.total_return_pct > max.total_return_pct ? r : max, rankings[0])?.total_return_pct || 0}%`}
            color="text-emerald-400"
          />
          <SummaryCard
            icon={Target}
            label="Best Win Rate"
            value={rankings.reduce((max, r) => r.win_rate > max.win_rate ? r : max, rankings[0])?.strategy_name || "—"}
            subValue={`${rankings.reduce((max, r) => r.win_rate > max.win_rate ? r : max, rankings[0])?.win_rate || 0}%`}
            color="text-blue-400"
          />
          <SummaryCard
            icon={TrendingDown}
            label="Lowest Drawdown"
            value={rankings.reduce((min, r) => r.max_drawdown_pct < min.max_drawdown_pct ? r : min, rankings[0])?.strategy_name || "—"}
            subValue={`${rankings.reduce((min, r) => r.max_drawdown_pct < min.max_drawdown_pct ? r : min, rankings[0])?.max_drawdown_pct || 0}%`}
            color="text-emerald-400"
          />
        </div>
      )}
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value, subValue, color }: any) {
  return (
    <Card className="p-3.5">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</span>
        <Icon className={cn("w-3.5 h-3.5", color)} />
      </div>
      <div className="text-xs font-semibold truncate">{value}</div>
      <div className={cn("text-[10px] font-mono tabular-nums mt-0.5", color)}>{subValue}</div>
    </Card>
  );
}
