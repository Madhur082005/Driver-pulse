import React from "react";
import type { LucideIcon } from "lucide-react";

interface TimelineItemProps {
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  title: string;
  subtitle: string;
  time?: string;
  isLast?: boolean;
  children?: React.ReactNode;
}

export function TimelineItem({
  icon: Icon,
  iconColor = "text-[#4e8ef7]",
  iconBg = "bg-[#276EF1]/10",
  title,
  subtitle,
  time,
  isLast = false,
  children,
}: TimelineItemProps) {
  return (
    <div className="flex gap-3 group">
      {/* Vertical connector */}
      <div className="flex flex-col items-center">
        <div
          className={[
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
            "transition-transform duration-200 group-hover:scale-110",
            iconBg,
            iconColor,
          ].join(" ")}
        >
          <Icon size={16} aria-label={title} />
        </div>
        {!isLast && (
          <div className="w-px flex-1 bg-gradient-to-b from-[#222] to-transparent" />
        )}
      </div>

      {/* Content */}
      <div className="pb-5 min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-white">{title}</span>
          {time && (
            <span className="text-[10px] text-[#555] tabular-nums">{time}</span>
          )}
        </div>
        <p className="mt-0.5 text-[12px] text-[#666] leading-relaxed">
          {subtitle}
        </p>
        {children && (
          <div className="mt-2.5 transition-all duration-300">{children}</div>
        )}
      </div>
    </div>
  );
}
