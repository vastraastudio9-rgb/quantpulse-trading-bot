"use client";

import { LineChart, Line, ResponsiveContainer, YAxis, Area, AreaChart } from "recharts";

interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
  width?: number;
  fill?: boolean;
}

export function Sparkline({ data, color = "#10B981", height = 40, width = 120, fill = false }: SparklineProps) {
  if (!data || data.length === 0) {
    return <div style={{ height, width }} className="bg-muted/20 rounded animate-pulse" />;
  }
  const chartData = data.map((v, i) => ({ i, v }));
  return (
    <div style={{ height, width }}>
      <ResponsiveContainer width="100%" height="100%">
        {fill ? (
          <AreaChart data={chartData} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
            <defs>
              <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.4} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="v"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#grad-${color.replace("#", "")})`}
              isAnimationActive={false}
            />
          </AreaChart>
        ) : (
          <LineChart data={chartData} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
            <YAxis domain={["dataMin", "dataMax"]} hide />
            <Line
              type="monotone"
              dataKey="v"
              stroke={color}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

interface EquityChartProps {
  data: { date: string; value: number }[];
  height?: number;
}

export function EquityChart({ data, height = 280 }: EquityChartProps) {
  if (!data || data.length === 0) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-muted-foreground text-sm">
        No data
      </div>
    );
  }
  const chartData = data.map((d) => ({
    date: new Date(d.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }),
    value: d.value,
  }));
  const firstValue = chartData[0]?.value ?? 0;
  const lastValue = chartData[chartData.length - 1]?.value ?? 0;
  const isUp = lastValue >= firstValue;
  const color = isUp ? "#10B981" : "#EF4444";

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
            tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
            stroke="#6B7280"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={56}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill="url(#equity-grad)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
