import { useEffect } from "react";
import { Sidebar, MobileNav } from "./sidebar";
import { Topbar } from "./topbar";
import { AlertsDrawer } from "./alerts-drawer";
import { DashboardView } from "./dashboard-view";
import { SignalsView } from "./signals-view";
import { BacktestView } from "./backtest-view";
import { ValidationView } from "./validation-view";
import { StrategiesView } from "./strategies-view";
import { PositionsView } from "./positions-view";
import { BrokersView } from "./brokers-view";
import { ResearchView } from "./research-view";
import { RegimeView } from "./regime-view";
import { LeaderboardView } from "./leaderboard-view";
import { JarvisResultsView } from "./jarvis-view";
import { SettingsView } from "./settings-view";
import { JARVIS_CYCLE_MS, useDesk } from "@/lib/trading/store";
import { enableLiveQuotes, generateAndStoreSignal } from "@/lib/trading/engine";

const SCAN_SYMBOLS = ["NIFTY", "BANKNIFTY", "GOLD", "XAUUSD"] as const;

export function AppShell() {
  const view = useDesk((s) => s.view);

  useEffect(() => {
    enableLiveQuotes();
    let scan: number | undefined;
    const tick = window.setInterval(() => useDesk.getState().tickMarket(), 3000);
    void Promise.resolve(useDesk.persist.rehydrate()).then(() => {
      const s = useDesk.getState();
      if (s.jarvisOn) {
        window.setTimeout(() => {
          if (useDesk.getState().jarvisOn) useDesk.getState().runJarvisCycle();
        }, 400);
      }
      scan = window.setInterval(() => {
        const st = useDesk.getState();
        if (st.jarvisOn) {
          st.runJarvisCycle();
          return;
        }
        if (st.killSwitch || !st.scannerOn) return;
        const keys = Object.entries(st.activeStrategies)
          .filter(([, on]) => on)
          .map(([k]) => k);
        if (!keys.length) return;
        const key = keys[Math.floor(Math.random() * keys.length)] ?? "STRADDLE_SELL";
        const symbol = SCAN_SYMBOLS[Math.floor(Math.random() * SCAN_SYMBOLS.length)] ?? "NIFTY";
        const sig = generateAndStoreSignal(key, symbol);
        st.ingestSignal(sig);
      }, JARVIS_CYCLE_MS);
    });
    return () => {
      window.clearInterval(tick);
      if (scan) window.clearInterval(scan);
    };
  }, []);

  return (
    <div className="flex min-h-svh bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
        <Topbar />
        <main className="mx-auto w-full max-w-[1600px] flex-1 p-4 lg:p-6">
          {view === "dashboard" && <DashboardView />}
          {view === "signals" && <SignalsView />}
          {view === "backtest" && <BacktestView />}
          {view === "validation" && <ValidationView />}
          {view === "strategies" && <StrategiesView />}
          {view === "positions" && <PositionsView />}
          {view === "brokers" && <BrokersView />}
          {view === "research" && <ResearchView />}
          {view === "regime" && <RegimeView />}
          {view === "leaderboard" && <LeaderboardView />}
          {view === "jarvis" && <JarvisResultsView />}
          {view === "settings" && <SettingsView />}
        </main>
      </div>
      <MobileNav />
      <AlertsDrawer />
    </div>
  );
}
