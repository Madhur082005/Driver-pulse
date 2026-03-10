# Driver Pulse — Hackathon Progress Log

**Team**: Hansuja  
**Project**: Driver Pulse — Real-Time Safety & Earnings Intelligence for Uber Drivers  
**Duration**: March 4 – March 10, 2026 (7 days)

---

## Day 1 — March 4 (Tuesday)
### Research & Dataset Analysis

**Objective**: Understand the raw data & define what's solvable.

**Work completed**:
- Analyzed the raw datasets: `accelerometer_data.csv` (17 KB), `audio_intensity_data.csv` (14 KB), `trips.csv` (20 KB), `drivers.csv` (12 KB)
- Key discovery: **dB ranges overlap completely** across all audio classes (50–98 dB for both "quiet" and "argument"). Decibel level alone is useless — `sustained_duration_sec` is the *only* reliable discriminator
- Computed accelerometer percentiles for braking detection:
  - `accel_y` (braking): p80 = 1.60g, p90 = 1.80g, p95 = 2.00g, harsh mean = 3.24g
  - `accel_x` (cornering): p80 = 2.60g, p90 = 2.80g, p95 = 2.90g, harsh mean = 4.30g
- Identified gravity offset problem: stationary Z-axis reads ~9.742g, not 9.81g (phone tilt)
- Defined the CMBI framework scope: Classify → Monitor → Broadcast → Intervene
- Decided on **edge-first architecture**: classifiers run on phone, only flagged events sent to server

**Key decisions**:
- No ML models — pure threshold-based classification (O(1) per sample, < 500 bytes state)
- Speed-delta validation for braking: large Y-axis spike without speed drop = pothole, not braking
- Weighted fusion: motion 55% + audio 45% (motion is more mechanically dangerous and measurable)

---

## Day 2 — March 5 (Wednesday)
### Motion & Audio Classifiers

**Objective**: Build the two core classifiers from the dataset insights.

**Work completed**:
- **`heuristics/motion.py`** — Braking & cornering classifier
  - 6 event types: emergency_stop, harsh_brake, moderate_brake, soft_brake, harsh_corner, moderate_corner
  - Speed-delta gates for emergency/harsh/moderate braking to eliminate false positives from potholes
  - Soft brakes (≥ 1.6g) intentionally skip the speed-delta gate — the deceleration is gentle enough to occur without a dramatic speed change
  - All thresholds derived from dataset percentile analysis

- **`heuristics/audio.py`** — Audio stress classifier
  - Sustained-duration-only approach after proving dB is unreliable as a standalone discriminator
  - Baseline calibration from first 60 seconds of driving
  - 4 classifications: background, elevated, very_loud, argument
  - Argument requires sustained ≥ 90s AND dB ≥ baseline + 10 (dual gate prevents false positives)

- **`heuristics/gravity.py`** — Gravity compensator
  - Simple per-axis mean subtraction from stationary samples
  - Calibrates from first 3 samples where speed < 2 km/h
  - Fallback to dataset mean (9.742g) if calibration hasn't triggered

**Lines of code**: ~270 across 3 files  
**Tests**: Manual validation against dataset edge cases

---

## Day 3 — March 6 (Thursday)
### Fusion Engine & Backend Structure

**Objective**: Combine motion + audio into a single conflict score and set up the FastAPI backend.

**Work completed**:
- **`heuristics/fusion.py`** — Conflict fusion engine
  - Weighted sum: `conflict = (motion × 0.55) + (audio × 0.45)`
  - Dual-signal amplifier: when both scores ≥ 0.6, boost by 1.3× (capped at 1.0)
  - 4 severity levels: HIGH (≥0.75), MEDIUM (≥0.45), LOW (≥0.25), SAFE (<0.25)
  - Flag type resolution: motion-first, fall back to audio

- **Backend scaffolding**:
  - FastAPI app (`main.py`) with CORS for localhost:3000
  - Router/service/schema structure for earnings API
  - Pydantic model for GoalPayload

- **`heuristics/__init__.py`** — Clean module exports

**Lines of code**: ~190 across 4 files  
**Architecture decision**: Stateless per-request design for horizontal scalability

---

## Day 4 — March 7 (Friday)
### Demo Stream & SSE Pipeline

**Objective**: Build a realistic synthetic data generator and stream it via SSE.

**Work completed**:
- **`heuristics/demo_stream.py`** — Full demo data pipeline
  - 10-trip Mumbai Uber driver scenario with realistic anomaly injection
  - Anomaly types: door_slam, hard_brake, loud_passenger, pothole_jolt, conflict, rapid_brake_pair, device_tilt, stop_go_traffic
  - Per-sample pipeline: gravity → motion → audio → fusion → SSE emit
  - CSV logging for sensor_stream, flagged_moments, and trip_summaries
  - SSE endpoint: `GET /api/sensor/demo?interval=0.05`

- **Data realism**:
  - Gaussian baselines: speed ~36 km/h (σ=4), audio ~52 dB (σ=2), gravity ~9.81g (σ=0.15)
  - Anomalies injected at 40% into each trip (mid-ride, not at boundaries)
  - Stationary warmup at trip start (3 samples at speed 0) for gravity calibration
  - Trip fares designed to create an earnings narrative: behind → catching up → at risk → recovery

**Lines of code**: ~520  
**Result**: Full SSE stream of ~280 classified events per demo run

---

## Day 5 — March 8 (Saturday)
### Earnings Intelligence Engine

**Objective**: Build the "Am I on pace?" system with dynamic thresholds.

**Work completed**:
- **`services/earnings_engine.py`** — Core evaluation logic
  - Target velocity: `target_earnings / target_hours`
  - Expected earnings: linear pace × elapsed hours
  - Early-shift softening: smooth ramp from 80% → 100% over first hour (no discontinuity)
  - Dynamic threshold: `max(goal × 5%, expected × 10%)` clamped ₹50–₹250
  - Status classification: ahead / on_track / at_risk (at_risk only after 1 hour)
  - End-of-shift projection: `current + remaining × velocity`, capped at 2× target

- **`routers/earnings_router.py`** — POST endpoint
  - Accepts GoalPayload, evaluates, logs to CSV
  - Alert generation with status change detection (no duplicate alerts)

- **`utils/alert_builder.py`** — Tonal alert text
  - "Slightly behind" vs "Significantly behind" based on % gap
  - Three tones for three statuses

- **`EARNINGS_SYSTEM.md`** — Full documentation of the math

**Lines of code**: ~330 across 4 files  
**Documented formulas**: 6 steps with LaTeX equations

---

## Day 6 — March 9 (Sunday)
### Frontend Dashboard

**Objective**: Build a live dashboard that's fully backend-driven (zero hardcoded business values).

**Work completed**:
- **Next.js 16 + React 19** frontend scaffold
  - `page.tsx` — Single-page dashboard with 4 tabs: Dashboard, Flagged Events, Trip Summaries, Earnings
  - Every number, driver name, city, currency, threshold — all from SSE payload
  - Real-time SSE connection to backend

- **Dashboard tab**:
  - Status hero with dynamic color from earnings_engine status
  - 4 stat tiles: Earnings Now, Projected End, Trips Completed, High Severity count
  - Progress bar with velocity metrics from evaluate_goal output
  - Recent flags list with severity badges

- **Flagged Events tab**:
  - 4-filter system: severity, trip, motion type, audio type (all populated from live data)
  - Icon system for motion/audio event types
  - Expandable detail cards with sensor readings, fusion scores, earnings snapshot at moment of flag

- **Trip Summaries tab**:
  - Per-trip cards with fare, distance, duration, event counts
  - Worst severity per trip, max conflict score

- **Earnings tab**:
  - SVG earnings chart with target/projected lines
  - Velocity metrics from backend

- **Design**: Dark mode, monospace accents, severity color palette (red/orange/yellow/green), glassmorphism cards

**Lines of code**: ~1,000 (page.tsx)  
**Design system**: Inline styles for zero-dependency artifact portability

---

## Day 7 — March 10 (Monday)
### Edge-Case Hardening, Bug Fixes & Documentation

**Objective**: Full mathematical audit, edge-case coverage, and production-ready README writeup.

**Work completed**:

### Code Fixes
| Fix | File | Impact |
|---|---|---|
| Gravity calibration: `== 0.0` → `< 2.0 km/h` | `gravity.py` | Calibration actually triggers now (GPS rarely reports exact 0) |
| Stationary warmup at trip start | `demo_stream.py` | Realistic (pickup) + enables gravity calibration |
| Reset `prev_speed` per trip | `demo_stream.py` | Prevents phantom harsh-brake at trip boundaries |
| Reset `sustained_loud_sec` per trip | `demo_stream.py` | Prevents inflated audio at trip boundaries |
| Bounds guard on `rapid_brake_pair` | `demo_stream.py` | Prevents crash on short trips |
| Smooth early-shift ramp (0.8→1.0) | `earnings_engine.py` | Eliminates discontinuity at 1 hour |
| Document `soft_brake` no-gate | `motion.py` | Prevents confusion about intentional design |
| Clarify `velocity_delta` naming | `earnings_engine.py` | API compatibility note |
| Fix `hard_brake` speed-delta | `demo_stream.py` | Was broken: speed set high at brake sample → positive delta → classified as road_noise |
| Fix `conflict` dual-signal | `demo_stream.py` | Audio now starts 2 samples before brake → argument + harsh_brake at same sample → HIGH via amplifier |
| Fix `rapid_brake_pair` speed-delta | `demo_stream.py` | Both brakes now have proper speed drops |
| Remove `upload_tier` references | `fusion.py`, `demo_stream.py`, `page.tsx`, `README.md` | Clean up unused concept |

### Documentation
- **Comprehensive `README.md`** (500+ lines):
  - System architecture with ASCII diagrams
  - Module-by-module math documentation
  - Scalability analysis with bandwidth savings
  - Running locally instructions
  - Project structure
- **Backend analysis artifact** with full mathematical audit

### Bug discovered & fixed
The most impactful bug: **3 of 5 anomaly types were silently failing**.
- `hard_brake`, `conflict`, and `rapid_brake_pair` all injected Y-axis spikes without manipulating speed
- The speed-delta gate in `motion.py` then classified them as `road_noise` (score 0.05)
- Result: almost no MEDIUM or HIGH severity events in the entire demo
- Fix: each anomaly now properly sets speed high BEFORE and low AT the onset sample

**Total lines changed today**: ~200 across 6 files

---

## Final Stats

| Metric | Value |
|---|---|
| **Total backend code** | ~1,100 lines across 9 files |
| **Total frontend code** | ~1,000 lines (single page.tsx) |
| **Hardcoded business values in frontend** | 0 |
| **Edge classifiers — state per instance** | < 500 bytes |
| **Edge classifiers — complexity per sample** | O(1) |
| **Demo events per run** | ~280 classified samples |
| **Severity levels generated** | HIGH, MEDIUM, LOW (verified) |
| **Bandwidth savings (edge vs raw)** | 99%+ |

---

## Architecture Summary

```
Phone Sensors → Gravity Comp → Motion + Audio → Fusion → Severity
                                                           ↓
                                              SSE to Backend → Dashboard
                                                           ↓
                                              Earnings Engine → Alerts
```

**Core insight**: By classifying on the phone and uploading only flagged events, we reduce data transfer from ~500 KB/hr to ~2-5 KB/hr per driver — making the system viable at global scale (5M+ drivers) without massive infrastructure.
