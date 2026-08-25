import { useEffect, useState } from "react";
import { Brain, CheckCircle2, Eye, XCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getRegimes } from "@/lib/trading/engine";
import type { RegimeSnapshot } from "@/lib/trading/types";
import { cn } from "@/lib/utils";

export function RegimeView() {
  const [regimes, setRegimes] = useState<RegimeSnapshot[]>(() => getRegimes());

  useEffect(() => {
    const t = setInterval(() => setRegimes(getRegimes()), 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-4">
      <Card className="border-primary/30 bg-primary/5 p-4">
        <div className="flex items-center gap-2">
          <Eye className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">Market Regime Monitor</h3>
          <Badge variant="outline" className="ml-auto">{regimes.length} instruments · 15s refresh</Badge>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">Trend / vol / range / liquidity / risk. Standing aside is a valid decision.</p>
      </Card>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {regimes.map((r) => <RegimeCard key={r.symbol} data={r} />)}
      </div>
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Brain className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">Strategy routing</h3>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs lg:grid-cols-3">
          {regimes.map((r) => (
            <div key={r.symbol} className="rounded border border-border p-2">
              <div className="mb-1 flex items-center justify-between">
                <span className="font-medium">{r.symbol}</span>
                <Badge variant={r.shouldTrade ? "bull" : "bear"}>{r.shouldTrade ? "TRADE OK" : "NO TRADE"}</Badge>
              </div>
              <div className="text-micro text-muted-foreground">{r.compositeRegime}</div>
              {r.recommendedStrategies.length > 0 && <div className="mt-1 text-micro text-bull">{r.recommendedStrategies.slice(0, 3).join(", ")}</div>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function RegimeCard({ data }: { data: RegimeSnapshot }) {
  const m = data.metrics;
  return (
    <Card className={cn("p-4", data.shouldTrade ? "border-bull/30" : "border-bear/30")}>
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-base font-bold">{data.symbol}</span>
            <Badge variant={data.shouldTrade ? "bull" : "bear"}>{data.shouldTrade ? "TRADE OK" : "NO TRADE"}</Badge>
          </div>
          <div className="mt-0.5 text-micro text-muted-foreground">{data.compositeRegime}</div>
        </div>
        <div className="text-right">
          <div className={cn("text-sm font-bold", data.shouldTrade ? "text-bull" : "text-bear")}>{data.confidence}%</div>
          <div className="text-micro text-muted-foreground">confidence</div>
        </div>
      </div>
      <div className="mb-3 grid grid-cols-3 gap-2 text-center">
        <Mini label="Trend" value={data.trendRegime} />
        <Mini label="Vol" value={data.volatilityRegime} />
        <Mini label="Risk" value={data.riskRegime} />
      </div>
      <div className="mb-3 grid grid-cols-3 gap-2">
        <Stat label="ADX" value={m.adx.toFixed(1)} />
        <Stat label="ATR %" value={m.atrPct.toFixed(2)} />
        <Stat label="BB width" value={m.bollingerWidthPct.toFixed(1)} />
        <Stat label="Hurst" value={m.hurst.toFixed(3)} />
        <Stat label="RSI" value={m.rsi.toFixed(1)} />
        <Stat label="Vol trend" value={`${m.volumeTrendPct > 0 ? "+" : ""}${m.volumeTrendPct}%`} />
      </div>
      <div className="border-t border-border pt-3">
        {data.shouldTrade ? (
          <>
            <div className="mb-1 flex items-start gap-1.5 text-micro text-bull"><CheckCircle2 className="mt-0.5 size-3 shrink-0" /> Recommended: {data.recommendedStrategies.join(", ")}</div>
            {data.avoidStrategies.length > 0 && <div className="flex items-start gap-1.5 text-micro text-bear"><XCircle className="mt-0.5 size-3 shrink-0" /> Avoid: {data.avoidStrategies.join(", ")}</div>}
          </>
        ) : (
          <div className="flex items-start gap-1.5 text-micro text-bear"><XCircle className="mt-0.5 size-3 shrink-0" /> {data.reason}</div>
        )}
      </div>
    </Card>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-micro uppercase text-muted-foreground">{label}</div>
      <div className="text-micro font-medium">{value}</div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-muted/30 p-1.5 text-center">
      <div className="text-micro text-muted-foreground">{label}</div>
      <div className="font-mono text-xs font-medium tabular-nums">{value}</div>
    </div>
  );
}
