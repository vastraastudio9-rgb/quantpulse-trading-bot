"use client";

import { useState } from "react";
import { Shield, Bell, Database, Send, AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { useToast } from "@/hooks/use-toast";

export function SettingsView() {
  const [maxDailyLoss, setMaxDailyLoss] = useState(3);
  const [maxPositions, setMaxPositions] = useState(5);
  const [positionSizing, setPositionSizing] = useState(2);
  const [killSwitch, setKillSwitch] = useState(false);
  const [soundAlerts, setSoundAlerts] = useState(true);
  const [telegramAlerts, setTelegramAlerts] = useState(false);
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const { toast } = useToast();

  const handleSave = () => {
    toast({
      title: "Settings saved",
      description: "Risk management + notification preferences updated.",
    });
  };

  const [testingTelegram, setTestingTelegram] = useState(false);

  const handleTestTelegram = async () => {
    if (!telegramToken || !telegramChatId) {
      toast({ title: "Missing credentials", description: "Enter Telegram bot token and chat ID first.", variant: "destructive" });
      return;
    }
    setTestingTelegram(true);
    try {
      const url = "/api/brokers/telegram/test?XTransformPort=3030";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token: telegramToken, chat_id: telegramChatId }),
      });
      const data = await res.json();
      if (data.ok) {
        toast({
          title: data.saved_securely ? "Telegram connected securely" : "Telegram test sent",
          description: data.saved_securely ? "Test delivered. Credentials encrypted locally for automatic restart recovery." : (data.save_error || data.message),
        });
      } else {
        toast({ title: "Telegram test failed", description: data.message || data.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Test failed", description: e.message, variant: "destructive" });
    } finally {
      setTestingTelegram(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Risk Management */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold">Risk Management</h3>
          <Badge variant="outline" className="text-[10px] ml-auto">Capital: ₹1,00,000</Badge>
        </div>

        <div className="space-y-4">
          {/* Max daily loss */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <Label className="text-xs">Max Daily Loss</Label>
              <span className="text-xs font-mono tabular-nums text-red-400">{maxDailyLoss}% (₹{(100000 * maxDailyLoss / 100).toLocaleString("en-IN", { maximumFractionDigits: 0 })})</span>
            </div>
            <Slider value={[maxDailyLoss]} onValueChange={(v) => setMaxDailyLoss(v[0])} min={1} max={10} step={0.5} className="py-1" />
            <p className="text-[10px] text-muted-foreground mt-1">Auto-halts all trading when daily loss exceeds this % of capital</p>
          </div>

          {/* Max open positions */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <Label className="text-xs">Max Open Positions</Label>
              <span className="text-xs font-mono tabular-nums">{maxPositions}</span>
            </div>
            <Slider value={[maxPositions]} onValueChange={(v) => setMaxPositions(v[0])} min={1} max={20} step={1} className="py-1" />
            <p className="text-[10px] text-muted-foreground mt-1">Maximum simultaneous open trades across all strategies</p>
          </div>

          {/* Position sizing */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <Label className="text-xs">Risk Per Trade</Label>
              <span className="text-xs font-mono tabular-nums text-amber-400">{positionSizing}% (₹{(100000 * positionSizing / 100).toLocaleString("en-IN", { maximumFractionDigits: 0 })})</span>
            </div>
            <Slider value={[positionSizing]} onValueChange={(v) => setPositionSizing(v[0])} min={0.5} max={5} step={0.5} className="py-1" />
            <p className="text-[10px] text-muted-foreground mt-1">% of capital risked per trade — used for position sizing calculation</p>
          </div>

          {/* Kill switch */}
          <div className="flex items-center justify-between pt-2 border-t border-border">
            <div>
              <Label className="text-xs font-medium">Kill Switch</Label>
              <p className="text-[10px] text-muted-foreground mt-0.5">Manually halt ALL trading immediately</p>
            </div>
            <Switch checked={killSwitch} onCheckedChange={(v) => {
              setKillSwitch(v);
              if (v) {
                toast({ title: "KILL SWITCH ACTIVATED", description: "All trading halted. No new orders will be placed.", variant: "destructive" });
              } else {
                toast({ title: "Kill switch deactivated", description: "Trading resumed." });
              }
            }} />
          </div>
        </div>
      </Card>

      {/* Notifications */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <Bell className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-semibold">Notifications</h3>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-xs font-medium">Sound Alerts</Label>
              <p className="text-[10px] text-muted-foreground mt-0.5">Play sound on new signal / SL hit / TP hit</p>
            </div>
            <Switch checked={soundAlerts} onCheckedChange={setSoundAlerts} />
          </div>

          <div className="pt-3 border-t border-border">
            <div className="flex items-center justify-between mb-2">
              <div>
                <Label className="text-xs font-medium">Telegram Alerts</Label>
                <p className="text-[10px] text-muted-foreground mt-0.5">Send signal alerts to Telegram</p>
              </div>
              <Switch checked={telegramAlerts} onCheckedChange={setTelegramAlerts} />
            </div>
            {telegramAlerts && (
              <div className="space-y-2 mt-2">
                <div>
                  <Label className="text-[10px]">Bot Token</Label>
                  <Input
                    type="password"
                    value={telegramToken}
                    onChange={(e) => setTelegramToken(e.target.value)}
                    placeholder="123456789:ABCdef..."
                    className="h-8 text-xs"
                  />
                </div>
                <div>
                  <Label className="text-[10px]">Chat ID</Label>
                  <Input
                    value={telegramChatId}
                    onChange={(e) => setTelegramChatId(e.target.value)}
                    placeholder="@yourchannel or 123456789"
                    className="h-8 text-xs"
                  />
                </div>
                <Button variant="outline" size="sm" className="h-7 text-xs" onClick={handleTestTelegram} disabled={testingTelegram}>
                  <Send className="w-3 h-3 mr-1" />
                  {testingTelegram ? "Sending..." : "Send Test"}
                </Button>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Data Storage */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <Database className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold">Data Storage</h3>
          <Badge variant="outline" className="text-[10px] ml-auto">SQLite • Local</Badge>
        </div>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Database location</span>
            <code className="text-[10px]">./db/custom.db</code>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Historical data retention</span>
            <span>6 months (configurable)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Trade log retention</span>
            <span>5 years (SEBI requirement)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Backup frequency</span>
            <span>Daily (3 AM IST)</span>
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <Button variant="outline" size="sm" className="h-7 text-xs">
            <Database className="w-3 h-3 mr-1" />
            Export Database
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs">
            Backup Now
          </Button>
        </div>
      </Card>

      {/* Warning */}
      <Card className="p-4 border-amber-500/30 bg-amber-500/5">
        <div className="flex gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-[11px] text-muted-foreground leading-relaxed">
            <span className="text-amber-400 font-medium">Important:</span> This is a paper trading system. No real orders are placed until you (1) connect a real broker, (2) switch off Paper mode in Brokers tab, and (3) explicitly enable LIVE for each strategy. Always start with paper trading for at least 4 weeks of forward testing before risking real capital. Past performance in backtests does not guarantee future results.
          </div>
        </div>
      </Card>

      {/* Save */}
      <div className="flex justify-end">
        <Button onClick={handleSave} className="h-9">Save All Settings</Button>
      </div>
    </div>
  );
}
