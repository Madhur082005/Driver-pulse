# heuristics/stream.py
# ─────────────────────────────────────────────────────────────────────────────
# SSE Streaming Pipeline
#
# Reads accelerometer & audio CSVs, pipes each aligned sample through:
#   gravity compensation → motion classification → audio classification → fusion
# and yields strict SSE-formatted JSON events to the client.
#
# Design decisions:
#   • Path resolution uses pathlib relative to this file — no hardcoded paths.
#   • CSV reads use context managers — no resource leaks.
#   • Missing files yield a JSON error event instead of crashing.
#   • Sleep interval is a parameter, exposed as a query param at the router.
#   • asyncio.CancelledError is caught for graceful client disconnects.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import csv
import json
import logging
from pathlib import Path
from typing import AsyncGenerator

from .audio import AudioClassifier
from .gravity import GravityCompensator
from .motion import classify_motion
from .fusion import fuse

logger = logging.getLogger(__name__)

# ── Dynamic path defaults ────────────────────────────────────────────────────
# Resolved relative to *this* file: backend/heuristics/stream.py
#   → parent.parent   = backend/
#   → parent.parent.parent = project root
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DATA_DIR: Path = _PROJECT_ROOT / "Data" / "sensor_data"

# ── Sensible defaults ────────────────────────────────────────────────────────
DEFAULT_INTERVAL_SEC: float = 0.5


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV into a list of row-dicts using a context manager."""
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _sse(data: dict, event: str = "message") -> str:
    """Format *data* as a strict SSE event string.

    Spec: https://html.spec.whatwg.org/multipage/server-sent-events.html
    Each event block ends with two newlines.
    """
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _safe_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    """Extract a float from a CSV row dict, returning *default* on failure."""
    try:
        return float(row[key])
    except (KeyError, ValueError, TypeError):
        return default


# ── Main streaming generator ─────────────────────────────────────────────────

async def stream_sensor_events(
    *,
    trip_id: str | None = None,
    interval_sec: float = DEFAULT_INTERVAL_SEC,
    data_dir: Path | str | None = None,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted sensor-heuristic events.

    Parameters
    ----------
    trip_id:
        If provided, only rows matching this trip are streamed.
    interval_sec:
        Seconds to pause between SSE pushes.  Configurable by the caller
        (typically exposed as a ``?interval=`` query parameter).
    data_dir:
        Override the default ``Data/sensor_data`` directory.

    Yields
    ------
    str
        SSE event blocks (``event: …\\ndata: {…}\\n\\n``).
    """
    resolved_dir = Path(data_dir).resolve() if data_dir else _DEFAULT_DATA_DIR

    accel_path = resolved_dir / "accelerometer_data.csv"
    audio_path = resolved_dir / "audio_intensity_data.csv"

    # ── Validate that data files exist before streaming ──────────────────
    for path, label in [(accel_path, "accelerometer"), (audio_path, "audio")]:
        if not path.is_file():
            yield _sse(
                {"error": f"{label} data file not found: {path.name}"},
                event="error",
            )
            return

    # ── Load CSVs (context-managed inside _load_csv) ─────────────────────
    try:
        accel_rows = _load_csv(accel_path)
        audio_rows = _load_csv(audio_path)
    except Exception as exc:
        logger.exception("Failed to parse sensor CSVs")
        yield _sse({"error": f"CSV parse error: {exc}"}, event="error")
        return

    # Index audio by (trip_id, elapsed_seconds) for O(1) lookup
    audio_index: dict[tuple[str, str], dict[str, str]] = {
        (r.get("trip_id", ""), r.get("elapsed_seconds", "")): r
        for r in audio_rows
    }

    # ── Stateful classifiers (reset per stream) ─────────────────────────
    gravity = GravityCompensator()
    audio_clf = AudioClassifier()
    prev_speed: float = 0.0
    events_sent: int = 0

    try:
        for accel_row in accel_rows:
            row_trip = accel_row.get("trip_id", "")
            if trip_id and row_trip != trip_id:
                continue

            # ── Parse accelerometer fields ───────────────────────────────
            ax = _safe_float(accel_row, "accel_x")
            ay = _safe_float(accel_row, "accel_y")
            az = _safe_float(accel_row, "accel_z")
            speed = _safe_float(accel_row, "speed_kmh")
            elapsed = _safe_float(accel_row, "elapsed_seconds")

            # ── Gravity compensation ─────────────────────────────────────
            gravity.feed(ax, ay, az, speed)
            cx, cy, cz = gravity.compensate(ax, ay, az)

            # ── Motion classification ────────────────────────────────────
            motion_result = classify_motion(cy, cx, speed, prev_speed)
            prev_speed = speed

            # ── Audio classification (match by trip + elapsed) ───────────
            audio_key = (row_trip, accel_row.get("elapsed_seconds", ""))
            audio_row = audio_index.get(audio_key)

            db_level = _safe_float(audio_row, "audio_level_db") if audio_row else 0.0
            sustained = (
                _safe_float(audio_row, "sustained_duration_sec") if audio_row else 0.0
            )
            audio_result = audio_clf.classify(db_level, sustained, elapsed)

            # ── Fusion ───────────────────────────────────────────────────
            fusion_result = fuse(motion_result, audio_result)

            # ── Yield SSE event ──────────────────────────────────────────
            event_data = {
                "index": events_sent,
                "trip_id": row_trip,
                "timestamp": accel_row.get("timestamp", ""),
                "elapsed_seconds": elapsed,
                "speed_kmh": speed,
                "motion": {
                    "event_type": motion_result.event_type,
                    "score": motion_result.score,
                    "axis": motion_result.axis,
                },
                "audio": {
                    "classification": audio_result.classification,
                    "score": audio_result.score,
                    "sustained_sec": audio_result.sustained_sec,
                    "db_level": audio_result.db_level,
                },
                "fusion": {
                    "severity": fusion_result.severity,
                    "conflict": fusion_result.conflict,
                    "flag_type": fusion_result.flag_type,
                    "upload_tier": fusion_result.upload_tier,
                    "amplified": fusion_result.amplified,
                },
            }

            yield _sse(event_data, event="sensor_update")
            events_sent += 1

            await asyncio.sleep(interval_sec)

        # ── Stream finished ──────────────────────────────────────────────
        yield _sse(
            {"status": "complete", "total_events": events_sent},
            event="done",
        )

    except asyncio.CancelledError:
        logger.info("Client disconnected — sensor stream stopped after %d events", events_sent)
        return
    except Exception as exc:
        logger.exception("Unexpected error during sensor streaming")
        yield _sse({"error": f"Stream error: {exc}"}, event="error")
