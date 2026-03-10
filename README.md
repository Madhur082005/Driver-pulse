# Driver Pulse — Real-Time Safety & Earnings Intelligence for Uber Drivers

A lightweight, edge-first system that turns raw phone sensor data into actionable safety alerts and earnings coaching for ride-hailing drivers — in real time, with no extra hardware.


Deployed Link : https://driver-pulse-seven.vercel.app/
---
Video Link : https://drive.google.com/drive/folders/1bbtQc2DY_bd0nG73F-7sbb9rOrauC8-w?usp=sharing
---
Github : https://github.com/Madhur082005/Driver-pulse

---

## Table of Contents

1. [Why This Exists](#1-why-this-exists)
2. [How It Helps Uber Drivers](#2-how-it-helps-uber-drivers)
3. [System Architecture](#3-system-architecture)
4. [Backend Module Deep-Dive](#4-backend-module-deep-dive)
5. [Earnings Intelligence Engine](#5-earnings-intelligence-engine)
6. [Data Flow & Sensor Pipeline](#6-data-flow--sensor-pipeline)
7. [Scalability Design](#7-scalability-design)
8. [Running Locally](#8-running-locally)
9. [Project Structure](#9-project-structure)
10. [Tech Stack](#10-tech-stack)

---

## 1. Why This Exists

Uber drivers in cities like Mumbai face a compounding problem:

| Pain Point | What Happens Today |
|---|---|
| **No safety feedback** | A driver hard-brakes 20 times a shift but never knows it's abnormal |
| **Earnings anxiety** | "Am I on pace?" has no answer until the shift is over |
| **Opaque scoring** | Platform ratings feel like a black box |
| **No real-time coaching** | Post-shift reports are too late to change behaviour |

Driver Pulse solves this by running **on the phone sensors you already have** — accelerometer, microphone, GPS — and producing per-second safety classifications + per-trip earnings intelligence, streamed live to a dashboard.

No wearables. No dashcams. No OBD dongles. **Just the phone.**

---

## 2. How It Helps Uber Drivers

### Safety Layer — "What just happened?"

- **Braking & cornering detection**: Classifies every accelerometer reading into `emergency_stop`, `harsh_brake`, `moderate_brake`, `soft_brake`, `harsh_corner`, or `normal`.  Speed-delta validation ensures potholes don't get flagged as braking.
- **Audio stress monitoring**: Sustained loud in-cabin audio (arguments, road rage) is detected using duration-based classification, not raw decibel thresholds (which overlap too much between classes to be useful alone).
- **Conflict fusion**: Motion + audio scores are fused into a single conflict score. When both channels fire simultaneously (e.g., hard brake + shouting), a dual-signal amplifier boosts severity — because real danger events almost always trigger multiple sensors.
- **Flagged moments timeline**: The dashboard shows a scrollable timeline of every flagged event with human-readable context ("Hard brake + Verbal conflict") so drivers can review their shift.

### Earnings Layer — "Am I on pace?"

- **Live earnings velocity**: Compares current ₹/hr against the target pace to answer "given how long I've driven, should I have earned more by now?"
- **Dynamic thresholds**: Instead of a fixed "you're behind by ₹100" cutoff, the threshold is personalised: 5% of the driver's own goal (clamped ₹50–₹250), or 10% of expected earnings so far — whichever is larger.  Small-goal drivers don't get over-penalised; large-goal drivers get more room for variance.
- **Gentle early-shift handling**: In the first hour, expectations are smoothly ramped from 80% to 100% of the linear pace.  This avoids panicking a driver who happened to get a short first trip.
- **End-of-shift projection**: "At your current pace, you'll finish the shift at ₹X" — capped at 2× the target to prevent one lucky trip from creating an unrealistic forecast.
- **Tonal alerts**: "Slightly behind" vs "Significantly behind" messages based on how far off-pace the driver actually is.

### Combined Value for the Driver

A typical shift with Driver Pulse active:

```
07:00  Shift starts.  System calibrates gravity offset from first 3
       stationary samples (phone is still during pickup).
07:02  Trip 1 begins.  Earnings tracker initialises at ₹0/₹2000 target.
07:06  Hard brake detected (5.5g Y-axis, speed drop -15 km/h).
       → Flagged as "harsh_braking", severity: medium.
07:12  Trip 1 ends.  ₹101 earned.  Status: on_track (too early to judge).
 ...
09:30  After 5 trips, driver is at ₹951.  Expected by now: ₹625.
       → Status: ahead.  Alert: "Great pace! You're ahead of target."
 ...
12:15  After 8 trips, driver is at ₹1356.  But traffic has been brutal.
       Projected finish: ₹1780.  Status: at_risk.
       → Alert: "You're slightly behind pace.  A couple of good trips
         can catch you up."
15:00  Shift ends.  Trip summary shows 4 flagged moments across 10 trips.
       Stress score: 0.31 (low).  Trip quality: 4/5 average.
```

---

## 3. System Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     PHONE (Edge)                           │
│                                                            │
│  Accelerometer ──┐                                         │
│  GPS/Speed ──────┤──▶ [ Gravity Compensator ]              │
│  Microphone ─────┘         │           │                   │
│                    ┌───────┘           └──────┐            │
│                    ▼                          ▼            │
│           [ Motion Classifier ]     [ Audio Classifier ]   │
│              score 0–1                  score 0–1          │
│                    │                          │            │
│                    └──────────┬───────────────┘            │
│                               ▼                            │
│                    [ Conflict Fusion Engine ]               │
│                       severity level                       │
│                               │                            │
│            ┌──────────┬───────┴───────┬──────────┐           │
│            ▼          ▼              ▼          ▼           │
│         HIGH      MEDIUM          LOW        SAFE         │
│        (≥0.75)    (≥0.45)        (≥0.25)    (<0.25)       │
│            └─────────┴──────────────┴──────────┘           │
│                               │                            │
│                     Flagged events sent                    │
│                     to backend via SSE                     │
└───────────────────────────┬────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                        │
│                                                            │
│   /api/sensor/demo  ──▶  SSE stream of classified events   │
│   /api/earnings/goal ──▶ Earnings velocity + alert          │
│                                                            │
│   Logs: sensor_stream.csv, flagged_moments.csv,            │
│         trip_summaries.csv, earnings_log.csv                │
└───────────────────────────┬────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                   FRONTEND (Next.js)                       │
│                                                            │
│   Live Dashboard: G-Score timeline, earnings chart,        │
│   flagged moments feed, trip summary cards                 │
└────────────────────────────────────────────────────────────┘
```

### Why edge-first?

The classifiers (`motion.py`, `audio.py`, `gravity.py`, `fusion.py`) are designed to run **on the phone itself**:

- **O(1) per sample** — no rolling windows, no ML models, no matrix ops.
- **< 500 bytes of state** per classifier instance.
- **No dependencies** beyond basic arithmetic.
- The phone only uploads **flagged events**, not raw sensor streams — saving 95%+ of bandwidth.

The backend exists for the **demo** and for aggregation/analytics.  In production, the phone would run these classifiers locally and upload only the fusion results.

---

## 4. Backend Module Deep-Dive

### 4.1 `heuristics/gravity.py` — Gravity Compensation

**Problem**: A phone mounted on a car dashboard is tilted. The Z-axis accelerometer reads ~9.74g, not 9.81g. Without compensation, every sample has a constant offset that corrupts motion detection.

**Solution**: Standard zero-g offset removal.

```
compensated = raw_reading - baseline
```

- **Calibration**: Collects the first 3 samples where `speed < 2 km/h` (stationary at pickup) and averages them to establish the per-axis baseline.
- **Fallback**: If calibration hasn't completed yet, uses `9.742g` (dataset mean) as the Z baseline.
- **State**: 3 floats (baseline_x, baseline_y, baseline_z) + 1 bool. ~100 bytes total.

### 4.2 `heuristics/motion.py` — Braking & Cornering Classifier

**Thresholds** (derived from dataset percentile analysis):

| Event | Y-axis threshold | Speed-delta gate | Score |
|---|---|---|---|
| Emergency stop | ≥ 4.0g | ≤ -15 km/h | 1.00 |
| Harsh brake | ≥ 2.8g | ≤ -10 km/h | 0.82 |
| Moderate brake | ≥ 1.8g | ≤ -5 km/h | 0.48 |
| Soft brake | ≥ 1.6g | *(none)* | 0.20 |
| Harsh corner | ≥ 3.5g (X-axis) | — | 0.85 |
| Moderate corner | ≥ 2.8g (X-axis) | — | 0.50 |

**Key design decision — Speed-delta validation**: A large Y-axis spike without a corresponding speed drop is a pothole or road bump, not braking.  This single check eliminates the #1 source of false positives in accelerometer-based systems.  Soft brakes (1.6g) intentionally skip this gate because the deceleration is gentle enough to occur without a dramatic speed change (e.g., rolling to a stop at a signal).

**Stateless**: Each sample is classified independently. O(1), no rolling windows.

### 4.3 `heuristics/audio.py` — Audio Stress Classifier

**Key insight from data**: Decibel ranges overlap completely across all audio classes (50–98 dB for both "quiet" and "argument").  dB level alone is **useless** as a discriminator.

**The only reliable signal is `sustained_duration_sec`**:
- `quiet / normal / conversation / loud` → sustained = 0
- `very_loud` → sustained > 0 (mean 78s)
- `argument` → sustained > 0 (mean 101s)

| Classification | Gate | Score |
|---|---|---|
| Argument | sustained ≥ 90s AND dB ≥ baseline + 10 | 0.92 |
| Very loud | sustained ≥ 50s | 0.65 |
| Elevated | sustained > 0 | 0.35 |
| Background | sustained = 0 | 0.00 |

**Baseline calibration**: Averages dB readings from the first 60 seconds of driving to establish a per-trip baseline.  The `argument` classification then requires dB to be at least 10 above this baseline — preventing a noisy car from being classified as an argument.

### 4.4 `heuristics/fusion.py` — Conflict Fusion Engine

Combines motion and audio scores into a single conflict score:

```
conflict = (motion_score × 0.55) + (audio_score × 0.45)

if motion ≥ 0.6 AND audio ≥ 0.6:
    conflict = min(conflict × 1.3, 1.0)    ← dual-signal amplifier
```

**Why 55/45 weighting?**  Motion events (braking, cornering) are more mechanically dangerous and more reliably measurable than audio.  But audio captures an entirely different risk dimension (interpersonal conflict, road rage) that motion can't see.  The weights reflect this asymmetry.

**Dual-signal amplifier**: When *both* channels fire above 0.6, the combined score is boosted by 30%.  This is because real danger events (e.g., argument escalating to dangerous driving) almost always trigger both sensors simultaneously.

**Severity thresholds**:

| Severity | Conflict score | Action |
|---|---|---|
| HIGH | ≥ 0.75 | Immediate alert |
| MEDIUM | ≥ 0.45 | Flagged for review |
| LOW | ≥ 0.25 | Logged |
| SAFE | < 0.25 | Discarded |

### 4.5 `heuristics/demo_stream.py` — Synthetic Data Generator

Generates a realistic 10-trip Mumbai Uber driver shift with controlled anomaly injection:

- **Base signals**: Gaussian noise around realistic baselines (speed 36 km/h, audio 52 dB, gravity 9.81g).
- **Anomaly injection**: Each trip has one defined anomaly type (door slam, hard brake, pothole, etc.) injected at 40% through the trip at precise array indices.
- **Stationary warmup**: Every trip starts with 3 samples at speed 0.0 km/h (simulating passenger pickup), which also provides gravity calibration samples.
- **Cross-trip isolation**: `prev_speed` and `sustained_loud_sec` are reset at trip boundaries to prevent state leakage (e.g., a trip ending at 60 km/h doesn't create a phantom harsh-brake at the start of the next trip).
- **Earnings accumulation**: Fare is distributed uniformly across trip samples, with a safety cap at 2.5× target earnings.

---

## 5. Earnings Intelligence Engine

> File: `services/earnings_engine.py`

### Core Question

*"Given how long this driver has worked so far, are they **ahead**, **on track**, or **at risk** of missing their daily earnings goal?"*

### The Math (step by step)

**Step 1 — Target velocity:**
```
target_velocity = target_earnings / target_hours     (₹/hour)
```

**Step 2 — Expected earnings by now:**
```
expected = target_velocity × current_hours
```
In the first hour, this is smoothly scaled down (80% → 100% linear ramp) to avoid flagging a new shift as "at risk" due to natural variance.

**Step 3 — Earnings gap:**
```
velocity_delta = current_earnings - expected         (₹)
```
Positive = ahead of pace.  Negative = behind pace.

**Step 4 — Dynamic threshold:**
```
absolute_threshold = clamp(target × 0.05, ₹50, ₹250)
relative_threshold = |expected| × 0.10

dynamic_threshold = max(absolute, relative)
```
This ensures small-goal drivers (₹500 target) aren't panicked by a ₹30 dip, while large-goal drivers (₹5000 target) have proportionally more room.

**Step 5 — Status classification:**
```
if gap ≥ +threshold       → "ahead"
if gap ≤ -threshold
   AND hours ≥ 1.0        → "at_risk"
else                       → "on_track"
```
The 1-hour minimum for "at_risk" prevents false alarms during the warm-up period.

**Step 6 — End-of-shift projection:**
```
projected = current_earnings + remaining_hours × current_velocity
         = clamped to [0, target × 2.0]
```

### Alert Tone

| Status | Message |
|---|---|
| Ahead | "Great pace! You're ahead of target." |
| On track | "You're on track. Keep going." |
| At risk (< 10% behind) | "You're slightly behind pace. A couple of good trips can catch you up." |
| At risk (> 10% behind) | "You're significantly behind pace. Consider moving to a high-demand area." |

---

## 6. Data Flow & Sensor Pipeline

### Per-sample flow (1 Hz in production, 1 per minute in demo mode)

```
Raw sensor reading
    │
    ├──▶ GravityCompensator.feed(ax, ay, az, speed)
    │        └─▶ .compensate(ax, ay, az) → (cx, cy, cz)
    │
    ├──▶ classify_motion(cy, cx, speed, prev_speed) → MotionResult
    │
    ├──▶ AudioClassifier.classify(db, sustained_sec, elapsed) → AudioResult
    │
    └──▶ fuse(motion_result, audio_result) → FusionResult
              │
              ├── severity: "high" | "medium" | "low" | "safe"
              ├── conflict: 0.0 – 1.0
              └── flag_type: "harsh_braking" | "conflict_moment" | ...
```

### Output artifacts

| File | Purpose | Written by |
|---|---|---|
| `sensor_stream.csv` | Complete per-sample log with all raw + classified fields | `demo_stream.py` |
| `flagged_moments.csv` | Only flagged events (severity ≥ low) with explanations | `demo_stream.py` |
| `trip_summaries.csv` | Per-trip aggregates (duration, fare, event counts, stress score) | `demo_stream.py` |
| `earnings_log.csv` | Per-checkpoint earnings evaluation log | `earnings_router.py` |

---

## 7. Scalability Design

### Edge-first architecture (the key insight)

The most expensive part of any real-time sensor system is **data transfer**.  A phone generating 1 Hz accelerometer + audio data produces ~500 KB/hour of raw data.  Multiply by 5 million active Uber drivers and you need **2.5 TB/hour** of ingestion bandwidth.

Driver Pulse solves this by classifying **on the phone**:

| Approach | Data uploaded per driver per hour |
|---|---|
| Raw sensor stream | ~500 KB |
| **Driver Pulse (flagged events only)** | **~2–5 KB** (99%+ reduction) |

The classifiers are designed for this:
- **O(1) per sample** — no FFTs, no ML inference, no rolling windows.
- **< 500 bytes total state** — fits in L1 cache.
- **No dependencies** — pure arithmetic, portable to any language.

### Severity-based event handling

Not all events are equally important:

| Severity | What it means | Example |
|---|---|---|
| HIGH (≥0.75) | Safety-critical, needs immediate attention | Hard brake during an argument |
| MEDIUM (≥0.45) | Notable event, worth reviewing | Isolated harsh brake |
| LOW (≥0.25) | Informational, logged for patterns | Elevated cabin noise |
| SAFE (<0.25) | Normal driving, discarded | Routine lane change |

In a production system, the phone would send only HIGH + MEDIUM events in real-time and batch LOW events periodically — reducing bandwidth by 95%+.

### Horizontal scaling on the backend

The backend is stateless per-request (FastAPI):

```
                    ┌─────────────┐
                    │  Load       │
                    │  Balancer   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         [ FastAPI ]  [ FastAPI ]  [ FastAPI ]
         instance 1   instance 2   instance N
              │            │            │
              └────────────┼────────────┘
                           ▼
                    ┌─────────────┐
                    │  Time-series│
                    │  Database   │
                    │  (InfluxDB/ │
                    │  TimescaleDB)│
                    └─────────────┘
```

- **No in-memory state** needed between requests (each event is self-contained).
- CSV logging is a demo convenience; production would use a time-series database.
- The SSE endpoint (`/api/sensor/demo`) is for live demos only; production would use a message queue (Kafka/Redis Streams).

### Scaling numbers

| Scale | Drivers | Events/sec | Backend instances | Bandwidth |
|---|---|---|---|---|
| City pilot (Mumbai) | 10,000 | ~500 flagged/sec | 2–3 | ~50 KB/s |
| Country (India) | 500,000 | ~25,000 flagged/sec | 15–20 | ~2.5 MB/s |
| Global | 5,000,000 | ~250,000 flagged/sec | 100+ | ~25 MB/s |

These are flagged-events-only numbers (after edge classification).  Raw sensor streams would be 100× higher.

### Database design for scale

```sql
-- Partitioned by driver_id + time for fast lookups
CREATE TABLE flagged_events (
    event_id        UUID PRIMARY KEY,
    driver_id       TEXT NOT NULL,
    trip_id         TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    severity        TEXT NOT NULL,       -- "high" | "medium" | "low"
    conflict_score  FLOAT NOT NULL,
    motion_type     TEXT,
    audio_type      TEXT,
    flag_type       TEXT,
    context         TEXT
) PARTITION BY RANGE (timestamp);

-- Index for per-driver timeline queries
CREATE INDEX idx_driver_time ON flagged_events (driver_id, timestamp DESC);
```

---

## 8. Running Locally

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm or yarn

### Backend

```bash
cd Driver-pulse/backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt
pip install numpy              # required for demo stream

# Start the server
uvicorn main:app --reload --port 8000
```

The backend exposes:
- `GET  /api/sensor/demo?interval=0.05` — SSE stream of synthetic demo data
- `POST /api/earnings/goal` — Evaluate an earnings checkpoint

### Frontend

```bash
cd Driver-pulse/frontend

npm install
npm run dev
```

Opens at `http://localhost:3000`.  The dashboard auto-connects to the backend SSE stream.

---

## 9. Project Structure

```
Driver-pulse/
├── backend/
│   ├── main.py                         # FastAPI app, CORS, route mounting
│   ├── requirements.txt                # Python dependencies
│   ├── EARNINGS_SYSTEM.md              # Detailed earnings engine documentation
│   │
│   ├── heuristics/                     # Edge-runnable classifiers
│   │   ├── gravity.py                  #   Gravity offset compensation
│   │   ├── motion.py                   #   Braking & cornering classifier
│   │   ├── audio.py                    #   Audio stress classifier
│   │   ├── fusion.py                   #   Conflict score fusion engine
│   │   └── demo_stream.py             #   Synthetic data generator + SSE stream
│   │
│   ├── services/
│   │   └── earnings_engine.py          # Earnings velocity evaluation
│   │
│   ├── routers/
│   │   └── earnings_router.py          # /api/earnings/goal endpoint
│   │
│   ├── schemas/
│   │   └── goal_schema.py              # Pydantic model for earnings payload
│   │
│   └── utils/
│       └── alert_builder.py            # Human-readable alert text generation
│
├── frontend/                           # Next.js 16 dashboard
│   ├── src/
│   │   ├── app/page.tsx                # Main dashboard page
│   │   ├── components/                 # Charts, timeline, UI components
│   │   └── lib/types.ts                # TypeScript type definitions
│   └── package.json
│
└── Data/                               # Reference datasets
    ├── drivers/drivers.csv             # 10 demo driver profiles
    ├── earnings/                       # Goal progress + velocity logs
    ├── sensor_data/                    # Accelerometer + audio CSVs
    ├── trips/trips.csv                 # Trip metadata
    └── flagged_moments.csv             # Pre-generated flagged events
```

---

## 10. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | FastAPI + Uvicorn | Async, fast, great for SSE streaming |
| **Classifiers** | Pure Python + NumPy | Edge-portable, no ML dependencies |
| **Frontend** | Next.js 16 + React 19 | Server components, fast hydration |
| **Charts** | Recharts | Composable, React-native charting |
| **Styling** | Tailwind CSS v4 | Utility-first, rapid iteration |
| **Data validation** | Pydantic v2 | Type-safe API contracts |
