import React from "react";

interface StatBlockProps {
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  deltaType?: "positive" | "negative" | "neutral";
  className?: string;
}

const deltaColors = {
  positive: "text-[#05C168]",
  negative: "text-[#E54937]",
  neutral: "text-[#666]",
};

export function StatBlock({
  label,
  value,
  unit,
  delta,
  deltaType = "neutral",
  className = "",
}: StatBlockProps) {
  return (
    <div className={`flex flex-col items-center gap-0.5 min-w-0 ${className}`}>
      <span className="text-[10px] font-semibold uppercase tracking-widest text-[#555]">
        {label}
      </span>
      <span className="text-xl font-extrabold text-white leading-none tabular-nums">
        {value}
        {unit && (
          <span className="ml-0.5 text-[11px] font-normal text-[#555]">{unit}</span>
        )}
      </span>
      {delta && (
        <span className={`text-[11px] font-semibold ${deltaColors[deltaType]}`}>
          {delta}
        </span>
      )}
    </div>
  );
}
