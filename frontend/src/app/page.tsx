// Main Application Entry Point
"use client";

import React, { useState } from "react";
import { Home, ClipboardList, Activity, LogOut } from "lucide-react";
import { signOut } from "next-auth/react";
import { MidShiftView } from "@/views/MidShiftView";
import { PostTripView } from "@/views/PostTripView";
import type { TabId } from "@/lib/types";

const tabs: { id: TabId; label: string; icon: typeof Home }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "trips", label: "Trips", icon: ClipboardList },
];

export default function DriverDashboard() {
  const [activeTab, setActiveTab] = useState<TabId>("home");

  return (
    <div className="flex min-h-dvh flex-col">
      {/* ── Sticky Header ─────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b border-[#141414] bg-[#0a0a0a]/90 backdrop-blur-xl px-4 lg:px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#276EF1]">
              <Activity size={15} className="text-white" aria-label="Driver Pulse logo" />
            </div>
            <div>
              <h1 className="text-[13px] font-bold text-white leading-tight">
                Driver Pulse
              </h1>
              <p className="text-[9px] text-[#555] uppercase tracking-widest font-medium">
                Live Shift Intelligence
              </p>
            </div>
          </div>

          {/* ── Desktop Navigation (hidden on mobile) ──────────── */}
          <nav className="hidden lg:flex items-center gap-1" aria-label="Desktop navigation">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={[
                    "flex items-center gap-2 rounded-xl px-4 py-2 text-[13px] font-semibold transition-all duration-200",
                    isActive
                      ? "bg-[#276EF1]/10 text-[#276EF1]"
                      : "text-[#555] hover:text-white hover:bg-white/5",
                  ].join(" ")}
                  aria-current={isActive ? "page" : undefined}
                >
                  <Icon size={16} aria-hidden />
                  {tab.label}
                </button>
              );
            })}
          </nav>

          <div className="flex items-center gap-3">
            {/* Online badge */}
            <div className="flex h-7 items-center rounded-full bg-[#05C168]/10 border border-[#05C168]/20 px-2.5 gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[#05C168] animate-pulse" />
              <span className="text-[9px] font-bold text-[#05C168] uppercase tracking-wider">
                Online
              </span>
            </div>

            {/* Logout button */}
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#1f1f1f] bg-[#111] text-[#555] transition-all duration-200 hover:text-white hover:border-[#333] hover:bg-[#1a1a1a] active:scale-95"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Content ──────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto pt-4 pb-[88px] lg:pb-6">
        <div
          className="max-w-screen-xl w-full mx-auto px-4 sm:px-6 lg:px-8 transition-opacity duration-200"
          key={activeTab}
        >
          {activeTab === "home" ? <MidShiftView /> : <PostTripView />}
        </div>
      </main>

      {/* ── Bottom Navigation (mobile only) ────────────────────────── */}
      <nav
        className="fixed bottom-0 left-1/2 z-40 w-full -translate-x-1/2 border-t border-[#141414] bg-[#0a0a0a]/90 backdrop-blur-xl lg:hidden"
        aria-label="Main navigation"
      >
        <div className="flex relative max-w-[600px] mx-auto">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={[
                  "flex flex-1 flex-col items-center gap-1 py-3 min-h-[56px]",
                  "transition-all duration-200 relative",
                  isActive
                    ? "text-[#276EF1]"
                    : "text-[#444] hover:text-[#888] active:text-white",
                ].join(" ")}
                aria-label={`${tab.label} tab`}
                aria-current={isActive ? "page" : undefined}
              >
                {isActive && (
                  <span className="absolute top-0 left-1/2 -translate-x-1/2 h-[2px] w-10 rounded-full bg-[#276EF1] transition-all duration-300" />
                )}
                <Icon size={20} aria-hidden />
                <span className="text-[10px] font-semibold">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
