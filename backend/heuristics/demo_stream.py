from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import AsyncGenerator, Iterable

import numpy as np

from services.earnings_engine import evaluate_goal
from .audio import AudioClassifier
from .fusion import fuse
from .gravity import GravityCompensator
from .motion import classify_motion


ACCEL_SAMPLE_RATE_SEC: int = 1
AUDIO_SAMPLE_RATE_SEC: int = 1
EARNINGS_UPDATE_INTERVAL_MIN: int = 20

# Audio: dB threshold above which a sample counts toward sustained-loud
AUDIO_SUSTAINED_THRESHOLD_DB: float = 70.0


@dataclass
class DemoDriver:
    driver_id: str
    name: str
    city: str
    shift_start: datetime
    shift_end: datetime
    target_earnings: float   # INR
    target_hours: float


@dataclass
class DemoTripConfig:
    code: str
    duration_min: int
    fare: float              # INR
    distance_km: float
    anomaly: str


def _sse(data: dict, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


_BACKEND_DIR = Path(__file__).resolve().parent.parent
FLAGGED_CSV  = _BACKEND_DIR / "flagged_moments.csv"
SUMMARIES_CSV = _BACKEND_DIR / "trip_summaries.csv"
STREAM_CSV   = _BACKEND_DIR / "sensor_stream.csv"

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1, "safe": 0}
_flag_counter = 0


def _next_flag_id() -> str:
    global _flag_counter
    _flag_counter += 1
    return f"FLAG{_flag_counter:04d}"


def _ensure_flagged_header() -> None:
    if FLAGGED_CSV.is_file():
        return
    with FLAGGED_CSV.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            "flag_id", "trip_id", "driver_id", "timestamp",
            "elapsed_seconds", "flag_type", "severity",
            "motion_score", "audio_score", "combined_score",
            "explanation", "context",
        ])


def _ensure_summaries_header() -> None:
    if SUMMARIES_CSV.is_file():
        return
    with SUMMARIES_CSV.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            "trip_id", "driver_id", "date", "duration_min",
            "distance_km", "fare_inr", "earnings_velocity_inr_per_min",
            "motion_events_count", "audio_events_count",
            "flagged_moments_count", "max_severity",
            "stress_score", "trip_quality_rating",
        ])


def _ensure_stream_header() -> None:
    if STREAM_CSV.is_file():
        return
    with STREAM_CSV.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            "index", "driver_id", "trip_id", "timestamp", "elapsed_seconds",
            "accel_x", "accel_y", "accel_z", "speed_kmh", "audio_level_db",
            "sustained_audio_sec",
            "motion_event_type", "motion_score",
            "audio_classification", "audio_score",
            "fusion_severity", "fusion_conflict", "fusion_flag_type",
            "earnings_status", "earnings_current_inr",
            "earnings_current_velocity", "earnings_target_velocity",
            "earnings_velocity_delta", "earnings_expected",
            "earnings_dynamic_threshold", "earnings_projected",
        ])


def _base_demo_scenario() -> tuple[DemoDriver, list[DemoTripConfig]]:
    """
    10 trips for a Mumbai Uber driver. Anomaly codes map to SINGLE, realistic
    incidents — not sustained multi-sample injections.

    Anomaly legend (each produces at most 1–3 flagged samples):
      door_slam        – 1 abrupt stop + 1 jolt on y-axis at pickup
      hard_brake       – 1 single harsh braking event mid-trip
      loud_passenger   – 2–3 samples of elevated audio (passenger call), NOT argument
      pothole_jolt     – 1 sharp vertical jolt (z-axis spike)
      conflict         – 1 harsh brake + 3 consecutive loud samples (brief argument)
      rapid_brake_pair – 2 moderate brakes ~6 samples apart (traffic signal jumping)
      device_tilt      – 1 device shift/tilt (single high y-accel spike)
      stop_go_traffic  – NO anomaly injection; only realistic speed variation
      none             – clean trip, no injections
    """
    date_str  = "2024-10-25"
    shift_start = datetime.strptime(f"{date_str} 07:00:00", "%Y-%m-%d %H:%M:%S")

    driver = DemoDriver(
        driver_id="DRV_ARJUN",
        name="Arjun Kumar",
        city="Mumbai",
        shift_start=shift_start,
        shift_end=shift_start + timedelta(hours=8),
        target_earnings=2000.0,
        target_hours=8.0,
    )

    trips: list[DemoTripConfig] = [
        # Morning rush — behind pace
        DemoTripConfig("TRIP_001", 15,  101.0,   3.5, "door_slam"),
        DemoTripConfig("TRIP_002", 22, 135.0,   6.0, "none"),
        DemoTripConfig("TRIP_003", 28, 115.0,   7.0, "loud_passenger"),
        # Mid-morning — short high-value rides, briefly on track
        DemoTripConfig("TRIP_004", 18, 290.0,  13.0, "hard_brake"),
        DemoTripConfig("TRIP_005", 25, 310.0,  16.0, "conflict"),
        # Afternoon grind — low fares, falling behind
        DemoTripConfig("TRIP_006", 30, 120.0,   7.0, "rapid_brake_pair"),
        DemoTripConfig("TRIP_007", 20,  140.0,   6.0, "pothole_jolt"),
        DemoTripConfig("TRIP_008", 45, 145.0,  11.0, "stop_go_traffic"),
        # Late surge — recovery
        DemoTripConfig("TRIP_009", 40, 530.0,  39.0, "none"),   # airport run
        DemoTripConfig("TRIP_010", 35, 265.0,  19.0, "device_tilt"),
    ]

    return driver, trips


def _generate_trip_samples(
    driver: DemoDriver,
    trip: DemoTripConfig,
    start_time: datetime,
    *,
    demo_mode: bool = True,
) -> Iterable[dict]:
    if demo_mode:
        num_samples = trip.duration_min or 1
        time_step   = timedelta(minutes=1)
        sec_per_step = 60.0
    else:
        num_samples  = (trip.duration_min * 60) or 1
        time_step    = timedelta(seconds=ACCEL_SAMPLE_RATE_SEC)
        sec_per_step = float(ACCEL_SAMPLE_RATE_SEC)

    timestamps  = [start_time + time_step * i for i in range(num_samples)]
    elapsed_sec = np.arange(num_samples, dtype=float) * sec_per_step

    # ------------------------------------------------------------------
    # Tight baselines — minimise accidental threshold crossings
    # ------------------------------------------------------------------
    base_speed = 18.0 if trip.anomaly == "stop_go_traffic" else 36.0
    z_accel   = np.random.normal(9.81, 0.15, num_samples)   # gravity dominant
    y_accel   = np.random.normal(0.0,  0.08, num_samples)   # near-zero longitudinal
    x_accel   = np.random.normal(0.0,  0.06, num_samples)   # near-zero lateral
    audio_db  = np.random.normal(52.0, 2.0,  num_samples)   # quiet cabin baseline
    speed_kmh = np.random.normal(base_speed, 4.0, num_samples).clip(0)

    # Anomaly injection window — always at sample index 'onset'
    # We choose onset = 40% into the trip so it is clearly mid-ride
    onset = max(2, int(num_samples * 0.40))

    if trip.anomaly == "door_slam":
        # Brief stop at pickup then single y-jolt as door closes
        speed_kmh[onset:onset + 2] = 0.0
        y_accel[onset]             = -5.5          # 1 sample flagged

    elif trip.anomaly == "hard_brake":
        # Single harsh braking event — 1 sample
        speed_kmh[onset] = 68.0                    # was travelling fast
        y_accel[onset]   = -6.8                    # 1 sample flagged

    elif trip.anomaly == "loud_passenger":
        # Passenger on a phone call — elevated but NOT argument-level; 3 samples
        audio_db[onset:onset + 3] = 74.0           # just above threshold, low severity

    elif trip.anomaly == "pothole_jolt":
        # Single z-axis spike from pothole — 1 sample
        z_accel[onset] = 16.5                      # 1 sample flagged

    elif trip.anomaly == "conflict":
        # 1 harsh brake (driver reacts) + brief verbal argument (3 samples)
        y_accel[onset]                = -7.8       # 1 motion flag
        audio_db[onset + 1:onset + 4] = 88.0       # 3 audio flags (sustained)

    elif trip.anomaly == "rapid_brake_pair":
        # Two moderate brakes separated by ~6 samples (traffic signal jumping)
        y_accel[onset]     = -5.2                  # 1 flag
        y_accel[onset + 6] = -5.0                  # 1 flag (if onset+6 < num_samples)

    elif trip.anomaly == "device_tilt":
        # Phone slips/tilts — single spike then back to normal
        y_accel[onset] = -9.5                      # 1 flag (unusual but not harsh_brake)

    elif trip.anomaly == "stop_go_traffic":
        # Realistic Mumbai traffic: repeated gentle stops, no flag-level brakes
        # Speed oscillates; y_accel stays within safe range
        for k in range(4, num_samples - 4, 10):
            speed_kmh[k:k + 3] = np.random.uniform(0, 5)
            y_accel[k]         = np.random.uniform(-1.0, -0.4)  # soft, below threshold

    # elif trip.anomaly == "none": nothing injected — clean trip

    for i in range(num_samples):
        spd = speed_kmh[i]
        yield {
            "driver_id":       driver.driver_id,
            "trip_id":         trip.code,
            "timestamp":       timestamps[i],
            "elapsed_seconds": float(elapsed_sec[i]),
            "accel_x":         float(x_accel[i]),
            "accel_y":         float(y_accel[i]),
            "accel_z":         float(z_accel[i]),
            "speed_kmh":       float(spd) if not np.isnan(spd) else 0.0,
            "audio_level_db":  float(audio_db[i]),
        }


async def stream_demo_events(
    *,
    interval_sec: float = 0.05,
    demo_mode: bool = True,
) -> AsyncGenerator[str, None]:
    
    driver, trips = _base_demo_scenario()

    gravity   = GravityCompensator()
    audio_clf = AudioClassifier()
    prev_speed: float   = 0.0
    current_earnings: float = 0.0
    shift_start = driver.shift_start
    events_sent = 0
    last_earnings_eval_min: float = 0.0
    earnings: dict = {}
    sustained_loud_sec: float = 0.0

    try:
        for p in (FLAGGED_CSV, SUMMARIES_CSV, STREAM_CSV):
            if p.is_file():
                p.unlink()
        _ensure_flagged_header()
        _ensure_summaries_header()
        _ensure_stream_header()

        current_time = shift_start + timedelta(minutes=5)

        for trip in trips:
            motion_events_count   = 0
            audio_events_count    = 0
            flagged_moments_count = 0
            max_severity          = "safe"
            motion_scores: list[float] = []
            audio_scores:  list[float] = []

            trip_steps    = trip.duration_min or 1
            per_step_fare = trip.fare / trip_steps

            for sample in _generate_trip_samples(
                driver, trip, current_time, demo_mode=demo_mode
            ):
                ts: datetime = sample["timestamp"]

                current_earnings += per_step_fare
                if current_earnings > driver.target_earnings * 2.5:
                    current_earnings = driver.target_earnings * 2.5

                elapsed_hours   = max((ts - shift_start).total_seconds() / 3600.0, 0.0)
                elapsed_minutes = elapsed_hours * 60.0

                should_eval = demo_mode or (
                    elapsed_minutes - last_earnings_eval_min >= EARNINGS_UPDATE_INTERVAL_MIN
                )
                if should_eval or not earnings:
                    goal = SimpleNamespace(
                        goal_id="GOAL_DEMO",
                        driver_id=driver.driver_id,
                        target_earnings=driver.target_earnings,
                        target_hours=driver.target_hours,
                        current_earnings=current_earnings,
                        current_hours=elapsed_hours,
                    )
                    earnings = evaluate_goal(goal)
                    last_earnings_eval_min = elapsed_minutes

                ax    = sample["accel_x"]
                ay    = sample["accel_y"]
                az    = sample["accel_z"]
                speed = sample["speed_kmh"]

                gravity.feed(ax, ay, az, speed)
                cx, cy, cz = gravity.compensate(ax, ay, az)

                motion_result = classify_motion(cy, cx, speed, prev_speed)
                prev_speed    = speed

                if sample["audio_level_db"] >= AUDIO_SUSTAINED_THRESHOLD_DB:
                    sustained_loud_sec += 60.0 if demo_mode else float(AUDIO_SAMPLE_RATE_SEC)
                else:
                    sustained_loud_sec = 0.0

                audio_result = audio_clf.classify(
                    db_level=sample["audio_level_db"],
                    sustained_sec=sustained_loud_sec,
                    elapsed_seconds=(ts - shift_start).total_seconds(),
                )

                fusion_result = fuse(motion_result, audio_result)

                if motion_result.event_type not in ("normal", "road_noise"):
                    motion_events_count += 1
                    motion_scores.append(motion_result.score)
                if audio_result.classification != "background":
                    audio_events_count += 1
                    audio_scores.append(audio_result.score)

                if fusion_result.severity in ("low", "medium", "high"):
                    flagged_moments_count += 1
                    if _SEVERITY_RANK[fusion_result.severity] > _SEVERITY_RANK[max_severity]:
                        max_severity = fusion_result.severity

                    explanation_parts: list[str] = []
                    if motion_result.event_type not in ("normal", "road_noise"):
                        explanation_parts.append(
                            f"Motion: {motion_result.event_type.replace('_', ' ')} "
                            f"(score {motion_result.score:.2f})"
                        )
                    if audio_result.classification != "background":
                        explanation_parts.append(
                            f"Audio: {audio_result.classification} "
                            f"(score {audio_result.score:.2f})"
                        )
                    if fusion_result.amplified:
                        explanation_parts.append("dual-signal amplified")
                    explanation = (
                        "; ".join(explanation_parts)
                        if explanation_parts
                        else f"Combined score {fusion_result.conflict:.2f}"
                    )

                    motion_label = {
                        "emergency_stop":  "Emergency stop",
                        "harsh_brake":     "Hard brake",
                        "moderate_brake":  "Moderate brake",
                        "soft_brake":      "Soft brake",
                        "harsh_corner":    "Sharp turn",
                        "moderate_corner": "Moderate turn",
                    }
                    audio_label = {
                        "argument":  "Verbal conflict",
                        "very_loud": "High noise",
                        "elevated":  "Elevated noise",
                    }
                    context_parts = []
                    if motion_result.event_type in motion_label:
                        context_parts.append(motion_label[motion_result.event_type])
                    if audio_result.classification in audio_label:
                        context_parts.append(audio_label[audio_result.classification])
                    context = " + ".join(context_parts) if context_parts else "Normal conditions"

                    with FLAGGED_CSV.open("a", newline="", encoding="utf-8") as f:
                        csv.writer(f).writerow([
                            _next_flag_id(), trip.code, driver.driver_id,
                            ts.strftime("%Y-%m-%d %H:%M:%S"),
                            sample["elapsed_seconds"],
                            fusion_result.flag_type or fusion_result.severity,
                            fusion_result.severity,
                            round(motion_result.score, 4),
                            round(audio_result.score, 4),
                            round(fusion_result.conflict, 4),
                            explanation, context,
                        ])

                with STREAM_CSV.open("a", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow([
                        events_sent, driver.driver_id, trip.code,
                        ts.strftime("%Y-%m-%d %H:%M:%S"),
                        sample["elapsed_seconds"],
                        ax, ay, az, speed, sample["audio_level_db"],
                        round(sustained_loud_sec, 1),
                        motion_result.event_type, motion_result.score,
                        audio_result.classification, audio_result.score,
                        fusion_result.severity, fusion_result.conflict,
                        fusion_result.flag_type,
                        earnings["status"],
                        round(current_earnings, 2),
                        earnings["current_velocity"],
                        earnings["target_velocity"],
                        earnings["velocity_delta"],
                        earnings.get("expected_earnings"),
                        earnings.get("dynamic_threshold"),
                        earnings.get("projected_shift_earnings"),
                    ])

                payload = {
                    "index":                 events_sent,
                    "driver_id":             driver.driver_id,
                    "trip_id":               trip.code,
                    "timestamp":             ts.isoformat(),
                    "elapsed_shift_hours":   round(elapsed_hours, 3),
                    "shift_target_earnings": driver.target_earnings,
                    "shift_target_hours":    driver.target_hours,
                    "currency":              "INR",
                    "earnings": {
                        "current_earnings":         round(current_earnings, 2),
                        "status":                   earnings["status"],
                        "current_velocity":         earnings["current_velocity"],
                        "target_velocity":          earnings["target_velocity"],
                        "velocity_delta":           earnings["velocity_delta"],
                        "expected_earnings":        earnings.get("expected_earnings"),
                        "dynamic_threshold":        earnings.get("dynamic_threshold"),
                        "projected_shift_earnings": earnings.get("projected_shift_earnings"),
                    },
                    "sensor": {
                        "accel_x":  ax, "accel_y": ay,
                        "accel_z":  az, "speed_kmh": speed,
                    },
                    "motion": {
                        "event_type": motion_result.event_type,
                        "score":      motion_result.score,
                        "axis":       motion_result.axis,
                    },
                    "audio": {
                        "classification": audio_result.classification,
                        "score":          audio_result.score,
                        "db_level":       audio_result.db_level,
                        "sustained_sec":  audio_result.sustained_sec,
                    },
                    "fusion": {
                        "severity":    fusion_result.severity,
                        "conflict":    fusion_result.conflict,
                        "flag_type":   fusion_result.flag_type,
                        "upload_tier": fusion_result.upload_tier,
                        "amplified":   fusion_result.amplified,
                    },
                }

                yield _sse(payload, event="demo_update")
                events_sent += 1
                await asyncio.sleep(interval_sec)

            # Per-trip summary
            avg_motion = sum(motion_scores) / len(motion_scores) if motion_scores else 0.0
            avg_audio  = sum(audio_scores)  / len(audio_scores)  if audio_scores  else 0.0
            stress_score      = round(avg_motion * 0.55 + avg_audio * 0.45, 4)
            earnings_velocity = round(trip.fare / trip.duration_min, 2) if trip.duration_min else 0.0

            if   flagged_moments_count == 0:                                   trip_quality_rating = 5
            elif flagged_moments_count >= 5 and max_severity == "high":        trip_quality_rating = 1
            elif flagged_moments_count >= 3 or  max_severity == "high":        trip_quality_rating = 2
            elif max_severity == "medium":                                      trip_quality_rating = 3
            else:                                                               trip_quality_rating = 4

            with SUMMARIES_CSV.open("a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    trip.code, driver.driver_id,
                    driver.shift_start.date().isoformat(),
                    float(trip.duration_min), float(trip.distance_km),
                    float(trip.fare), earnings_velocity,
                    motion_events_count, audio_events_count,
                    flagged_moments_count, max_severity,
                    stress_score, trip_quality_rating,
                ])

            yield _sse({
                "trip_id":          trip.code,
                "driver_id":        driver.driver_id,
                "timestamp":        (current_time + timedelta(minutes=trip.duration_min)).isoformat(),
                "current_earnings": round(current_earnings, 2),
                "currency":         "INR",
                "fare":             trip.fare,
                "distance_km":      trip.distance_km,
                "duration_min":     trip.duration_min,
            }, event="trip_done")

            current_time += timedelta(minutes=trip.duration_min + 10)

        yield _sse({
            "status":         "complete",
            "total_events":   events_sent,
            "final_earnings": round(current_earnings, 2),
            "currency":       "INR",
        }, event="done")

    except asyncio.CancelledError:
        return