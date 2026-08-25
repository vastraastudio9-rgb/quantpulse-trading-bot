import { Bell, CheckCheck, Radio, Send, ShieldAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDesk } from "@/lib/trading/store";

export function AlertsDrawer() {
  const { alertsOpen, setAlertsOpen, alerts, markAlertsRead } = useDesk();
  if (!alertsOpen) return null;

  return (
    <div className="fixed inset-0 z-50">
      <button type="button" className="absolute inset-0 bg-background/60 backdrop-blur-sm" aria-label="Close alerts" onClick={() => setAlertsOpen(false)} />
      <aside className="absolute top-0 right-0 flex h-full w-full max-w-md flex-col border-l border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Bell className="size-4 text-primary" />
            <h2 className="text-sm font-semibold">Desk alerts</h2>
          </div>
          <div className="flex items-center gap-1">
            <button type="button" className="rounded-md p-2 text-muted-foreground hover:bg-muted/40 hover:text-foreground" onClick={markAlertsRead} aria-label="Mark read">
              <CheckCheck className="size-4" />
            </button>
            <button type="button" className="rounded-md p-2 text-muted-foreground hover:bg-muted/40 hover:text-foreground" onClick={() => setAlertsOpen(false)} aria-label="Close">
              <X className="size-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          {alerts.length === 0 ? (
            <p className="px-2 py-12 text-center text-sm text-muted-foreground">No alerts yet. Generate a signal or arm Telegram.</p>
          ) : (
            <ul className="space-y-2">
              {alerts.map((a) => (
                <li key={a.id} className={cn("rounded-lg border border-border p-3", !a.read && "border-primary/30 bg-primary/5")}>
                  <div className="mb-1 flex items-center gap-2">
                    {a.kind === "TELEGRAM" ? <Send className="size-3.5 text-primary" /> : a.kind === "RISK" ? <ShieldAlert className="size-3.5 text-bear" /> : <Radio className="size-3.5 text-warn" />}
                    <span className="text-xs font-semibold">{a.title}</span>
                    {a.mode && <span className={cn("ml-auto text-micro font-semibold", a.mode === "LIVE" ? "text-bull" : "text-warn")}>{a.mode}</span>}
                  </div>
                  <p className="text-2xs leading-relaxed text-muted-foreground">{a.body}</p>
                  <p className="mt-1 text-micro text-muted-foreground">
                    {new Date(a.at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false })} IST
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
