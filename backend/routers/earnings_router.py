from __future__ import annotations

import csv
from pathlib import Path

from fastapi import APIRouter

from schemas.goal_schema import GoalPayload
from services.earnings_engine import evaluate_goal
from utils.alert_builder import build_alert

router = APIRouter(prefix="/api/earnings")

# In-memory cache so we only send alerts when status changes.
_last_status_by_driver_id: dict[str, str] = {}

# Simple CSV log to prove everything is computed, not hardcoded.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
EARNINGS_LOG_CSV = _BACKEND_DIR / "earnings_log.csv"


def _ensure_earnings_header() -> None:
    if EARNINGS_LOG_CSV.is_file():
        return
    with EARNINGS_LOG_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "goal_id",
                "driver_id",
                "date",
                "timestamp",
                "target_earnings",
                "target_hours",
                "current_earnings",
                "current_hours",
                "status",
                "current_velocity",
                "target_velocity",
                "velocity_delta",
                "expected_earnings",
                "dynamic_threshold",
                "projected_shift_earnings",
            ]
        )


@router.post("/goal")
def insert_goal(goal: GoalPayload):
    _ensure_earnings_header()

    # Treat the incoming payload as the goal object for evaluate_goal
    result = evaluate_goal(goal)

    with EARNINGS_LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                goal.goal_id,
                goal.driver_id,
                goal.date,
                goal.timestamp,
                goal.target_earnings,
                goal.target_hours,
                goal.current_earnings,
                goal.current_hours,
                result["status"],
                result["current_velocity"],
                result["target_velocity"],
                result["velocity_delta"],
                result.get("expected_earnings"),
                result.get("dynamic_threshold"),
                result.get("projected_shift_earnings"),
            ]
        )

    previous_status = _last_status_by_driver_id.get(goal.driver_id)
    if previous_status == result["status"]:
        alert = None
    else:
        alert = build_alert(
            result["status"],
            delta=result["velocity_delta"],
            expected=result.get("expected_earnings"),
        )
        _last_status_by_driver_id[goal.driver_id] = result["status"]

    return {
        "driver_id": goal.driver_id,
        "status": result["status"],
        "alert": alert,
        "projected_shift_earnings": result.get("projected_shift_earnings"),
    }