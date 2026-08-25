import { useEffect, useState } from "react";
import { Loader2, Target, TrendingDown, TrendingUp, Trophy } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getInstruments, getLeaderboard } from "@/lib/trading/engine";
import type { Instrument, LeaderboardEntry } from "@/lib/trading/types";
import { cn } from "@/lib/utils";

export function LeaderboardView() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [symbol, setSymbol] = useState("NIFTY");
  const [days, setDays] = useState(90);
  const [rows, setRows] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => setInstruments(getInstruments()), []);

  useEffect(() => {
    setLoading(true);
    const t = window.setTimeout(() => {
      setRows(getLeaderboard(symbol, days));
      setLoading(false);
    }, 280);
    return () => window.clearTimeout(t);
  }, [symbol, days]);

  const best = rows[0];
  const bestReturn = rows.reduce((m, r) => (r.totalReturnPct > m.totalReturnPct ? r : m), rows[0]);
  const bestWr = rows.reduce((m, r) => (r.winRate > m.winRate ? r : m), rows[0]);
  const lowDd = rows.reduce((m, r) => (r.maxDrawdownPct < m.maxDrawdownPct ? r : m), rows[0]);

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label>Instrument</Label>
            <Select value={symbol} onValueChange={setSymbol}>
              <SelectTrigger className="h-9 w-40 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{instruments.map((i) => <SelectItem key={i.symbol} value={i.symbol} className="text-xs">{i.symbol}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Days</Label>
            <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
              <SelectTrigger className="h-9 w-24 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{[60, 90, 180].map((d) => <SelectItem key={d} value={String(d)} className="text-xs">{d}d</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <Button size="sm" className="h-9" onClick={() => {
            setLoading(true);
            window.setTimeout(() => {
              setRows(getLeaderboard(symbol, days));
              setLoading(false);
            }, 280);
          }} disabled={loading}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Trophy className="size-4" />} Refresh
          </Button>
          {best && (
            <div className="ml-auto flex items-center gap-2 text-xs">
              <Trophy className="size-4 text-primary" />
              <span className="text-muted-foreground">Best:</span>
              <span className="font-semibold">{best.strategyName}</span>
              <Badge variant="outline">Sharpe {best.sharpe}</Badge>
            </div>
          )}
        </div>
      </Card>
      <Card className="p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Trophy className="size-4 text-primary" /> {symbol} · {days}d</h3>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
            <Loader2 className="mr-2 size-5 animate-spin text-primary" /> Ranking strategies…
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  {["Rank", "Strategy", "Sharpe", "Return %", "Win rate", "PF", "Max DD", "Trades", "Expectancy"].map((h) => (
                    <th key={h} className="pb-2 pr-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((r) => (
                  <tr key={r.strategyKey} className={cn("hover:bg-muted/20", r.rank === 1 && "bg-primary/5")}>
                    <td className="py-2 pr-2 font-semibold tabular-nums">{r.rank}</td>
                    <td className="py-2 pr-2">
                      <div className="font-medium">{r.strategyName}</div>
                      <div className="text-micro text-muted-foreground">{r.type}</div>
                    </td>
                    <td className={cn("py-2 pr-2 text-right font-medium tabular-nums", r.sharpe >= 1 ? "text-bull" : r.sharpe >= 0 ? "text-warn" : "text-bear")}>{r.sharpe}</td>
                    <td className={cn("py-2 pr-2 text-right tabular-nums", r.totalReturnPct >= 0 ? "text-bull" : "text-bear")}>{r.totalReturnPct >= 0 ? "+" : ""}{r.totalReturnPct}%</td>
                    <td className="py-2 pr-2 text-right tabular-nums">{r.winRate}%</td>
                    <td className={cn("py-2 pr-2 text-right tabular-nums", r.profitFactor >= 1.5 ? "text-bull" : "text-muted-foreground")}>{r.profitFactor}</td>
                    <td className="py-2 pr-2 text-right tabular-nums text-bear">{r.maxDrawdownPct}%</td>
                    <td className="py-2 pr-2 text-right tabular-nums">{r.totalTrades}</td>
                    <td className={cn("py-2 text-right tabular-nums", r.expectancy >= 0 ? "text-bull" : "text-bear")}>₹{r.expectancy}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {!loading && rows.length > 0 && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Sum icon={Trophy} label="Best Sharpe" value={best?.strategyName ?? "—"} sub={`Sharpe ${best?.sharpe ?? 0}`} />
          <Sum icon={TrendingUp} label="Best return" value={bestReturn?.strategyName ?? "—"} sub={`${bestReturn?.totalReturnPct ?? 0}%`} />
          <Sum icon={Target} label="Best win rate" value={bestWr?.strategyName ?? "—"} sub={`${bestWr?.winRate ?? 0}%`} />
          <Sum icon={TrendingDown} label="Lowest drawdown" value={lowDd?.strategyName ?? "—"} sub={`${lowDd?.maxDrawdownPct ?? 0}%`} />
        </div>
      )}
    </div>
  );
}

function Sum({ icon: Icon, label, value, sub }: { icon: typeof Trophy; label: string; value: string; sub: string }) {
  return (
    <Card className="p-3.5">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-micro uppercase tracking-wider text-muted-foreground">{label}</span>
        <Icon className="size-3.5 text-primary" />
      </div>
      <div className="truncate text-xs font-semibold">{value}</div>
      <div className="mt-0.5 font-mono text-micro tabular-nums text-primary">{sub}</div>
    </Card>
  );
}
