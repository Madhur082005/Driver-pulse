import React from "react";

interface ProgressBarProps {
  value: number;
  max: number;
  label?: string;
  showAmount?: boolean;
  color?: string;
  className?: string;
}

export function ProgressBar({
  value,
  max,
  label,
  showAmount = true,
  color = "#05C168",
  className = "",
}: ProgressBarProps) {
  const pct = Math.min((value / max) * 100, 100);

  return (
    <div className={`w-full ${className}`}>
      {(label || showAmount) && (
        <div className="mb-2 flex items-end justify-between">
          {label && (
            <span className="text-[11px] font-medium uppercase tracking-wider text-[#666]">
              {label}
            </span>
          )}
          {showAmount && (
            <span className="text-xs font-semibold text-white">
              ${value.toFixed(0)}
              <span className="font-normal text-[#666]"> / ${max}</span>
            </span>
          )}
        </div>
      )}
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-white/[0.06]">
        {/* Animated fill */}
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-700 ease-out"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
        {/* Glow at the leading edge */}
        <div
          className="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full blur-md opacity-50 transition-all duration-700"
          style={{ left: `calc(${pct}% - 8px)`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}
