"use client";

import React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { EVENT_COLORS } from "@/lib/mockData";

interface Slice {
  name: string;
  value: number;
}

interface EventDistributionChartProps {
  data: Slice[];
}

function DonutTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number }>;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#222] bg-[#0e0e0e] px-3 py-2 shadow-2xl">
      <p className="text-xs font-semibold text-white">
        {payload[0].name}: {payload[0].value}
      </p>
    </div>
  );
}

export function EventDistributionChart({ data }: EventDistributionChartProps) {
  return (
    <div className="flex items-center gap-5">
      <div className="h-[110px] w-[110px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={30}
              outerRadius={48}
              strokeWidth={0}
              paddingAngle={3}
            >
              {data.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={EVENT_COLORS[entry.name] || "#444"}
                />
              ))}
            </Pie>
            <Tooltip content={<DonutTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-col gap-2">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-2 text-xs">
            <span
              className="h-2.5 w-2.5 rounded-full shrink-0"
              style={{ backgroundColor: EVENT_COLORS[d.name] || "#444" }}
            />
            <span className="text-white font-medium">{d.name}</span>
            <span className="text-[#555]">×{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
