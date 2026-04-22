"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format, parseISO } from "date-fns";

type Point = { date: string; Close: number | null };

export function PriceChart({ data }: { data: Point[] }) {
  const rows = data.filter((d) => d.Close !== null).map((d) => ({
    date: d.date,
    close: d.Close as number,
  }));

  if (rows.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
        No price history available.
      </div>
    );
  }

  const closes = rows.map((r) => r.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const pad = (max - min) * 0.08 || 1;

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <AreaChart data={rows} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--accent))" stopOpacity={0.3} />
              <stop offset="100%" stopColor="hsl(var(--accent))" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            stroke="hsl(var(--muted-foreground))"
            fontSize={11}
            tickFormatter={(v: string) => safeFormat(v, "d MMM")}
            minTickGap={24}
          />
          <YAxis
            stroke="hsl(var(--muted-foreground))"
            fontSize={11}
            domain={[min - pad, max + pad]}
            tickFormatter={(n: number) => n.toFixed(2)}
            width={56}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number) => [`A$${value.toFixed(2)}`, "Close"]}
            labelFormatter={(v: string) => safeFormat(v, "EEEE d MMM yyyy")}
          />
          <Area
            type="monotone"
            dataKey="close"
            stroke="hsl(var(--accent))"
            strokeWidth={2}
            fill="url(#priceFill)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function safeFormat(value: string, pattern: string): string {
  try {
    const d = value.length === 10 ? parseISO(value) : new Date(value);
    return format(d, pattern);
  } catch {
    return value;
  }
}
