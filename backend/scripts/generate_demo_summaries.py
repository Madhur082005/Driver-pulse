"""
backend/scripts/generate_demo_summaries.py
==========================================
Batch-processing pipeline for the 10-driver hackathon demo.

Reads raw sensor CSVs + full trips table, scopes everything to the
10 demo drivers (from Demo_Data/drivers.csv), runs every sample through
the full heuristics pipeline (gravity → motion → audio → fusion),
and exports three demo-ready artefacts:

  1. backend/trips_demo.csv            — demo-scoped trip manifest
  2. backend/flagged_moments_demo.csv  — flagged events (reference-compatible schema)
  3. backend/trip_summaries_demo.csv   — per-trip aggregates (counts + max/mean conflict)

Usage (from the repo root):
    python -m backend.scripts.generate_demo_summaries

Or directly:
    cd backend && python scripts/generate_demo_summaries.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path bootstrap — make `backend/` importable regardless of cwd.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent          # backend/scripts/
_BACKEND_DIR = _SCRIPT_DIR.parent                      # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent                    # repo root

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from heuristics.gravity import GravityCompensator      # noqa: E402
from heuristics.motion import classify_motion           # noqa: E402
from heuristics.audio import AudioClassifier            # noqa: E402
from heuristics.fusion import fuse                      # noqa: E402

# ---------------------------------------------------------------------------
# 1. INPUT / OUTPUT PATHS  (all resolved dynamically — zero hardcoded paths)
# ---------------------------------------------------------------------------
# Primary input CSVs (in backend/)
ACCEL_CSV = _BACKEND_DIR / "accelerometer_final.csv"
AUDIO_CSV = _BACKEND_DIR / "audio_final.csv"

# Fallback: originals from the Data/ folder (always runnable out of the box)
_ACCEL_FALLBACK = _PROJECT_ROOT / "Data" / "sensor_data" / "accelerometer_data.csv"
_AUDIO_FALLBACK = _PROJECT_ROOT / "Data" / "sensor_data" / "audio_intensity_data.csv"
_TRIPS_FALLBACK = _PROJECT_ROOT / "Data" / "trips" / "trips.csv"

# Demo driver roster — the canonical 10-driver set for the demo
_DEMO_DRIVERS_CSV = _PROJECT_ROOT / "Demo_Data" / "drivers.csv"

# Outputs
TRIPS_DEMO_OUT = _BACKEND_DIR / "trips_demo.csv"
FLAGGED_OUT    = _BACKEND_DIR / "flagged_moments_demo.csv"
SUMMARIES_OUT  = _BACKEND_DIR / "trip_summaries_demo.csv"

# How many demo drivers to keep (matches Demo_Data/drivers.csv count)
MAX_DEMO_DRIVERS = 10

# Fusion severity threshold — only flag events at or above "low"
FLAG_SEVERITY_LEVELS = {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# 2. DATA LOADING
# ---------------------------------------------------------------------------

def _resolve(primary: Path, fallback: Path, label: str) -> Path:
    """Return *primary* if it exists, else *fallback*.  Abort if neither."""
    if primary.is_file():
        return primary
    if fallback.is_file():
        print(f"  [INFO] {label}: {primary.name} not found, "
              f"using fallback {fallback.relative_to(_PROJECT_ROOT)}")
        return fallback
    sys.exit(f"  [ERROR] {label}: neither {primary} nor {fallback} exist.")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and lightly normalise the three source CSVs."""

    accel_path = _resolve(ACCEL_CSV, _ACCEL_FALLBACK, "Accelerometer")
    audio_path = _resolve(AUDIO_CSV, _AUDIO_FALLBACK, "Audio")
    trips_path = _resolve(_BACKEND_DIR / "trips_mapping.csv", _TRIPS_FALLBACK, "Trips")

    # ── Accelerometer ────────────────────────────────────────────────────
    accel = pd.read_csv(accel_path, parse_dates=["timestamp"])
    # Normalise column names (edge_sensor_processor renames to x/y/z)
    accel = accel.rename(columns={"x": "accel_x", "y": "accel_y", "z": "accel_z"})
    for col in ("accel_x", "accel_y", "accel_z", "speed_kmh", "elapsed_seconds"):
        if col not in accel.columns:
            sys.exit(f"  [ERROR] Accelerometer CSV missing required column: {col}")
    accel = accel.sort_values(["trip_id", "elapsed_seconds"]).reset_index(drop=True)

    # ── Audio ────────────────────────────────────────────────────────────
    audio = pd.read_csv(audio_path, parse_dates=["timestamp"])
    if "audio_level_db" in audio.columns and "db_level" not in audio.columns:
        audio = audio.rename(columns={"audio_level_db": "db_level"})
    for col in ("db_level", "sustained_duration_sec", "elapsed_seconds"):
        if col not in audio.columns:
            sys.exit(f"  [ERROR] Audio CSV missing required column: {col}")
    audio = audio.sort_values(["trip_id", "elapsed_seconds"]).reset_index(drop=True)

    # ── Trips ────────────────────────────────────────────────────────────
    trips = pd.read_csv(trips_path)
    for col in ("trip_id", "driver_id"):
        if col not in trips.columns:
            sys.exit(f"  [ERROR] Trips CSV missing required column: {col}")

    return accel, audio, trips


# ---------------------------------------------------------------------------
# 3. DEMO SCOPING — pick 10 drivers that actually have sensor data
# ---------------------------------------------------------------------------

def scope_to_demo(
    accel: pd.DataFrame,
    audio: pd.DataFrame,
    trips: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Narrow everything to the 10-driver demo set.

    Strategy:
      1. Find trip_ids that have BOTH accel AND audio data.
      2. If Demo_Data/drivers.csv exists AND those drivers appear in the
         trips table, prefer that roster.  Otherwise, pick the first 10
         unique drivers from the sensor-covered trips.
      3. Filter accel, audio, trips to keep only those drivers' trips.
      4. Return (accel, audio, trips_demo, demo_drivers_df).
    """
    # Trips that have both sensor streams
    sensor_trips = set(accel["trip_id"].unique()) & set(audio["trip_id"].unique())
    trips_with_sensors = trips[trips["trip_id"].isin(sensor_trips)].copy()

    if trips_with_sensors.empty:
        sys.exit("  [ERROR] No trips found with both accelerometer and audio data.")

    # Try loading the canonical demo driver list
    demo_driver_ids: list[str] | None = None
    if _DEMO_DRIVERS_CSV.is_file():
        demo_drivers_df = pd.read_csv(_DEMO_DRIVERS_CSV)
        if "driver_id" in demo_drivers_df.columns:
            roster = set(demo_drivers_df["driver_id"])
            # Check overlap: do any sensor-covered trips belong to these drivers?
            overlap = trips_with_sensors[trips_with_sensors["driver_id"].isin(roster)]
            if len(overlap["driver_id"].unique()) >= MAX_DEMO_DRIVERS:
                demo_driver_ids = list(overlap["driver_id"].unique())[:MAX_DEMO_DRIVERS]
                print(f"  [INFO] Using {len(demo_driver_ids)} drivers from Demo_Data/drivers.csv "
                      f"that have sensor data")
            else:
                print(f"  [INFO] Demo_Data/drivers.csv has only "
                      f"{len(overlap['driver_id'].unique())} drivers with sensor data — "
                      f"falling back to first {MAX_DEMO_DRIVERS} sensor-covered drivers")

    # Fallback: pick first 10 unique drivers from sensor-covered trips
    if demo_driver_ids is None:
        all_driver_ids = trips_with_sensors["driver_id"].unique()
        demo_driver_ids = list(all_driver_ids[:MAX_DEMO_DRIVERS])
        print(f"  [INFO] Selected first {len(demo_driver_ids)} drivers from sensor-covered trips")

    # Filter trips to demo drivers + sensor coverage
    trips_demo = trips_with_sensors[
        trips_with_sensors["driver_id"].isin(demo_driver_ids)
    ].copy().reset_index(drop=True)

    demo_trip_ids = set(trips_demo["trip_id"])
    accel = accel[accel["trip_id"].isin(demo_trip_ids)].reset_index(drop=True)
    audio = audio[audio["trip_id"].isin(demo_trip_ids)].reset_index(drop=True)

    return accel, audio, trips_demo, trips_demo


# ---------------------------------------------------------------------------
# 4. TIME-ALIGN: merge 15 s accel + 30 s audio onto a common timeline
# ---------------------------------------------------------------------------

def align_sensors(accel: pd.DataFrame, audio: pd.DataFrame) -> pd.DataFrame:
    """Merge accelerometer (~15 s cadence) with audio (~30 s cadence).

    Uses a per-trip merge_asof on elapsed_seconds so each accel row picks
    up the most recent audio reading (no future-leak).  Audio is
    forward-filled within each trip for the 2:1 rate mismatch.
    """
    merged_parts: list[pd.DataFrame] = []

    for trip_id, a_grp in accel.groupby("trip_id"):
        au_grp = audio.loc[audio["trip_id"] == trip_id].copy()

        a_grp = a_grp.sort_values("elapsed_seconds")
        au_grp = au_grp.sort_values("elapsed_seconds")

        combined = pd.merge_asof(
            a_grp,
            au_grp[["elapsed_seconds", "db_level", "sustained_duration_sec"]],
            on="elapsed_seconds",
            direction="backward",
            suffixes=("", "_audio"),
        )

        combined["db_level"] = combined["db_level"].ffill().fillna(0.0)
        combined["sustained_duration_sec"] = (
            combined["sustained_duration_sec"].ffill().fillna(0.0)
        )

        merged_parts.append(combined)

    if not merged_parts:
        return pd.DataFrame()

    return pd.concat(merged_parts, ignore_index=True)


# ---------------------------------------------------------------------------
# 5. PIPELINE: gravity → motion → audio → fusion (per sample, per trip)
# ---------------------------------------------------------------------------

# Global flag counter — produces FLAG0001, FLAG0002, …
_flag_counter = 0


def _next_flag_id() -> str:
    """Generate a unique sequential flag ID like FLAG0001."""
    global _flag_counter
    _flag_counter += 1
    return f"FLAG{_flag_counter:04d}"


def _build_explanation(fusion_result, motion_result, audio_result) -> str:
    """Build a human-readable explanation for a flagged moment."""
    parts: list[str] = []
    if motion_result.event_type not in ("normal", "road_noise"):
        parts.append(
            f"Motion: {motion_result.event_type.replace('_', ' ')} "
            f"(score {motion_result.score:.2f})"
        )
    if audio_result.classification != "background":
        parts.append(
            f"Audio: {audio_result.classification} "
            f"(score {audio_result.score:.2f})"
        )
    if fusion_result.amplified:
        parts.append("dual-signal amplified")
    return "; ".join(parts) if parts else f"Combined score {fusion_result.conflict:.2f}"


def _build_context(motion_result, audio_result) -> str:
    """Build an environment context string like 'High noise + Hard brake'."""
    parts: list[str] = []

    # Motion context
    motion_map = {
        "emergency_stop": "Emergency stop",
        "harsh_brake": "Hard brake",
        "moderate_brake": "Moderate brake",
        "soft_brake": "Soft brake",
        "harsh_corner": "Sharp turn",
        "moderate_corner": "Moderate turn",
    }
    if motion_result.event_type in motion_map:
        parts.append(motion_map[motion_result.event_type])

    # Audio context
    audio_map = {
        "argument": "Verbal conflict",
        "very_loud": "High noise",
        "elevated": "Elevated noise",
    }
    if audio_result.classification in audio_map:
        parts.append(audio_map[audio_result.classification])

    return " + ".join(parts) if parts else "Normal conditions"


def _compute_trip_quality_rating(flagged_count: int, max_severity: str) -> int:
    """Compute a 1–5 trip quality rating (5 = best, 1 = worst).

    Logic:
        0 flags                         → 5 (excellent)
        1-2 flags, max sev ≤ low        → 4 (good)
        1-2 flags, max sev medium       → 3 (fair)
        3+ flags OR max sev high        → 2 (poor)
        5+ flags AND max sev high       → 1 (critical)
    """
    if flagged_count == 0:
        return 5
    if flagged_count >= 5 and max_severity == "high":
        return 1
    if flagged_count >= 3 or max_severity == "high":
        return 2
    if max_severity == "medium":
        return 3
    return 4


_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1, "safe": 0}


def run_pipeline(
    merged: pd.DataFrame,
    trips_demo: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process the merged sensor stream.

    Returns (flagged_moments_df, trip_summaries_df) with the v2 schema:
      - flagged: flag_id, trip_id, driver_id, timestamp, elapsed_seconds,
                 flag_type, severity, motion_score, audio_score,
                 combined_score, explanation, context
      - summaries: trip_id, driver_id, date, duration_min, distance_km, fare,
                   earnings_velocity, motion_events_count, audio_events_count,
                   flagged_moments_count, max_severity, stress_score,
                   trip_quality_rating
    """

    # Reset global flag counter for a clean run
    global _flag_counter
    _flag_counter = 0

    # Build lookup tables from trips_demo
    trip_meta: dict[str, dict] = {}
    for _, t in trips_demo.iterrows():
        trip_meta[t["trip_id"]] = {
            "driver_id": t["driver_id"],
            "date": t.get("date", ""),
            "duration_min": t.get("duration_min", 0),
            "distance_km": t.get("distance_km", 0),
            "fare": t.get("fare", 0),
        }

    flagged_rows: list[dict] = []
    summary_rows: list[dict] = []

    for trip_id, grp in merged.groupby("trip_id"):
        meta = trip_meta.get(trip_id, {"driver_id": "UNKNOWN"})
        driver_id = meta["driver_id"]

        # Fresh stateful classifiers per trip
        gravity = GravityCompensator()
        audio_clf = AudioClassifier()
        prev_speed: float = 0.0

        # Per-trip accumulators
        all_motion_scores: list[float] = []
        all_audio_scores: list[float] = []
        motion_events_count: int = 0
        audio_events_count: int = 0
        max_severity: str = "safe"
        flagged_count: int = 0

        grp = grp.sort_values("elapsed_seconds")
        prev_accel_mag: float | None = None

        for _, row in grp.iterrows():
            ax = float(row["accel_x"])
            ay = float(row["accel_y"])
            az = float(row["accel_z"])
            speed = float(row["speed_kmh"])
            elapsed = float(row["elapsed_seconds"])
            db = float(row["db_level"])
            sustained = float(row["sustained_duration_sec"])

            # ── Gravity compensation ─────────────────────────────────
            gravity.feed(ax, ay, az, speed)
            cx, cy, cz = gravity.compensate(ax, ay, az)

            prev_accel_mag_val = prev_accel_mag  # save for jerk (unused in new schema but keep pipeline intact)
            accel_mag = math.sqrt(cx**2 + cy**2 + cz**2)
            prev_accel_mag = accel_mag

            # ── Motion classification ────────────────────────────────
            motion_result = classify_motion(
                comp_y=cy, comp_x=cx,
                speed_kmh=speed, prev_speed=prev_speed,
            )
            prev_speed = speed

            # ── Audio classification ─────────────────────────────────
            audio_result = audio_clf.classify(
                db_level=db,
                sustained_sec=sustained,
                elapsed_seconds=elapsed,
            )

            # ── Fusion ───────────────────────────────────────────────
            fusion_result = fuse(motion_result, audio_result)

            # Track motion/audio events for summary counts
            if motion_result.event_type not in ("normal", "road_noise"):
                all_motion_scores.append(motion_result.score)
                motion_events_count += 1
            if audio_result.classification != "background":
                all_audio_scores.append(audio_result.score)
                audio_events_count += 1

            # ── Flagged moment? ──────────────────────────────────────
            if fusion_result.severity in FLAG_SEVERITY_LEVELS:
                flagged_count += 1

                # Track max severity
                if _SEVERITY_RANK.get(fusion_result.severity, 0) > _SEVERITY_RANK.get(max_severity, 0):
                    max_severity = fusion_result.severity

                flagged_rows.append({
                    "flag_id": _next_flag_id(),
                    "trip_id": trip_id,
                    "driver_id": driver_id,
                    "timestamp": row.get("timestamp", ""),
                    "elapsed_seconds": round(elapsed, 2),
                    "flag_type": fusion_result.flag_type or fusion_result.severity,
                    "severity": fusion_result.severity,
                    "motion_score": round(motion_result.score, 4),
                    "audio_score": round(audio_result.score, 4),
                    "combined_score": round(fusion_result.conflict, 4),
                    "explanation": _build_explanation(fusion_result, motion_result, audio_result),
                    "context": _build_context(motion_result, audio_result),
                })

        # ── Per-trip summary (after all samples processed) ───────────
        duration_min = float(meta.get("duration_min", 0))
        fare = float(meta.get("fare", 0))
        earnings_velocity = round(fare / duration_min, 2) if duration_min > 0 else 0.0

        # stress_score: weighted average of motion and audio scores (same weights as fusion)
        avg_motion = float(np.mean(all_motion_scores)) if all_motion_scores else 0.0
        avg_audio = float(np.mean(all_audio_scores)) if all_audio_scores else 0.0
        stress_score = round((avg_motion * 0.55) + (avg_audio * 0.45), 4)

        trip_quality = _compute_trip_quality_rating(flagged_count, max_severity)

        summary_rows.append({
            "trip_id": trip_id,
            "driver_id": driver_id,
            "date": meta.get("date", ""),
            "duration_min": duration_min,
            "distance_km": meta.get("distance_km", 0),
            "fare": fare,
            "earnings_velocity": earnings_velocity,
            "motion_events_count": motion_events_count,
            "audio_events_count": audio_events_count,
            "flagged_moments_count": flagged_count,
            "max_severity": max_severity,
            "stress_score": stress_score,
            "trip_quality_rating": trip_quality,
        })

    # ── Build DataFrames with explicit column order ──────────────────────

    flagged_cols = [
        "flag_id", "trip_id", "driver_id", "timestamp", "elapsed_seconds",
        "flag_type", "severity", "motion_score", "audio_score",
        "combined_score", "explanation", "context",
    ]
    flagged_df = pd.DataFrame(flagged_rows, columns=flagged_cols)

    summary_cols = [
        "trip_id", "driver_id", "date", "duration_min", "distance_km", "fare",
        "earnings_velocity", "motion_events_count", "audio_events_count",
        "flagged_moments_count", "max_severity", "stress_score",
        "trip_quality_rating",
    ]
    summaries_df = pd.DataFrame(summary_rows, columns=summary_cols)

    return flagged_df, summaries_df


# ---------------------------------------------------------------------------
# 6. MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 62)
    print("  Uber Driver Pulse — Demo Data Pipeline")
    print("=" * 62)

    # Step 1 — Load raw data
    print("\n[1/5] Loading source data …")
    accel, audio, trips = load_data()
    print(f"       Accelerometer rows : {len(accel):,}")
    print(f"       Audio rows         : {len(audio):,}")
    print(f"       Full trips table   : {len(trips):,}")

    # Step 2 — Scope to demo drivers
    print("\n[2/5] Scoping to demo drivers …")
    accel, audio, trips_demo, _ = scope_to_demo(accel, audio, trips)
    demo_drivers = trips_demo["driver_id"].nunique()
    print(f"       Demo drivers       : {demo_drivers}")
    print(f"       Demo trips         : {len(trips_demo):,}")
    print(f"       Accel rows (scoped): {len(accel):,}")
    print(f"       Audio rows (scoped): {len(audio):,}")

    # Step 3 — Write trips_demo.csv
    print("\n[3/5] Writing trips_demo.csv …")
    trips_demo.to_csv(TRIPS_DEMO_OUT, index=False)
    print(f"       → {TRIPS_DEMO_OUT.relative_to(_PROJECT_ROOT)}")

    # Step 4 — Time-align & run pipeline
    print("\n[4/5] Aligning sensors + running heuristics pipeline …")
    merged = align_sensors(accel, audio)
    print(f"       Aligned rows       : {len(merged):,}")
    flagged, summaries = run_pipeline(merged, trips_demo)
    print(f"       Flagged moments    : {len(flagged):,}")
    print(f"       Trip summaries     : {len(summaries):,}")

    # Step 5 — Export
    print("\n[5/5] Writing output CSVs …")
    flagged.to_csv(FLAGGED_OUT, index=False)
    summaries.to_csv(SUMMARIES_OUT, index=False)
    print(f"       → {FLAGGED_OUT.relative_to(_PROJECT_ROOT)}")
    print(f"       → {SUMMARIES_OUT.relative_to(_PROJECT_ROOT)}")

    # ── Quick sanity stats ───────────────────────────────────────────────
    print("\n── Summary Stats ──────────────────────────────────────────")
    if not summaries.empty:
        print(f"   Trips with flags       : "
              f"{(summaries['flagged_moments_count'] > 0).sum()} / {len(summaries)}")
        print(f"   Max stress score       : {summaries['stress_score'].max():.4f}")
        print(f"   Avg earnings velocity  : {summaries['earnings_velocity'].mean():.2f} ₹/min")
        print(f"   Quality rating dist    : "
              f"{(summaries['trip_quality_rating'] == 5).sum()}★5  "
              f"{(summaries['trip_quality_rating'] == 4).sum()}★4  "
              f"{(summaries['trip_quality_rating'] == 3).sum()}★3  "
              f"{(summaries['trip_quality_rating'] == 2).sum()}★2  "
              f"{(summaries['trip_quality_rating'] == 1).sum()}★1")
    if not flagged.empty:
        print(f"   Event breakdown        : "
              f"{(flagged['severity'] == 'high').sum()} high, "
              f"{(flagged['severity'] == 'medium').sum()} medium, "
              f"{(flagged['severity'] == 'low').sum()} low")

    print("\n✓ Done.\n")


if __name__ == "__main__":
    main()
