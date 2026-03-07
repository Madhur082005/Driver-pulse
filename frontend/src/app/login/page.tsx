"use client";

import { signIn } from "next-auth/react";
import { Activity } from "lucide-react";

export default function LoginPage() {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-black px-4">
      <div className="w-full max-w-[380px] rounded-3xl border border-[#1f1f1f] bg-[#0a0a0a] p-8 shadow-2xl shadow-black/60">
        {/* ── Branding ─────────────────────────────────────────── */}
        <div className="flex flex-col items-center text-center">
          <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-[#276EF1]">
            <Activity size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            Driver Pulse
          </h1>
          <p className="mt-2 text-sm font-medium uppercase tracking-[0.2em] text-[#555]">
            Live Shift Intelligence
          </p>
        </div>

        {/* ── Divider ──────────────────────────────────────────── */}
        <div className="my-8 h-px bg-[#1f1f1f]" />

        {/* ── Google Sign-In ───────────────────────────────────── */}
        <button
          onClick={() => signIn("google", { callbackUrl: "/" })}
          className="group flex w-full items-center justify-center gap-3 rounded-2xl bg-white px-6 py-4 text-[15px] font-semibold text-black transition-all duration-200 hover:bg-gray-100 active:scale-[0.98] min-h-[56px]"
        >
          {/* Google "G" icon */}
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            className="shrink-0"
          >
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              fill="#EA4335"
            />
          </svg>
          Continue with Google
        </button>

        {/* ── Footer ───────────────────────────────────────────── */}
        <p className="mt-6 text-center text-[11px] text-[#444] leading-relaxed">
          By continuing, you agree to Driver Pulse&apos;s{" "}
          <span className="text-[#555] underline underline-offset-2 cursor-pointer">
            Terms of Service
          </span>{" "}
          and{" "}
          <span className="text-[#555] underline underline-offset-2 cursor-pointer">
            Privacy Policy
          </span>
        </p>
      </div>
    </div>
  );
}
