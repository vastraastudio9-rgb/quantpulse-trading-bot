import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";

interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
  width?: number;
}

export function Sparkline({ data, color = "var(--color-bull)", height = 40, width = 120 }: SparklineProps) {
  if (!data.length) return <div style={{ height, width }} className="rounded bg-muted/40" />;
  const chartData = data.map((v, i) => ({ i, v }));
  const id = `sp-${color.replace(/[^a-z0-9]/gi, "").slice(-8)}`;
  return (
    <div style={{ height, width }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} fill={`url(#${id})`} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function EquityChart({ data, height = 280 }: { data: { date: string; value: number }[]; height?: number }) {
  if (!data.length) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-sm text-muted-foreground">
        No data
      </div>
    );
  }
  const chartData = data.map((d) => ({
    date: new Date(d.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }),
    value: d.value,
  }));
  const isUp = (chartData.at(-1)?.value ?? 0) >= (chartData[0]?.value ?? 0);
  const color = isUp ? "var(--color-bull)" : "var(--color-bear)";

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 8, bottom: 0, left: 0, right: 8 }}>
          <defs>
            <linearGradient id="equity-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis
            domain={["dataMin", "dataMax"]}
            tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}k`}
            stroke="var(--color-muted-foreground)"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={56}
          />
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill="url(#equity-grad)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
