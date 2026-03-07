"use client";

import React from "react";
import { TrendingUp, Clock, Zap, Target, ChevronRight, Car } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatBlock } from "@/components/ui/StatBlock";
import { EarningsChart } from "@/components/charts/EarningsChart";
import { shiftData, earningsLog, getPaceStatus } from "@/lib/mockData";

const paceConfig = {
  ahead: {
    label: "Ahead of Goal",
    variant: "green" as const,
    border: "border-[#05C168]/20",
    bg: "bg-[#05C168]/[0.08]",
    icon: TrendingUp,
    message: "Great pace! You're on track to exceed your daily goal.",
  },
  "on-track": {
    label: "On Track",
    variant: "yellow" as const,
    border: "border-[#FFC043]/20",
    bg: "bg-[#FFC043]/[0.08]",
    icon: Target,
    message: "Holding steady — maintain this pace to hit your target.",
  },
  behind: {
    label: "Falling Behind",
    variant: "red" as const,
    border: "border-[#E54937]/20",
    bg: "bg-[#E54937]/[0.08]",
    icon: Zap,
    message: "You need to pick up the pace to reach your daily goal.",
  },
};

export function MidShiftView() {
  const pace = getPaceStatus(shiftData);
  const config = paceConfig[pace];
  const PaceIcon = config.icon;
  const delta = shiftData.currentVelocity - shiftData.requiredVelocity;
  const hoursRemaining = shiftData.totalHours - shiftData.hoursWorked;

  return (
    <div className="space-y-4 pb-6">
      {/* ── Status Banner ──────────────────────────────────────────── */}
      <div
        className={`rounded-2xl ${config.bg} border ${config.border} p-4 flex items-start gap-3`}
      >
        <div className="mt-0.5 shrink-0">
          <PaceIcon size={20} aria-label={config.label} />
        </div>
        <div className="flex-1 min-w-0">
          <Badge variant={config.variant}>{config.label}</Badge>
          <p className="mt-1.5 text-[12px] text-white/60 leading-relaxed">
            {config.message}
          </p>
        </div>
      </div>

      {/* ── Earnings Goal ──────────────────────────────────────────── */}
      <Card>
        <div className="flex items-center gap-2 mb-1">
          <Target size={14} className="text-[#555]" aria-label="Earnings goal" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[#555]">
            Earnings Goal
          </span>
        </div>
        <div className="flex items-baseline gap-1 mb-3">
          <span className="text-[40px] font-extrabold text-white leading-none tracking-tight">
            ${shiftData.currentEarnings.toFixed(0)}
          </span>
          <span className="text-lg text-[#555] font-medium">
            / ${shiftData.earningsGoal}
          </span>
        </div>
        <ProgressBar
          value={shiftData.currentEarnings}
          max={shiftData.earningsGoal}
          showAmount={false}
        />
      </Card>

      {/* ── Velocity Stats ─────────────────────────────────────────── */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <Zap size={14} className="text-[#555]" aria-label="Velocity" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[#555]">
            Earning Velocity
          </span>
        </div>
        <div className="grid grid-cols-3 divide-x divide-[#1f1f1f]">
          <StatBlock
            label="Current"
            value={`$${shiftData.currentVelocity.toFixed(0)}`}
            unit="/hr"
          />
          <StatBlock
            label="Required"
            value={`$${shiftData.requiredVelocity.toFixed(0)}`}
            unit="/hr"
          />
          <StatBlock
            label="Delta"
            value={`${delta >= 0 ? "+" : ""}$${Math.abs(delta).toFixed(1)}`}
            unit="/hr"
            delta={delta >= 0 ? "Above pace" : "Below pace"}
            deltaType={delta >= 0 ? "positive" : "negative"}
          />
        </div>
      </Card>

      {/* ── Earnings Chart ─────────────────────────────────────────── */}
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={14} className="text-[#555]" aria-label="Earnings chart" />
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[#555]">
            Earnings Over Time
          </span>
        </div>
        <EarningsChart data={earningsLog} />
      </Card>

      {/* ── Shift Progress ─────────────────────────────────────────── */}
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-[#555]" aria-label="Shift progress" />
            <span className="text-[10px] font-semibold uppercase tracking-widest text-[#555]">
              Shift Progress
            </span>
          </div>
          <Badge variant="blue">
            <Car size={10} aria-label="Trips completed" />
            {shiftData.tripsCompleted} trips
          </Badge>
        </div>
        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-3xl font-extrabold text-white leading-none">
            {shiftData.hoursWorked}h
          </span>
          <span className="text-sm text-[#555]">
            / {shiftData.totalHours}h completed
          </span>
        </div>
        <ProgressBar
          value={shiftData.hoursWorked}
          max={shiftData.totalHours}
          showAmount={false}
          color="#276EF1"
          className="mt-3"
        />
        <div className="mt-2.5 flex items-center justify-between text-[11px] text-[#555]">
          <span>{hoursRemaining.toFixed(1)}h remaining</span>
          <span className="flex items-center gap-0.5 min-h-[44px] items-center">
            Est. end 12:00 AM
            <ChevronRight size={12} aria-label="Details" />
          </span>
        </div>
      </Card>
    </div>
  );
}
