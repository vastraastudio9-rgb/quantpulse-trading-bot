import { useState } from "react";
import { Target, TrendingDown, TrendingUp, Wallet, X } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ClosedTrade, Position, TradeMode } from "@/lib/trading/types";
import { cn, formatInr } from "@/lib/utils";
import { bookOf, useDesk } from "@/lib/trading/store";

export function PositionsView() {
  const { positions, closedTrades, closePosition, paperCapital, liveCapital } = useDesk();
  const [tab, setTab] = useState<"ALL" | TradeMode>("ALL");
  const paper = bookOf({ positions, closedTrades, paperCapital, liveCapital }, "PAPER");
  const live = bookOf({ positions, closedTrades, paperCapital, liveCapital }, "LIVE");
  const shown = tab === "ALL" ? positions : positions.filter((p) => p.mode === tab);
  const closedShown = tab === "ALL" ? closedTrades : closedTrades.filter((t) => t.mode === tab);
  const totalPnl = shown.reduce((s, p) => s + p.unrealizedPnl, 0);
  const avgPct = shown.length ? shown.reduce((s, p) => s + p.unrealizedPnlPct, 0) / shown.length : 0;
  const margin = shown.reduce((s, p) => s + p.avgPrice * p.quantity * 0.15, 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Open" value={String(shown.length)} icon={Wallet} />
        <Stat label="Unrealized P&L" value={`${totalPnl >= 0 ? "+" : ""}₹${formatInr(totalPnl)}`} icon={totalPnl >= 0 ? TrendingUp : TrendingDown} tone={totalPnl >= 0 ? "bull" : "bear"} />
        <Stat label="Avg P&L %" value={`${avgPct >= 0 ? "+" : ""}${avgPct.toFixed(2)}%`} icon={Target} tone={avgPct >= 0 ? "bull" : "bear"} />
        <Stat label="Margin used" value={`₹${formatInr(margin)}`} icon={Wallet} />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <BookCard title="Paper book" book={paper} />
        <BookCard title="Live book" book={live} live />
      </div>
      <div className="flex flex-wrap gap-2">
        {(["ALL", "PAPER", "LIVE"] as const).map((t) => (
          <Button key={t} size="sm" variant={tab === t ? "default" : "outline"} className="h-9" onClick={() => setTab(t)}>
            {t === "ALL" ? "All books" : t}
          </Button>
        ))}
      </div>
      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Open positions</h3>
          <Badge variant="outline">{shown.length} open</Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                {["Book", "Instrument", "Strategy", "Side", "Qty", "Avg", "LTP", "SL", "Target", "P&L", "P&L %", ""].map((h) => (
                  <th key={h} className="pb-2 pr-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {shown.length === 0 ? (
                <tr><td colSpan={12} className="py-8 text-center text-muted-foreground">No open positions. Generate a signal and tap Fill PAPER or Fill LIVE.</td></tr>
              ) : shown.map((p) => (
                <PosRow key={p.id} p={p} onClose={() => { closePosition(p.id, "MANUAL"); toast.message("Position closed", { description: `${p.mode} · ${p.instrument}` }); }} />
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-semibold">Closed trades</h3>
        {closedShown.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">Flatten a row or wait for SL/TP. Closed fills land here on both books.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  {["Book", "Instrument", "Strategy", "Reason", "Exit", "P&L", "When"].map((h) => (
                    <th key={h} className="pb-2 pr-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {closedShown.map((t) => (
                  <ClosedRow key={`${t.id}-${t.closedAt}`} t={t} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function BookCard({ title, book, live }: { title: string; book: ReturnType<typeof bookOf>; live?: boolean }) {
  const up = book.todayPnl >= 0;
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">{title}</h3>
        <Badge variant={live ? "bull" : "warn"}>{book.mode}</Badge>
      </div>
      <div className={cn("text-2xl font-semibold tabular-nums", up ? "text-bull" : "text-bear")}>
        {up ? "+" : ""}₹{formatInr(book.todayPnl)}
      </div>
      <p className="mt-1 text-micro text-muted-foreground">Today · equity ₹{formatInr(book.equity)} · {book.openCount} open · win {book.winRate}%</p>
    </Card>
  );
}

function PosRow({ p, onClose }: { p: Position; onClose: () => void }) {
  const up = p.unrealizedPnl >= 0;
  return (
    <tr className="hover:bg-muted/20">
      <td className="py-2 pr-3"><Badge variant={p.mode === "LIVE" ? "bull" : "warn"}>{p.mode}</Badge></td>
      <td className="py-2 pr-3">
        <div className="font-medium">{p.instrument}</div>
        <div className="text-micro text-muted-foreground">{p.exchange} · {p.lots} lot</div>
      </td>
      <td className="py-2 pr-3 text-2xs text-muted-foreground">{p.strategy}</td>
      <td className="py-2 pr-3"><Badge variant={p.side === "LONG" ? "bull" : "bear"}>{p.side}</Badge></td>
      <td className="py-2 pr-3 text-right tabular-nums">{p.quantity}</td>
      <td className="py-2 pr-3 text-right tabular-nums">{p.avgPrice.toFixed(2)}</td>
      <td className="py-2 pr-3 text-right font-medium tabular-nums">{p.ltp.toFixed(2)}</td>
      <td className="py-2 pr-3 text-right tabular-nums text-bear">{p.stopLoss.toFixed(2)}</td>
      <td className="py-2 pr-3 text-right tabular-nums text-bull">{p.target.toFixed(2)}</td>
      <td className={cn("py-2 pr-3 text-right font-medium tabular-nums", up ? "text-bull" : "text-bear")}>{up ? "+" : ""}₹{formatInr(p.unrealizedPnl)}</td>
      <td className={cn("py-2 pr-3 text-right tabular-nums", up ? "text-bull" : "text-bear")}>{up ? "+" : ""}{p.unrealizedPnlPct}%</td>
      <td className="py-2">
        <Button variant="ghost" size="sm" className="h-9 px-2 hover:bg-bear-bg hover:text-bear" onClick={onClose} aria-label={`Close ${p.instrument}`}>
          <X className="size-3" />
        </Button>
      </td>
    </tr>
  );
}

function ClosedRow({ t }: { t: ClosedTrade }) {
  const up = t.pnl >= 0;
  return (
    <tr>
      <td className="py-2 pr-3"><Badge variant={t.mode === "LIVE" ? "bull" : "warn"}>{t.mode}</Badge></td>
      <td className="py-2 pr-3 font-medium">{t.instrument}</td>
      <td className="py-2 pr-3 text-2xs text-muted-foreground">{t.strategy}</td>
      <td className="py-2 pr-3"><Badge variant={t.reason === "SL_HIT" || t.reason === "REGIME" ? "bear" : t.reason === "TP_HIT" ? "bull" : "outline"}>{t.reason}</Badge></td>
      <td className="py-2 pr-3 tabular-nums">{t.exitPrice.toFixed(2)}</td>
      <td className={cn("py-2 pr-3 font-medium tabular-nums", up ? "text-bull" : "text-bear")}>{up ? "+" : ""}₹{formatInr(t.pnl)}</td>
      <td className="py-2 pr-3 text-micro text-muted-foreground">
        {new Date(t.closedAt).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false })}
      </td>
    </tr>
  );
}

function Stat({ label, value, icon: Icon, tone }: { label: string; value: string; icon: typeof Wallet; tone?: "bull" | "bear" }) {
  return (
    <Card className="p-4">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-micro uppercase tracking-wider text-muted-foreground">{label}</span>
        <Icon className={cn("size-3.5", tone === "bull" ? "text-bull" : tone === "bear" ? "text-bear" : "text-muted-foreground")} />
      </div>
      <div className={cn("text-xl font-semibold tabular-nums", tone === "bull" && "text-bull", tone === "bear" && "text-bear")}>{value}</div>
    </Card>
  );
}
