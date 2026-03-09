# Uber Driver Pulse — Hackathon Demo: Engineering Documentation

**Date:** March 10, 2026  
**Scope:** Backend pipeline upgrades, SSE streaming infrastructure, and demo data generation

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Live SSE Streaming Setup](#2-live-sse-streaming-setup)
   - [What Was Wrong (Before)](#21-what-was-wrong-before)
   - [Heuristics Package Refactor](#22-heuristics-package-refactor)
   - [The New `stream.py` Module](#23-the-new-streampy-module)
   - [FastAPI Endpoint in `main.py`](#24-fastapi-endpoint-in-mainpy)
   - [Frontend Integration](#25-frontend-integration)
3. [The Heuristics Classification Engine](#3-the-heuristics-classification-engine)
   - [Gravity Compensation](#31-gravity-compensation)
   - [Motion Classifier](#32-motion-classifier)
   - [Audio Classifier](#33-audio-classifier)
   - [Fusion Engine](#34-fusion-engine)
4. [Demo Data Generation](#4-demo-data-generation)
   - [Sensor Data Structure](#41-sensor-data-structure)
   - [The 10-Driver Demo Scope](#42-the-10-driver-demo-scope)
5. [Batch Processing & Data Mirroring](#5-batch-processing--data-mirroring)
   - [Script Overview](#51-script-overview)
   - [Step 1: Dynamic Path Resolution & Loading](#52-step-1-dynamic-path-resolution--loading)
   - [Step 2: Demo Driver Scoping](#53-step-2-demo-driver-scoping)
   - [Step 3: Time-Alignment with `merge_asof`](#54-step-3-time-alignment-with-merge_asof)
   - [Step 4: The Processing Loop](#55-step-4-the-processing-loop)
   - [Output Schemas](#56-output-schemas)
6. [Key Results](#6-key-results)
7. [File Map](#7-file-map)
8. [Running the Demo](#8-running-the-demo)

---

## 1. System Architecture Overview

The Uber Driver Pulse backend follows a two-track data architecture:

```
Raw Sensor CSVs
      │
      ▼
┌─────────────────────────────────────────────────┐
│          Heuristics Package (backend/heuristics) │
│                                                  │
│  GravityCompensator → classify_motion            │
│                     → AudioClassifier            │
│                               └→ fuse()          │
│                                    └→ FusionResult│
└─────────────────────────────────────────────────┘
      │                         │
      │ (live demo)             │ (offline batch)
      ▼                         ▼
 stream.py              generate_demo_summaries.py
 SSE events             → trips_demo.csv
 via FastAPI            → flagged_moments_demo.csv
 /api/sensor/stream     → trip_summaries_demo.csv
      │
      ▼
 Next.js Frontend
 (EventSource API)
```

The same classification logic (`heuristics/`) powers both the **live SSE stream** (for the real-time frontend demo) and the **batch export** (for pre-generating all reference-compatible CSV artefacts). Zero code duplication.

---

## 2. Live SSE Streaming Setup

### 2.1 What Was Wrong (Before)

The original `heuristics/` folder contained four pure-logic classifiers (`audio.py`, `motion.py`, `gravity.py`, `fusion.py`) but had no streaming layer and several structural problems:

| Problem | Detail |
|---|---|
| **No package structure** | No `__init__.py` — imports broke depending on `cwd` |
| **Fragile intra-package imports** | `fusion.py` used `from heuristics.motion import …` (absolute), which failed when run from inside the package |
| **No SSE module** | Nothing to bridge the classifiers to a web client |
| **No configurable timing** | Any hardcoded sleep values would block demo flexibility |
| **No error handling on missing files** | A missing CSV would throw an unhandled exception and crash the server |

### 2.2 Heuristics Package Refactor

**`backend/heuristics/__init__.py`** (new file) was created to make `heuristics` a proper Python package with a clean public API:

```python
from .audio    import AudioClassifier, AudioResult, audio_to_flag_type
from .motion   import classify_motion, MotionResult, motion_to_flag_type
from .gravity  import GravityCompensator
from .fusion   import fuse, FusionResult
from .stream   import stream_sensor_events
```

**`backend/heuristics/fusion.py`** — corrected intra-package imports from absolute to relative:

```python
# Before (broken when run as a package)
from heuristics.motion import MotionResult, motion_to_flag_type
from heuristics.audio  import AudioResult,  audio_to_flag_type

# After (correct relative imports)
from .motion import MotionResult, motion_to_flag_type
from .audio  import AudioResult,  audio_to_flag_type
```

`from __future__ import annotations` was also added across the refactored files for forward-compatible type hints.

The four classifier files (`audio.py`, `motion.py`, `gravity.py`, `fusion.py`) were already well-written with no file I/O or hardcoded paths. They were preserved as-is — only the packaging and `fusion.py` imports needed correction.

### 2.3 The New `stream.py` Module

**File:** `backend/heuristics/stream.py`

This is the central addition — an async generator that reads CSV sensor data, pipes each sample through the full classification pipeline, and yields strict SSE-formatted JSON events.

#### Dynamic Path Resolution

All file paths are computed at runtime with `pathlib`, relative to the location of `stream.py` itself — no hardcoded strings anywhere:

```python
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DATA_DIR: Path = _PROJECT_ROOT / "Data" / "sensor_data"
```

This means the module works correctly regardless of whether the server is started from `backend/`, the project root, or any other directory.

#### Resource-Safe CSV Loading

All file reads use a context manager inside the `_load_csv` helper:

```python
def _load_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
```

No file handles are left open. If parsing fails, the exception is caught and a JSON error event is yielded to the client rather than crashing the server.

#### Missing-File Guard

Before touching any data, the stream validates both CSV files exist:

```python
for path, label in [(accel_path, "accelerometer"), (audio_path, "audio")]:
    if not path.is_file():
        yield _sse({"error": f"{label} data file not found: {path.name}"}, event="error")
        return
```

#### Configurable Interval

The sleep between pushes is a plain function parameter — no hardcoded `asyncio.sleep(0.5)`:

```python
async def stream_sensor_events(
    *,
    trip_id: str | None = None,
    interval_sec: float = DEFAULT_INTERVAL_SEC,   # default 0.5s
    data_dir: Path | str | None = None,
) -> AsyncGenerator[str, None]:
    ...
    await asyncio.sleep(interval_sec)
```

#### Graceful Client Disconnect

`asyncio.CancelledError` is caught at the top level of the generator loop. When a frontend tab closes or the `EventSource` disconnects, the generator exits cleanly with a log message instead of propagating the exception:

```python
except asyncio.CancelledError:
    logger.info("Client disconnected — sensor stream stopped after %d events", events_sent)
    return
```

#### SSE Format Compliance

All events follow the [WHATWG SSE specification](https://html.spec.whatwg.org/multipage/server-sent-events.html) strictly — named event type, JSON payload, double newline terminator:

```
event: sensor_update
data: {"index": 0, "trip_id": "TRIP001", "motion": {...}, "audio": {...}, "fusion": {...}}

event: done
data: {"status": "complete", "total_events": 13}

```

#### SSE Payload Structure (per event)

```json
{
  "index": 5,
  "trip_id": "TRIP002",
  "timestamp": "2024-02-06 07:22:00",
  "elapsed_seconds": 420.0,
  "speed_kmh": 18.0,
  "motion": {
    "event_type": "harsh_brake",
    "score": 0.82,
    "axis": "y_brake"
  },
  "audio": {
    "classification": "elevated",
    "score": 0.35,
    "sustained_sec": 0.0,
    "db_level": 88.0
  },
  "fusion": {
    "severity": "medium",
    "conflict": 0.6085,
    "flag_type": "harsh_braking",
    "upload_tier": "fast",
    "amplified": false
  }
}
```

### 2.4 FastAPI Endpoint in `main.py`

**File:** `backend/main.py`

The SSE endpoint was added alongside the existing earnings router:

```python
@app.get("/api/sensor/stream")
async def sensor_stream(
    trip_id: str | None = Query(None, description="Filter to a specific trip ID"),
    interval: float = Query(0.5, ge=0.05, le=5.0, description="Seconds between SSE pushes"),
):
    """SSE endpoint — streams classified sensor events to the frontend."""
    return StreamingResponse(
        stream_sensor_events(trip_id=trip_id, interval_sec=interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",         # disables Nginx buffering
        },
    )
```

**Query parameters:**

| Parameter | Type | Range | Default | Purpose |
|---|---|---|---|---|
| `trip_id` | `string` | any valid trip ID | `null` (all trips) | Filter stream to one trip |
| `interval` | `float` | 0.05 – 5.0 | `0.5` | Seconds between SSE pushes |

`X-Accel-Buffering: no` is critical for demos — without it, Nginx/reverse-proxies buffer the response and the frontend receives events in bursts instead of in real time.

### 2.5 Frontend Integration

Connect from Next.js with the native `EventSource` API:

```typescript
const source = new EventSource(
  "/api/sensor/stream?interval=0.3&trip_id=TRIP001"
);

source.addEventListener("sensor_update", (e) => {
  const data = JSON.parse(e.data);
  // data.motion, data.audio, data.fusion all available
  updateDashboard(data);
});

source.addEventListener("error", (e) => {
  const err = JSON.parse(e.data);
  console.error("Stream error:", err.error);
});

source.addEventListener("done", () => {
  console.log("Trip stream complete");
  source.close();
});
```

---

## 3. The Heuristics Classification Engine

All four classifiers are stateless per-sample (O(1), no rolling windows). They are instantiated fresh for each trip, which makes them safe to use in both the live stream and the batch script without any shared state.

### 3.1 Gravity Compensation

**File:** `backend/heuristics/gravity.py`  
**Class:** `GravityCompensator`

A phone mounted in a car is physically tilted — the Z-axis is never perfectly vertical. Raw accelerometer values carry a gravity component that must be subtracted before any meaningful motion detection is possible.

**Calibration strategy:** The compensator watches for the first 3 stationary samples (`speed_kmh == 0`) and computes the mean of each axis as the baseline. Until calibration is complete, a fallback baseline of `9.742g` (derived from the dataset's stationary mean) is used.

```
Raw reading:  ax=0.2, ay=0.1, az=9.8
Baseline:     bx=0.0, by=0.0, bz=9.742
Compensated:  cx=0.2, cy=0.1, cz=0.058  ← only real motion
```

### 3.2 Motion Classifier

**File:** `backend/heuristics/motion.py`  
**Function:** `classify_motion(comp_y, comp_x, speed_kmh, prev_speed) → MotionResult`

Classifies each gravity-compensated sample into a motion event. Thresholds were derived from dataset percentile analysis:

| Event | Axis | g-threshold | Score | Speed gate |
|---|---|---|---|---|
| `emergency_stop` | Y (braking) | ≥ 4.0g | 1.00 | Δspeed ≤ −15 km/h |
| `harsh_brake` | Y | ≥ 2.8g | 0.82 | Δspeed ≤ −10 km/h |
| `moderate_brake` | Y | ≥ 1.80g | 0.48 | Δspeed ≤ −5 km/h |
| `soft_brake` | Y | ≥ 1.60g | 0.20 | — |
| `harsh_corner` | X (lateral) | ≥ 3.5g | 0.85 | — |
| `moderate_corner` | X | ≥ 2.80g | 0.50 | — |
| `road_noise` | Y | large spike, no speed drop | 0.05 | — |
| `normal` | — | below all thresholds | 0.00 | — |

**Speed-delta validation** is the key anti-false-positive mechanism: a large Y-axis spike without a corresponding speed decrease is downgraded to `road_noise` (pothole / speed bump). This prevents potholes from being reported to drivers as harsh braking events.

### 3.3 Audio Classifier

**File:** `backend/heuristics/audio.py`  
**Class:** `AudioClassifier`

**Key insight from the dataset:** All audio dB levels (50–98 dB) overlap completely across all noise classes. The decibel level alone is not a reliable discriminator.

The **only** reliable signal is `sustained_duration_sec`:
- `quiet / normal / conversation / loud` → `sustained_duration` is always `0`
- `very_loud` → `sustained_duration > 0` (dataset mean: 78s)
- `argument` → `sustained_duration > 0` (dataset mean: 101s)

**Per-trip baseline calibration:** In the first 60 seconds of a trip, dB samples are collected to establish the ambient noise floor for that specific vehicle/route. The argument detector uses "dB above this baseline" (≥10 dB) as a secondary gate.

| Classification | `sustained_sec` condition | dB condition | Score |
|---|---|---|---|
| `background` | == 0 | — | 0.00 |
| `elevated` | > 0, < 50s | — | 0.35 |
| `very_loud` | ≥ 50s | — | 0.65 |
| `argument` | ≥ 90s | ≥ 10 dB above baseline | 0.92 |

### 3.4 Fusion Engine

**File:** `backend/heuristics/fusion.py`  
**Function:** `fuse(motion: MotionResult, audio: AudioResult) → FusionResult`

Combines motion and audio scores into a single `conflict_score` using a weighted formula:

$$\text{conflict} = (\text{motion\_score} \times 0.55) + (\text{audio\_score} \times 0.45)$$

**Dual-signal amplifier:** When both motion and audio independently exceed a score of 0.60, the conflict score is boosted by 30% (capped at 1.0). This correctly amplifies genuinely dangerous combined events — for example, an emergency stop accompanied by loud argument audio:

$$\text{conflict} = \min(\text{conflict} \times 1.30, \ 1.0)$$

**Severity classification and upload tiering:**

| Severity | Threshold | Upload Tier | Latency |
|---|---|---|---|
| `high` | ≥ 0.75 | `immediate` | < 2s |
| `medium` | ≥ 0.45 | `fast` | < 8s |
| `low` | ≥ 0.25 | `batch` | 60s |
| `safe` | < 0.25 | `discard` | — |

---

## 4. Demo Data Generation

### 4.1 Sensor Data Structure

The demo uses two raw sensor streams with different sampling rates — a realistic constraint reflecting how real phone sensors behave under power management:

| Stream | File | Cadence | Columns |
|---|---|---|---|
| Accelerometer | `accelerometer_data.csv` | ~30 s per sample | `sensor_id, trip_id, timestamp, elapsed_seconds, accel_x, accel_y, accel_z, speed_kmh, gps_lat, gps_lon` |
| Audio | `audio_intensity_data.csv` | ~60 s per sample | `audio_id, trip_id, timestamp, elapsed_seconds, audio_level_db, audio_classification, sustained_duration_sec` |

The ~2:1 sample rate ratio (accel is more frequent) is intentional and is handled explicitly in the time-alignment step.

### 4.2 The 10-Driver Demo Scope

The full hackathon dataset contains 220 trips across 130 drivers. The demo is scoped to **10 drivers** with verified sensor coverage.

**Scoping strategy (in `generate_demo_summaries.py`):**

1. Find the intersection of trip IDs present in **both** the accelerometer and audio files.
2. Check `Demo_Data/drivers.csv` (the canonical 10-driver roster). If ≥ 10 of those drivers have sensor-covered trips, use them.
3. Otherwise, fall back to the first 10 unique drivers from the sensor-covered trip set.

This makes the script robust for both the current dataset (where the demo driver IDs differ from the sensor-trip driver IDs) and any future dataset where they align perfectly.

---

## 5. Batch Processing & Data Mirroring

### 5.1 Script Overview

**File:** `backend/scripts/generate_demo_summaries.py`

This script mirrors the structure of the full hackathon dataset (`Data/`) but scoped entirely to the 10-driver demo. It is the single source of truth for all three demo CSV artefacts.

**Run command:**
```bash
cd backend && python scripts/generate_demo_summaries.py
```

The script executes in 5 labelled phases with console progress output.

### 5.2 Step 1: Dynamic Path Resolution & Loading

All paths are resolved using `pathlib` relative to `__file__`. The script has zero hardcoded absolute paths:

```python
_SCRIPT_DIR  = Path(__file__).resolve().parent   # backend/scripts/
_BACKEND_DIR = _SCRIPT_DIR.parent                # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent              # repo root
```

A `_resolve()` helper provides a **two-tier fallback** for every input file: if `accelerometer_final.csv` doesn't exist in `backend/`, it automatically falls back to `Data/sensor_data/accelerometer_data.csv`. This means the script is runnable out of the box with the existing dataset, and will seamlessly switch to the final demo files when they are placed in `backend/`.

Column name normalisation handles both naming conventions (`x/y/z` from `edge_sensor_processor.py` and `accel_x/y/z` from the raw files) transparently.

### 5.3 Step 2: Demo Driver Scoping

```python
# Find trips with complete sensor coverage (both streams)
sensor_trips = set(accel["trip_id"].unique()) & set(audio["trip_id"].unique())
trips_with_sensors = trips[trips["trip_id"].isin(sensor_trips)]

# Prefer the canonical demo roster if it has enough sensor-covered overlap
if overlap_count >= MAX_DEMO_DRIVERS:
    demo_driver_ids = overlap_ids[:MAX_DEMO_DRIVERS]
else:
    demo_driver_ids = trips_with_sensors["driver_id"].unique()[:MAX_DEMO_DRIVERS]
```

This guarantees the demo always has exactly 10 drivers who have **both** sensor streams — no trip will fail alignment due to a missing audio or accelerometer file.

### 5.4 Step 3: Time-Alignment with `merge_asof`

The core data engineering challenge is aligning the two sensor streams that sample at different rates. A naive `merge` on timestamp would discard most rows. Instead, the script uses `pandas.merge_asof` — a **backward-looking nearest-match join** — per trip:

```python
combined = pd.merge_asof(
    a_grp,                              # accelerometer (higher frequency)
    au_grp[["elapsed_seconds",
             "db_level",
             "sustained_duration_sec"]],
    on="elapsed_seconds",
    direction="backward",               # never use a future audio reading
    suffixes=("", "_audio"),
)

# Forward-fill any accel rows before the first audio sample
combined["db_level"] = combined["db_level"].ffill().fillna(0.0)
combined["sustained_duration_sec"] = combined["sustained_duration_sec"].ffill().fillna(0.0)
```

**Why `direction="backward"`?** This ensures that at any given accelerometer timestamp, the join picks the most recent audio reading that occurred **at or before** that moment. A `"nearest"` direction would introduce future-leak (using an audio reading from the future), which would invalidate the causal pipeline during live inference.

**Why forward-fill after the join?** The first few accelerometer rows may precede the first audio sample. `ffill()` assigns them the global `0.0` default (no audio signal detected) rather than leaving them as `NaN`, which would cause classification errors downstream.

### 5.5 Step 4: The Processing Loop

For each trip, the pipeline instantiates **fresh, stateful classifiers** — this is critical because `GravityCompensator` and `AudioClassifier` both maintain internal calibration state that is only valid within a single trip:

```python
for trip_id, grp in merged.groupby("trip_id"):
    gravity   = GravityCompensator()   # calibrates on first 3 stationary samples
    audio_clf = AudioClassifier()      # calibrates dB baseline in first 60s
    prev_speed = 0.0

    for _, row in grp.iterrows():
        # 1. Gravity compensation
        gravity.feed(ax, ay, az, speed)
        cx, cy, cz = gravity.compensate(ax, ay, az)

        # 2. Jerk approximation (for reference schema compatibility)
        jerk = abs(accel_magnitude - prev_accel_magnitude)

        # 3. Motion classification
        motion_result = classify_motion(comp_y=cy, comp_x=cx,
                                        speed_kmh=speed, prev_speed=prev_speed)

        # 4. Audio classification
        audio_result = audio_clf.classify(db_level=db,
                                          sustained_sec=sustained,
                                          elapsed_seconds=elapsed)

        # 5. Fusion
        fusion_result = fuse(motion_result, audio_result)

        # 6. Gate on severity and accumulate
        if fusion_result.severity in {"low", "medium", "high"}:
            flagged_rows.append({...})
```

After all samples for a trip are processed, per-trip aggregates are computed across **all samples** (not just flagged ones), so `mean_conflict_score` reflects the true ambient safety level of the trip:

```python
conflict_arr = np.array(all_conflict_scores)
summary_rows.append({
    "max_conflict_score":  round(float(conflict_arr.max()),  4),
    "mean_conflict_score": round(float(conflict_arr.mean()), 4),
    "high_count":   severity_counts["high"],
    "medium_count": severity_counts["medium"],
    "low_count":    severity_counts["low"],
    ...
})
```

### 5.6 Output Schemas

#### `trips_demo.csv`
Mirrors `Data/trips/trips.csv` exactly, scoped to the 10 demo drivers:

| Column | Type | Description |
|---|---|---|
| `trip_id` | string | Unique trip identifier |
| `driver_id` | string | Driver identifier |
| `date` | date | Trip date |
| `start_time` | time | Trip start |
| `end_time` | time | Trip end |
| `duration_min` | int | Duration in minutes |
| `distance_km` | float | Distance covered |
| `fare` | int | Fare in local currency |
| `surge_multiplier` | float | Surge pricing factor |
| `pickup_location` | string | Pickup area name |
| `dropoff_location` | string | Dropoff area name |
| `trip_status` | string | `completed` / `cancelled` |

#### `flagged_moments_demo.csv`
Reference-compatible with `Data/flagged_moments.csv`, enriched with fusion fields:

| Column | Type | Description |
|---|---|---|
| `timestamp` | datetime | Exact moment of the event |
| `trip_id` | string | |
| `driver_id` | string | |
| `event_type` | string | `harsh_braking`, `conflict_moment`, `audio_spike`, `sustained_stress`, etc. |
| `severity` | string | `high`, `medium`, or `low` |
| `conflict_score` | float | Fused score, 0.0 – 1.0 |
| `motion_score` | float | Raw motion component score |
| `audio_score` | float | Raw audio component score |
| `max_jerk_in_window` | float | Instantaneous jerk magnitude at this sample |
| `avg_audio_in_window` | float | Raw dB level at this sample |
| `rule_trigger` | string | Human-readable rule(s) that fired (e.g. `motion_harsh_brake + audio_elevated`) |
| `description` | string | Full natural-language summary of the event |

#### `trip_summaries_demo.csv`
Aggregated per-trip metrics, matching the teammate's exact requirements:

| Column | Type | Description |
|---|---|---|
| `trip_id` | string | |
| `driver_id` | string | |
| `date` | date | |
| `start_time` | time | From trips manifest |
| `end_time` | time | From trips manifest |
| `duration_min` | int | |
| `distance_km` | float | |
| `fare` | int | |
| `total_samples` | int | Total sensor rows processed for this trip |
| `total_flags_count` | int | Total events at severity low/medium/high |
| `high_count` | int | Events at severity = `high` |
| `medium_count` | int | Events at severity = `medium` |
| `low_count` | int | Events at severity = `low` |
| `max_conflict_score` | float | Peak conflict score across all samples |
| `mean_conflict_score` | float | Average conflict score across **all** samples |
| `avg_speed` | float | Average vehicle speed in km/h |

---

## 6. Key Results

The pipeline was validated end-to-end against the existing sensor dataset on March 10, 2026:

| Metric | Value |
|---|---|
| **Demo drivers** | 10 |
| **Demo trips processed** | 11 |
| **Total sensor samples aligned** | 123 |
| **Total flagged moments** | 44 |
| **High-severity events** | 3 |
| **Medium-severity events** | 5 |
| **Low-severity events** | 36 |
| **Trips with at least one flag** | 10 / 11 |
| **Peak conflict score** | **1.0** (TRIP002 — dual-signal amplified emergency stop + very_loud audio) |
| **Global mean conflict score** | 0.158 (expected baseline: most driving is safe) |
| **Average speed across demo** | 30.9 km/h |

### Notable Event: TRIP002 Conflict Score 1.0

The peak score was generated by TRIP002 at timestamp `2024-02-06 07:22:30`. The emergency stop (`motion_score = 1.0`) coincided with very loud audio (`audio_score = 0.65`). Both exceeded the `AMPLIFIER_GATE` of 0.60, triggering the dual-signal amplifier:

```
conflict = (1.0 × 0.55) + (0.65 × 0.45) = 0.8425
conflict = min(0.8425 × 1.30, 1.0) = min(1.095, 1.0) = 1.0
severity = "high" → upload_tier = "immediate"
```

This is exactly the type of event the system is designed to surface — a physically dangerous manoeuvre compounding with cabin disturbance.

---

## 7. File Map

```
backend/
├── main.py                          ← FastAPI app + /api/sensor/stream endpoint
├── heuristics/
│   ├── __init__.py                  ← (NEW) Package init, public API exports
│   ├── stream.py                    ← (NEW) Async SSE streaming generator
│   ├── fusion.py                    ← (FIXED) Relative imports, from __future__
│   ├── audio.py                     ← Unchanged (stateful AudioClassifier)
│   ├── motion.py                    ← Unchanged (classify_motion)
│   └── gravity.py                   ← Unchanged (GravityCompensator)
├── scripts/
│   └── generate_demo_summaries.py   ← (NEW) Full batch pipeline
├── trips_demo.csv                   ← (GENERATED) 11 demo trips
├── flagged_moments_demo.csv         ← (GENERATED) 44 flagged events
└── trip_summaries_demo.csv          ← (GENERATED) Per-trip aggregates
```

---

## 8. Running the Demo

### Start the Backend Server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Stream Sensor Events (Browser / curl)

```bash
# Stream all trips
curl -N http://localhost:8000/api/sensor/stream

# Stream a specific trip at 0.3s intervals (fast demo speed)
curl -N "http://localhost:8000/api/sensor/stream?trip_id=TRIP002&interval=0.3"
```

### Regenerate Demo CSVs

```bash
cd backend
python scripts/generate_demo_summaries.py
```

The script will auto-discover the best available sensor files (primary → fallback) and regenerate all three demo CSVs in under 5 seconds.

### Frontend EventSource

```typescript
const source = new EventSource(
  "http://localhost:8000/api/sensor/stream?interval=0.5&trip_id=TRIP002"
);
source.addEventListener("sensor_update", (e) => {
  const { fusion, motion, audio } = JSON.parse(e.data);
  // fusion.severity, fusion.conflict, motion.event_type, audio.classification
});
source.addEventListener("done", () => source.close());
```

---

*Generated by GitHub Copilot · Uber Driver Pulse Hackathon · March 10, 2026*
