import React from "react";

type BadgeVariant = "green" | "yellow" | "red" | "blue" | "muted";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const styles: Record<BadgeVariant, string> = {
  green: "bg-[#05C168]/15 text-[#05C168] border-[#05C168]/20",
  yellow: "bg-[#FFC043]/15 text-[#FFC043] border-[#FFC043]/20",
  red: "bg-[#E54937]/15 text-[#E54937] border-[#E54937]/20",
  blue: "bg-[#276EF1]/15 text-[#4e8ef7] border-[#276EF1]/20",
  muted: "bg-white/5 text-[#888] border-white/5",
};

export function Badge({ children, variant = "muted", className = "" }: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1",
        "text-[11px] font-semibold tracking-wide uppercase",
        "transition-colors duration-150",
        "min-h-[24px]",
        styles[variant],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}
