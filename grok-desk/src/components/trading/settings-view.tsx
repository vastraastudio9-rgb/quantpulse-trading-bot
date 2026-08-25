import { type ReactNode } from "react";
import { AlertTriangle, Bell, Database, Send, Shield } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { useDesk } from "@/lib/trading/store";
import { formatInr } from "@/lib/utils";

export function SettingsView() {
  const {
    maxDailyLoss, setMaxDailyLoss, maxPositions, setMaxPositions, riskPerTrade, setRiskPerTrade,
    killSwitch, setKillSwitch, soundAlerts, setSoundAlerts,
    autoExecutePaper, setAutoExecutePaper, autoExecuteLive, setAutoExecuteLive,
    scannerOn, setScannerOn, telegram, paperMode, setView, jarvisOn, setJarvisOn,
  } = useDesk();

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Shield className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">Risk management</h3>
          <Badge variant="outline" className="ml-auto">₹1,00,000 per book</Badge>
        </div>
        <div className="space-y-4">
          <SliderRow label="Max daily loss" value={`${maxDailyLoss}% (₹${formatInr(100000 * maxDailyLoss / 100)})`} hint="Arms the kill switch when either book breaches this % today.">
            <Slider value={[maxDailyLoss]} onValueChange={(v) => setMaxDailyLoss(v[0] ?? 3)} min={1} max={10} step={0.5} />
          </SliderRow>
          <SliderRow label="Max open positions" value={String(maxPositions)} hint="Cap simultaneous fills on each book.">
            <Slider value={[maxPositions]} onValueChange={(v) => setMaxPositions(v[0] ?? 5)} min={1} max={20} step={1} />
          </SliderRow>
          <SliderRow label="Risk per trade" value={`${riskPerTrade}% (₹${formatInr(100000 * riskPerTrade / 100)})`} hint="Used for lot sizing on paper and live fills.">
            <Slider value={[riskPerTrade]} onValueChange={(v) => setRiskPerTrade(v[0] ?? 2)} min={0.5} max={5} step={0.5} />
          </SliderRow>
          <div className="flex items-center justify-between border-t border-border pt-3">
            <div>
              <Label className="font-medium text-foreground">Kill switch</Label>
              <p className="mt-0.5 text-micro text-muted-foreground">Halt new entries. JARVIS still exits into the close and on regime flips.</p>
            </div>
            <Switch checked={killSwitch} onCheckedChange={(v) => { setKillSwitch(v); toast[v ? "error" : "success"](v ? "Kill switch on — no new orders" : "Kill switch off"); }} />
          </div>
        </div>
      </Card>
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Bell className="size-4 text-warn" />
          <h3 className="text-sm font-semibold">Execution & alerts</h3>
        </div>
        <div className="space-y-3">
          <Row label="Sound alerts" hint="Tone on new generated signals">
            <Switch checked={soundAlerts} onCheckedChange={setSoundAlerts} />
          </Row>
          <Row label="JARVIS autonomous" hint="Enter, hold, regime-exit, session flatten — every ~45s">
            <Switch checked={jarvisOn} onCheckedChange={setJarvisOn} />
          </Row>
          <Row label="Random scanner" hint="Fallback signals when JARVIS is disarmed">
            <Switch checked={scannerOn} onCheckedChange={setScannerOn} />
          </Row>
          <Row label="Auto-fill paper" hint="Every new signal fills the paper book">
            <Switch checked={autoExecutePaper} onCheckedChange={setAutoExecutePaper} />
          </Row>
          <Row label="Auto-fill live" hint="Every new signal fills the live book (dangerous)">
            <Switch checked={autoExecuteLive} onCheckedChange={setAutoExecuteLive} />
          </Row>
        </div>
      </Card>
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Send className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">Telegram</h3>
          <Badge variant={telegram.enabled ? "bull" : "outline"} className="ml-auto">{telegram.enabled ? "ARMED" : "OFF"}</Badge>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">
          {telegram.enabled
            ? `Chat ${telegram.chatId} receives ${[telegram.sendSignals && "signals", telegram.sendFills && "fills", telegram.sendCloses && "closes", telegram.sendCycles !== false && "JARVIS cycles"].filter(Boolean).join(", ")}.`
            : "Not armed. Open Brokers, paste a BotFather token and chat ID, then send a test."}
        </p>
        <Button variant="outline" size="sm" className="h-9" onClick={() => setView("brokers")}>Open Telegram setup</Button>
      </Card>
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Database className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">Local storage</h3>
          <Badge variant="outline" className="ml-auto">This device</Badge>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between"><span className="text-muted-foreground">Desk state</span><span>localStorage · quantpulse-desk</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Books</span><span>Paper + live ledgers persisted</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Telegram token</span><span>Stored here, sent only to Telegram</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Broker secrets</span><span>Memory only — re-enter after refresh</span></div>
        </div>
      </Card>
      <Card className={cnWarn(paperMode)}>
        <div className="flex gap-2.5">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />
          <p className="text-2xs leading-relaxed text-muted-foreground">
            <span className="font-medium text-warn">{paperMode ? "Paper book." : "Live book."}</span>{" "}
            {paperMode
              ? "Paper fills are simulated. Arm Telegram to get the same tickets on your phone. Connect Kite before switching to LIVE if you want broker routing."
              : "Live fills post to the live ledger and Telegram. Kite orders fire only with a valid access token. Size small and keep the kill switch reachable."}
          </p>
        </div>
      </Card>
      <div className="flex justify-end">
        <Button className="h-9" onClick={() => toast.success("Settings saved on this device")}>Save settings</Button>
      </div>
    </div>
  );
}

function cnWarn(paper: boolean) {
  return paper ? "border-warn/30 bg-warn-bg p-4" : "border-bull/30 bg-bull-bg p-4";
}

function Row({ label, hint, children }: { label: string; hint: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <Label className="font-medium text-foreground">{label}</Label>
        <p className="mt-0.5 text-micro text-muted-foreground">{hint}</p>
      </div>
      {children}
    </div>
  );
}

function SliderRow({ label, value, hint, children }: { label: string; value: string; hint: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <Label>{label}</Label>
        <span className="font-mono text-xs tabular-nums">{value}</span>
      </div>
      {children}
      <p className="mt-1 text-micro text-muted-foreground">{hint}</p>
    </div>
  );
}
