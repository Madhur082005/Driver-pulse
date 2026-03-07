import type {
  TripSummary,
  FlaggedMoment,
  EarningsLog,
  ShiftData,
  PaceStatus,
} from "./types";

// ─── Shift Data ──────────────────────────────────────────────────────────────

export const shiftData: ShiftData = {
  currentEarnings: 127.5,
  earningsGoal: 200,
  hoursWorked: 4.5,
  totalHours: 8,
  currentVelocity: 28.33,
  requiredVelocity: 25.0,
  tripsCompleted: 9,
};

export function getPaceStatus(shift: ShiftData): PaceStatus {
  const ratio = shift.currentVelocity / shift.requiredVelocity;
  if (ratio >= 1.08) return "ahead";
  if (ratio >= 0.92) return "on-track";
  return "behind";
}

// ─── Earnings Timeline ───────────────────────────────────────────────────────

export const earningsLog: EarningsLog[] = [
  { timestamp: "4 PM", earnings: 0 },
  { timestamp: "5 PM", earnings: 24 },
  { timestamp: "6 PM", earnings: 52 },
  { timestamp: "7 PM", earnings: 78 },
  { timestamp: "8 PM", earnings: 105 },
  { timestamp: "8:30", earnings: 127.5 },
];

// ─── Trips ───────────────────────────────────────────────────────────────────

export const trips: TripSummary[] = [
  {
    tripId: "trip-001",
    duration: "22 min",
    fare: 18.5,
    qualityScore: 68,
    route: "Market St → 3rd Ave → Pine St",
    startTime: "7:12 PM",
    endTime: "7:34 PM",
    distance: "8.3 mi",
  },
  {
    tripId: "trip-002",
    duration: "28 min",
    fare: 32.0,
    qualityScore: 96,
    route: "Pine St → I-5 → Airport Terminal",
    startTime: "7:40 PM",
    endTime: "8:08 PM",
    distance: "14.1 mi",
  },
];

// ─── Flagged Moments (keyed by tripId) ───────────────────────────────────────

export const flaggedMoments: Record<string, FlaggedMoment[]> = {
  "trip-001": [
    {
      id: "evt-1",
      timestamp: "7:18 PM",
      eventType: "Harsh Braking",
      severity: "High",
      maxJerk: 4.5,
      avgAudio: 62,
      description: "Sudden stop at red light — vehicle ahead braked unexpectedly.",
      tripProgress: 27,
    },
    {
      id: "evt-2",
      timestamp: "7:21 PM",
      eventType: "Audio Spike",
      severity: "Medium",
      maxJerk: 1.2,
      avgAudio: 88,
      description: "Elevated cabin noise detected — possible passenger dispute.",
      tripProgress: 42,
    },
    {
      id: "evt-3",
      timestamp: "7:26 PM",
      eventType: "Conflict",
      severity: "Medium",
      maxJerk: 0.8,
      avgAudio: 85,
      description: "Sustained elevated audio with sharp tone indicators.",
      tripProgress: 63,
    },
    {
      id: "evt-4",
      timestamp: "7:31 PM",
      eventType: "Harsh Braking",
      severity: "Medium",
      maxJerk: 3.2,
      avgAudio: 58,
      description: "Moderate braking event entering construction zone.",
      tripProgress: 86,
    },
  ],
  "trip-002": [], // Clean trip → triggers empty state
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

export function getEventDistribution(events: FlaggedMoment[]) {
  const counts: Record<string, number> = {};
  events.forEach((e) => {
    counts[e.eventType] = (counts[e.eventType] || 0) + 1;
  });
  return Object.entries(counts).map(([name, value]) => ({ name, value }));
}

export function getStarRating(score: number): number {
  if (score >= 90) return 5;
  if (score >= 75) return 4;
  if (score >= 60) return 3;
  if (score >= 40) return 2;
  return 1;
}

export const EVENT_COLORS: Record<string, string> = {
  "Harsh Braking": "#E54937",
  "Audio Spike": "#FFC043",
  Conflict: "#276EF1",
};
