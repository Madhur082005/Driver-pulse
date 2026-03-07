"use client";

import React, { useState } from "react";
import {
  Star,
  ShieldCheck,
  ChevronDown,
  MapPin,
  Clock,
  Route,
  Sparkles,
} from "lucide-react";

import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EventDistributionChart } from "@/components/charts/EventDistributionChart";
import { StressEventTimeline } from "@/components/timeline/StressEventTimeline";
import { trips, flaggedMoments, getEventDistribution, getStarRating } from "@/lib/mockData";

function QualityStars({ score }: { score: number }) {
  const filled = getStarRating(score);
  return (
    <div className="flex items-center gap-0.5" aria-label={`${filled} out of 5 stars`}>
      {Array.from({ length: 5 }).map((_, i) => (
        <Star
          key={i}
          size={16}
          className={
            i < filled
              ? "fill-[#FFC043] text-[#FFC043]"
              : "text-white/10"
          }
          aria-hidden
        />
      ))}
    </div>
  );
}

export function PostTripView() {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const trip = trips[selectedIdx];
  const events = flaggedMoments[trip.tripId] || [];
  const distribution = getEventDistribution(events);
  const hasEvents = events.length > 0;

  const scoreColor =
    trip.qualityScore >= 80
      ? "text-[#05C168]"
      : trip.qualityScore >= 50
      ? "text-[#FFC043]"
      : "text-[#E54937]";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 pb-6">
      {/* ── Trip Selector ──────────────────────────────────────────── */}
      <div className="relative lg:col-span-12">
        <select
          value={selectedIdx}
          onChange={(e) => setSelectedIdx(Number(e.target.value))}
          aria-label="Select trip"
          className={[
            "w-full appearance-none rounded-2xl border border-[#1f1f1f] bg-[#111]",
            "px-4 py-3.5 pr-10 text-sm font-semibold text-white",
            "outline-none focus:border-[#276EF1] transition-colors duration-200",
            "min-h-[48px]",
          ].join(" ")}
        >
          {trips.map((t, i) => (
            <option key={t.tripId} value={i}>
              Trip #{t.tripId.split("-")[1]} — {t.route.split("→")[0].trim()}
            </option>
          ))}
        </select>
        <ChevronDown
          size={16}
          className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[#555]"
          aria-hidden
        />
      </div>

      {/* ── Trip Meta ──────────────────────────────────────────────── */}
      <div className="flex items-center gap-4 text-[11px] text-[#555] lg:col-span-12">
        <span className="flex items-center gap-1">
          <Clock size={11} aria-label="Duration" />
          {trip.duration}
        </span>
        <span className="flex items-center gap-1">
          <MapPin size={11} aria-label="Distance" />
          {trip.distance}
        </span>
        <span className="flex items-center gap-1">
          <Route size={11} aria-label="Route" />
          ${trip.fare.toFixed(2)}
        </span>
      </div>

      {/* ── Quality Score ──────────────────────────────────────────── */}
      <Card className="lg:col-span-6">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-widest text-[#555]">
              Trip Quality Score
            </span>
            <div className="mt-1 flex items-baseline gap-2">
              <span className={`text-[44px] font-extrabold leading-none tracking-tight ${scoreColor}`}>
                {trip.qualityScore}
              </span>
              <span className="text-sm text-[#444]">/ 100</span>
            </div>
            <div className="mt-2">
              <QualityStars score={trip.qualityScore} />
            </div>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white/[0.04]">
            <ShieldCheck size={28} className={scoreColor} aria-label="Quality shield" />
          </div>
        </div>
      </Card>

      {hasEvents ? (
        <>
          {/* ── Event Distribution ────────────────────────────────── */}
          <Card className="lg:col-span-6">
            <span className="block mb-3 text-[10px] font-semibold uppercase tracking-widest text-[#555]">
              Event Distribution
            </span>
            <EventDistributionChart data={distribution} />
          </Card>

          {/* ── Stress Event Timeline ────────────────────────────── */}
          <Card className="lg:col-span-12">
            <span className="block mb-4 text-[10px] font-semibold uppercase tracking-widest text-[#555]">
              Flagged Moments
            </span>
            <StressEventTimeline events={events} />
          </Card>
        </>
      ) : (
        /* ── Empty State ──────────────────────────────────────────── */
        <div className="flex flex-col items-center justify-center py-14 text-center lg:col-span-12">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#05C168]/10">
            <Sparkles size={28} className="text-[#05C168]" aria-label="Clean trip" />
          </div>
          <h3 className="text-sm font-semibold text-white">No stress events detected</h3>
          <p className="mt-1.5 max-w-[240px] text-[12px] text-[#555] leading-relaxed">
            This trip was smooth sailing — great driving! Keep it up.
          </p>
          <Badge variant="green" className="mt-4">
            <ShieldCheck size={12} aria-label="Perfect" />
            Clean Trip
          </Badge>
        </div>
      )}
    </div>
  );
}
