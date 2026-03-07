import React from "react";
import { AlertTriangle, Volume2, Users } from "lucide-react";
import { TimelineItem } from "./TimelineItem";
import { Badge } from "@/components/ui/Badge";
import type { FlaggedMoment } from "@/lib/types";

interface StressEventTimelineProps {
  events: FlaggedMoment[];
}

const eventIcons = {
  "Harsh Braking": AlertTriangle,
  "Audio Spike": Volume2,
  Conflict: Users,
} as const;

const eventStyles = {
  "Harsh Braking": { color: "text-[#E54937]", bg: "bg-[#E54937]/10" },
  "Audio Spike": { color: "text-[#FFC043]", bg: "bg-[#FFC043]/10" },
  Conflict: { color: "text-[#276EF1]", bg: "bg-[#276EF1]/10" },
} as const;

export function StressEventTimeline({ events }: StressEventTimelineProps) {
  return (
    <div>
      {events.map((evt, i) => {
        const Icon = eventIcons[evt.eventType];
        const style = eventStyles[evt.eventType];
        const severityVariant = evt.severity === "High" ? "red" : "yellow";

        return (
          <TimelineItem
            key={evt.id}
            icon={Icon}
            iconColor={style.color}
            iconBg={style.bg}
            title={evt.eventType}
            subtitle={`${evt.tripProgress}% into trip — ${evt.description}`}
            time={evt.timestamp}
            isLast={i === events.length - 1}
          >
            {/* Transparency Card with raw signals */}
            <div className="rounded-xl border border-[#1a1a1a] bg-[#0c0c0c] p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-[#555]">
                  Raw Signals
                </span>
                <Badge variant={severityVariant}>{evt.severity}</Badge>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <div>
                  <span className="text-[#555]">Max Jerk: </span>
                  <span
                    className={`font-bold ${
                      evt.maxJerk > 3.0 ? "text-[#E54937]" : "text-white"
                    }`}
                  >
                    {evt.maxJerk} m/s³
                  </span>
                </div>
                <div className="h-3 w-px bg-[#222]" />
                <div>
                  <span className="text-[#555]">Avg Audio: </span>
                  <span
                    className={`font-bold ${
                      evt.avgAudio > 80 ? "text-[#FFC043]" : "text-white"
                    }`}
                  >
                    {evt.avgAudio} dB
                  </span>
                </div>
              </div>
            </div>
          </TimelineItem>
        );
      })}
    </div>
  );
}
