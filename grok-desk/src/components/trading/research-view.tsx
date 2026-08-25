import { BookOpen, ExternalLink, Layers, Lightbulb, Star } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getResearch } from "@/lib/trading/engine";
import { cn } from "@/lib/utils";

export function ResearchView() {
  const { repos, recommendedStack, keyInsights } = getResearch();
  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Layers className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">Recommended composable stack</h3>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">No single repo covers Kite + MT5 + options + validation. Layer these.</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(recommendedStack).map(([layer, rec]) => (
            <div key={layer} className="rounded-lg border border-border bg-muted/20 p-2.5">
              <div className="text-micro font-medium uppercase tracking-wider text-primary">{layer.replace(/_/g, " ")}</div>
              <div className="mt-0.5 text-xs">{rec}</div>
            </div>
          ))}
        </div>
      </Card>
      <Card className="border-warn/30 bg-warn-bg p-4">
        <div className="mb-3 flex items-center gap-2">
          <Lightbulb className="size-4 text-warn" />
          <h3 className="text-sm font-semibold">Reality check</h3>
        </div>
        <ul className="space-y-2">
          {keyInsights.map((insight) => (
            <li key={insight} className="flex gap-2 text-xs leading-relaxed text-muted-foreground">
              <span className="shrink-0 text-warn">→</span>
              <span>{insight}</span>
            </li>
          ))}
        </ul>
      </Card>
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold"><BookOpen className="size-4 text-primary" /> GitHub repositories</h3>
          <Badge variant="outline">{repos.length} analyzed</Badge>
        </div>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {repos.map((repo) => (
            <Card key={repo.name} className="p-4 transition-colors hover:border-primary/40">
              <div className="mb-2 flex items-start justify-between gap-2">
                <a href={repo.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-semibold hover:text-primary">
                  {repo.name} <ExternalLink className="size-3 opacity-60" />
                </a>
                <div className="flex items-center gap-0.5">
                  {Array.from({ length: 5 }, (_, i) => (
                    <Star key={i} className={cn("size-3", i < repo.rating ? "fill-primary text-primary" : "text-muted")} />
                  ))}
                </div>
              </div>
              <p className="mb-3 text-2xs leading-relaxed text-muted-foreground">{repo.description}</p>
              <div className="mb-2.5 text-micro"><span className="text-muted-foreground">Best for: </span><span className="font-medium text-primary">{repo.bestFor}</span></div>
              <div className="flex items-center gap-3 text-micro text-muted-foreground">
                <span className="flex items-center gap-1"><Star className="size-3" />{repo.stars}</span>
                <Badge variant="outline">{repo.lang}</Badge>
                <Badge variant="outline">{repo.license}</Badge>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
