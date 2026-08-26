"use client";

import { useEffect, useState } from "react";
import { Star, GitFork, ExternalLink, BookOpen, Lightbulb, Layers, FlaskConical, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { tradingApi, type ResearchRepo } from "@/lib/trading-api";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

export function ResearchView() {
  const [repos, setRepos] = useState<ResearchRepo[]>([]);
  const [stack, setStack] = useState<Record<string, string>>({});
  const [insights, setInsights] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalog, setCatalog] = useState<Array<{ source: string; symbol: string; timeframe: string; rows: number; start: string; end: string }>>([]);
  const [policy, setPolicy] = useState<{ mode: string; data_source: string; evidence_grade?: string } | null>(null);
  const [rnd, setRnd] = useState<any>(null);
  const [rndBusy, setRndBusy] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    (async () => {
      try {
        const [r, catalogRes, policyRes, rndRes] = await Promise.all([
          tradingApi.getResearch(),
          fetch("/api/jarvis/data/catalog?XTransformPort=3030"),
          fetch("/api/jarvis/research-policy?XTransformPort=3030"),
          fetch("/api/jarvis/rnd/intraday/latest?XTransformPort=3030"),
        ]);
        setRepos(r.repos);
        setStack(r.recommended_stack);
        setInsights(r.key_insights);
        if (catalogRes.ok) setCatalog((await catalogRes.json()).items || []);
        if (policyRes.ok) setPolicy(await policyRes.json());
        if (rndRes.ok) setRnd(await rndRes.json());
        setLoading(false);
      } catch (e: any) {
        toast({ title: "Failed to load research", description: e.message, variant: "destructive" });
        setLoading(false);
      }
    })();
  }, [toast]);

  const runIntradayResearch = async () => {
    setRndBusy(true);
    try {
      const response = await fetch("/api/jarvis/rnd/intraday/run?XTransformPort=3030", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: "NIFTYBEES", source: "YAHOO_PROXY", lot_size: 1, tick_size: 0.01 }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail?.message || payload.detail || "Research failed");
      setRnd(payload);
      toast({ title: "Intraday R&D completed", description: `${payload.candidates_tested || 0} candidates tested · ${payload.status}` });
    } catch (e: any) {
      toast({ title: "Intraday R&D failed", description: e.message, variant: "destructive" });
    } finally {
      setRndBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <Card className="p-5 h-48 animate-pulse bg-muted/20" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="p-5 h-40 animate-pulse bg-muted/20" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4 border-cyan-500/30 bg-cyan-500/5">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <h3 className="text-sm font-semibold">Research Evidence</h3>
            <p className="text-xs text-muted-foreground mt-1">Only quality-approved real candles can produce real-market evidence.</p>
          </div>
          <Badge variant="outline" className={cn("text-[10px]", policy?.evidence_grade === "REAL_MARKET" ? "text-emerald-400 border-emerald-500/40" : "text-amber-400 border-amber-500/40")}>
            {policy?.evidence_grade?.replace(/_/g, " ") || "ENGINEERING ONLY"}
          </Badge>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
          <EvidenceMetric label="Algorithm Mode" value={policy?.mode || "RISK OFF"} />
          <EvidenceMetric label="Policy Source" value={policy?.data_source || "NONE"} />
          <EvidenceMetric label="Real Datasets" value={String(catalog.length)} />
          <EvidenceMetric label="Stored Candles" value={catalog.reduce((sum, item) => sum + item.rows, 0).toLocaleString()} />
        </div>
        {catalog.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{catalog.map((item) => (
          <Badge key={`${item.source}-${item.symbol}-${item.timeframe}`} variant="outline" className="text-[9px]">
            {item.symbol} · {item.timeframe} · {item.rows.toLocaleString()} · {item.source}
          </Badge>
        ))}</div>}
      </Card>

      <Card className="p-4 border-violet-500/30 bg-violet-500/5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold"><FlaskConical className="h-4 w-4 text-violet-400" />Automated Intraday R&amp;D</h3>
            <p className="mt-1 text-xs text-muted-foreground">VWAP pullback and mean-reversion · costs · walk-forward · untouched holdout · paper-only gates.</p>
          </div>
          <Button size="sm" onClick={runIntradayResearch} disabled={rndBusy}>
            {rndBusy && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}{rndBusy ? "Testing..." : "Run Full R&D"}
          </Button>
        </div>
        {rnd && rnd.status !== "NOT_RUN" && <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-5 text-xs">
          <EvidenceMetric label="Decision" value={String(rnd.status).replace(/_/g, " ")} />
          <EvidenceMetric label="Strategy" value={rnd.selected_config?.strategy || "NONE"} />
          <EvidenceMetric label="Candidates" value={String(rnd.candidates_tested || 0)} />
          <EvidenceMetric label="Holdout Return" value={`${rnd.holdout?.return_pct ?? 0}%`} />
          <EvidenceMetric label="Holdout PF" value={String(rnd.holdout?.profit_factor ?? 0)} />
        </div>}
      </Card>
      {/* Recommended stack */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <Layers className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold">Recommended Composable Stack</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          No single GitHub repo covers all needs (Zerodha + MT5 + options + backtest). Use this layered stack:
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {Object.entries(stack).map(([layer, recommendation]) => (
            <div key={layer} className="bg-muted/20 p-2.5 rounded border border-border">
              <div className="text-[10px] text-emerald-400 uppercase tracking-wider font-medium">{layer.replace(/_/g, " ")}</div>
              <div className="text-xs mt-0.5">{recommendation}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Key insights */}
      <Card className="p-4 border-amber-500/30 bg-amber-500/5">
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-semibold">Key Insights & Reality Check</h3>
        </div>
        <ul className="space-y-2">
          {insights.map((insight, i) => (
            <li key={i} className="text-xs text-muted-foreground leading-relaxed flex gap-2">
              <span className="text-amber-400 shrink-0">→</span>
              <span>{insight}</span>
            </li>
          ))}
        </ul>
      </Card>

      {/* Repos grid */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-emerald-400" />
            Top GitHub Repositories
          </h3>
          <Badge variant="outline" className="text-[10px]">{repos.length} repos analyzed</Badge>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {repos.map((repo) => (
            <RepoCard key={repo.name} repo={repo} />
          ))}
        </div>
      </div>
    </div>
  );
}

function EvidenceMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded border border-border bg-background/30 p-2.5">
    <div className="text-[9px] uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="mt-1 font-medium truncate">{value}</div>
  </div>;
}

function RepoCard({ repo }: { repo: ResearchRepo }) {
  const ratingColor =
    repo.rating === 5 ? "text-emerald-400" : repo.rating === 4 ? "text-amber-400" : "text-zinc-400";

  return (
    <Card className="p-4 hover:border-emerald-500/40 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <a
          href={repo.url}
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-sm hover:text-emerald-400 inline-flex items-center gap-1"
        >
          {repo.name}
          <ExternalLink className="w-3 h-3 opacity-60" />
        </a>
        <div className="flex items-center gap-0.5">
          {[...Array(5)].map((_, i) => (
            <Star
              key={i}
              className={cn(
                "w-3 h-3",
                i < repo.rating ? `${ratingColor} fill-current` : "text-zinc-700"
              )}
            />
          ))}
        </div>
      </div>

      {/* Description */}
      <p className="text-[11px] text-muted-foreground leading-relaxed mb-3">{repo.description}</p>

      {/* Best for */}
      <div className="text-[10px] mb-2.5">
        <span className="text-muted-foreground">Best for: </span>
        <span className="text-emerald-400 font-medium">{repo.best_for}</span>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <Star className="w-3 h-3" />
          {repo.stars}
        </span>
        <Badge variant="outline" className="text-[9px] px-1 py-0">{repo.lang}</Badge>
        <Badge variant="outline" className="text-[9px] px-1 py-0">{repo.license}</Badge>
      </div>
    </Card>
  );
}
