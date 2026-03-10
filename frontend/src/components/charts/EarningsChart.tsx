"use client";

import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { EarningsLog } from "@/lib/types";

interface EarningsChartProps {
  data: EarningsLog[];
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#222] bg-[#0e0e0e] px-3 py-2 shadow-2xl">
      <p className="text-[10px] text-[#666]">{label}</p>
      <p className="text-sm font-bold text-white">${payload[0].value.toFixed(0)}</p>
    </div>
  );
}

export function EarningsChart({ data }: EarningsChartProps) {
  return (
    <div className="h-[170px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <defs>
            <linearGradient id="earningsGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#276EF1" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#276EF1" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="timestamp"
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#444", fontSize: 10, fontWeight: 500 }}
            dy={8}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#444", fontSize: 10, fontWeight: 500 }}
            tickFormatter={(v: number) => `₹${v}`}
            width={42}
          />
          <Tooltip content={<ChartTooltip />} cursor={false} />
          <Area
            type="monotone"
            dataKey="earnings"
            stroke="#276EF1"
            strokeWidth={2.5}
            fill="url(#earningsGrad)"
            dot={false}
            activeDot={{
              r: 5,
              fill: "#276EF1",
              stroke: "#0a0a0a",
              strokeWidth: 3,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
