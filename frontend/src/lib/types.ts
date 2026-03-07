// ─── Core TypeScript Models (matching Python edge-processing backend) ────────

export interface TripSummary {
  tripId: string;
  duration: string;
  fare: number;
  qualityScore: number;
  route: string;
  startTime: string;
  endTime: string;
  distance: string;
}

export interface FlaggedMoment {
  id: string;
  timestamp: string;
  eventType: "Harsh Braking" | "Audio Spike" | "Conflict";
  severity: "Medium" | "High";
  maxJerk: number;
  avgAudio: number;
  description: string;
  tripProgress: number; // 0–100, percent into trip
}

export interface EarningsLog {
  timestamp: string;
  earnings: number;
}

// ─── App-Level Types ─────────────────────────────────────────────────────────

export type PaceStatus = "ahead" | "on-track" | "behind";

export interface ShiftData {
  currentEarnings: number;
  earningsGoal: number;
  hoursWorked: number;
  totalHours: number;
  currentVelocity: number;
  requiredVelocity: number;
  tripsCompleted: number;
}

export type TabId = "home" | "trips";
