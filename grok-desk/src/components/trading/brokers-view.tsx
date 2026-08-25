import { useMemo, useState } from "react";
import { CheckCircle2, ExternalLink, KeyRound, Plug, Send, ShieldCheck, Terminal, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { getBrokersStatus } from "@/lib/trading/engine";
import { testTelegram } from "@/lib/trading/telegram-api";
import { cn } from "@/lib/utils";
import { useDesk } from "@/lib/trading/store";

const FIELDS: Record<string, { key: string; label: string; placeholder: string; password?: boolean }[]> = {
  ZERODHA: [
    { key: "apiKey", label: "API Key", placeholder: "Kite API key", password: true },
    { key: "accessToken", label: "Access token", placeholder: "Daily access token", password: true },
  ],
  MT5: [
    { key: "login", label: "MT5 Login", placeholder: "Account number" },
    { key: "server", label: "Server", placeholder: "ICMarketsSC-Demo" },
  ],
  ANGEL: [{ key: "apiKey", label: "SmartAPI Key", placeholder: "Angel API key", password: true }],
  FYERS: [{ key: "apiKey", label: "App ID", placeholder: "Fyers App ID", password: true }],
};

export function BrokersView() {
  const { paperMode, setPaperMode, connectedBrokers, setBrokerConnected, setBrokerCreds, telegram } = useDesk();
  const status = useMemo(() => getBrokersStatus(connectedBrokers, paperMode), [connectedBrokers, paperMode]);

  return (
    <div className="space-y-4">
      <Card className="border-warn/30 bg-warn-bg p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-warn" />
              <span className="text-sm font-semibold">Trading mode</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Paper fills the simulated book. Live fills the live book, tries Kite if connected, and both push to Telegram when armed.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn("text-xs font-medium", paperMode ? "text-warn" : "text-bull")}>{paperMode ? "PAPER" : "LIVE"}</span>
            <Switch checked={!paperMode} onCheckedChange={(v) => setPaperMode(!v)} />
          </div>
        </div>
      </Card>
      <TelegramCard />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {status.brokers.map((b) => (
          <BrokerCard
            key={b.id}
            broker={b}
            paperMode={paperMode}
            onConnect={(creds) => {
              setBrokerCreds(b.id, creds);
              setBrokerConnected(b.id, true);
              toast.success(`${b.name} ${paperMode ? "paper" : "live"} session armed`);
            }}
          />
        ))}
      </div>
      <Card className="p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Terminal className="size-4 text-primary" /> Setup notes</h3>
        <div className="space-y-4 text-xs">
          <Step n="1" title="Telegram signals" href="https://t.me/BotFather" label="BotFather" items={["Message @BotFather, create a bot, copy the token", "Message your bot once, then get chat ID from @userinfobot", "Test send — a real message lands in Telegram"]} />
          <Step n="2" title="Zerodha Kite Connect" href="https://kite.trade/docs/connect/v3/" label="Kite docs" items={["Create a Connect app on developers.kite.trade", "Daily access token after login", "LIVE fills POST to Kite when key + token are saved"]} />
          <Step n="3" title="MetaTrader 5" href="https://www.mql5.com/en/docs/python" label="MT5 Python" items={["Keep the terminal open for the local socket API", "Demo account first", "Windows-only native package — desk still books live fills here"]} />
        </div>
      </Card>
      {telegram.enabled && (
        <p className="text-micro text-muted-foreground">Telegram bot token stays on this device. It is used only when sending a message.</p>
      )}
    </div>
  );
}

function BrokerCard({
  broker,
  paperMode,
  onConnect,
}: {
  broker: ReturnType<typeof getBrokersStatus>["brokers"][0];
  paperMode: boolean;
  onConnect: (creds: Record<string, string>) => void;
}) {
  const [vals, setVals] = useState<Record<string, string>>({});
  const fields = FIELDS[broker.type] ?? FIELDS.ZERODHA;
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-muted font-semibold text-primary">{broker.name[0]}</div>
          <div>
            <div className="text-sm font-semibold">{broker.name}</div>
            <div className="text-micro text-muted-foreground">{broker.type}</div>
          </div>
        </div>
        {broker.isConnected ? <Badge variant="bull"><CheckCircle2 className="size-3" /> CONNECTED</Badge> : <Badge variant="outline"><XCircle className="size-3" /> OFFLINE</Badge>}
      </div>
      <p className="mb-3 rounded bg-muted/30 p-2 text-2xs text-muted-foreground">{broker.message}</p>
      <div className="mb-3 flex flex-wrap gap-1">
        {broker.segments.map((s) => <Badge key={s} variant="outline">{s}</Badge>)}
      </div>
      <div className="mb-3 space-y-2">
        {fields.map((f) => (
          <div key={f.key}>
            <Label>{f.label}</Label>
            <Input type={f.password ? "password" : "text"} placeholder={f.placeholder} className="mt-1 h-9 text-xs" value={vals[f.key] ?? ""} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })} />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Button size="sm" className="h-9 text-xs" onClick={() => {
          if (Object.values(vals).some((v) => !v.trim())) { toast.error("Fill the fields first"); return; }
          onConnect(vals);
        }}>
          <Plug className="size-3" /> {paperMode ? "Arm paper session" : "Arm live routing"}
        </Button>
        <Button variant="outline" size="sm" className="h-9 text-xs" onClick={() => onConnect(vals)}><KeyRound className="size-3" /> Save</Button>
        <div className="flex-1" />
        <Badge variant={paperMode ? "warn" : "bull"}>{paperMode ? "PAPER" : "LIVE"}</Badge>
      </div>
    </Card>
  );
}

function TelegramCard() {
  const { telegram, setTelegram, setBrokerConnected, notify } = useDesk();
  const [token, setToken] = useState(telegram.botToken);
  const [chat, setChat] = useState(telegram.chatId);
  const [busy, setBusy] = useState(false);

  const connect = async () => {
    if (!token.trim() || !chat.trim()) {
      toast.error("Enter bot token and chat ID");
      return;
    }
    setBusy(true);
    try {
      const r = await testTelegram({ data: { token: token.trim(), chatId: chat.trim() } });
      setTelegram({ botToken: token.trim(), chatId: chat.trim(), enabled: true });
      setBrokerConnected("telegram", true);
      notify("TELEGRAM", "Telegram armed", `Signals will go to ${r.bot}`);
      toast.success(`Telegram connected · ${r.bot}`, { description: "Check your chat for the test message." });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Telegram test failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-primary/30 p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Send className="size-4 text-primary" />
            Telegram signals
          </div>
          <div className="text-micro text-muted-foreground">Real Bot API send — paper and live. Token stays on this device.</div>
        </div>
        {telegram.enabled ? <Badge variant="bull">ARMED</Badge> : <Badge variant="outline">NOT SET</Badge>}
      </div>
      <div className="mb-3 grid gap-2 sm:grid-cols-2">
        <div>
          <Label>Bot token</Label>
          <Input type="password" className="mt-1 h-9 text-xs" value={token} onChange={(e) => setToken(e.target.value)} placeholder="123456:ABC…" autoComplete="off" />
        </div>
        <div>
          <Label>Chat ID</Label>
          <Input className="mt-1 h-9 text-xs" value={chat} onChange={(e) => setChat(e.target.value)} placeholder="Your user id or -100…" inputMode="numeric" />
        </div>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-4 text-xs">
        <label className="flex items-center gap-2">
          <Switch checked={telegram.sendSignals} onCheckedChange={(v) => setTelegram({ sendSignals: v })} />
          Signals
        </label>
        <label className="flex items-center gap-2">
          <Switch checked={telegram.sendFills} onCheckedChange={(v) => setTelegram({ sendFills: v })} />
          Fills
        </label>
        <label className="flex items-center gap-2">
          <Switch checked={telegram.sendCloses} onCheckedChange={(v) => setTelegram({ sendCloses: v })} />
          Closes
        </label>
        <label className="flex items-center gap-2">
          <Switch checked={telegram.sendCycles !== false} onCheckedChange={(v) => setTelegram({ sendCycles: v })} />
          JARVIS cycles
        </label>
      </div>
      <Button size="sm" className="h-9 w-full text-xs" disabled={busy} onClick={() => void connect()}>
        <Send className="size-3.5" />
        {busy ? "Sending test…" : "Send test to Telegram"}
      </Button>
    </Card>
  );
}

function Step({ n, title, items, href, label }: { n: string; title: string; items: string[]; href: string; label: string }) {
  return (
    <div className="border-l-2 border-primary/40 pl-3">
      <div className="mb-1.5 flex items-center gap-2">
        <span className="flex size-5 items-center justify-center rounded-full bg-primary/15 text-micro font-semibold text-primary">{n}</span>
        <span className="text-xs font-medium">{title}</span>
        <a href={href} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-0.5 text-micro text-primary hover:underline">{label} <ExternalLink className="size-2.5" /></a>
      </div>
      <ul className="ml-7 space-y-1">
        {items.map((s) => <li key={s} className="text-2xs leading-relaxed text-muted-foreground">· {s}</li>)}
      </ul>
    </div>
  );
}
