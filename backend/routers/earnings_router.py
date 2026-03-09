from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from models.driver_goal import DriverGoal
from models.earnings_velocity import EarningsVelocity

from services.earnings_engine import evaluate_goal
from utils.alert_builder import build_alert
from schemas.goal_schema import GoalPayload

router = APIRouter(prefix="/api/earnings")

# Lightweight, in-memory cache for last known status per driver.
# This keeps the edge/API side simple and avoids spamming duplicate alerts.
_last_status_by_driver_id: dict[str, str] = {}


@router.post("/goal")
def insert_goal(goal: GoalPayload, db: Session = Depends(get_db)):

    goal_row = DriverGoal(**goal.dict())
    db.add(goal_row)
    db.commit()

    result = evaluate_goal(goal_row)

    log = EarningsVelocity(
        driver_id=goal_row.driver_id,
        date=goal_row.date,
        timestamp=goal_row.timestamp,
        cumulative_earnings=goal_row.current_earnings,
        elapsed_hours=goal_row.current_hours,
        current_velocity=result["current_velocity"],
        target_velocity=result["target_velocity"],
        velocity_delta=result["velocity_delta"],
        trips_completed=0,
        forecast_status=result["status"],
    )

    db.add(log)
    db.commit()

    previous_status = _last_status_by_driver_id.get(goal_row.driver_id)

    if previous_status == result["status"]:
        # No status change → suppress duplicate alert content.
        alert = None
    else:
        alert = build_alert(
            result["status"],
            delta=result["velocity_delta"],
            expected=result["expected_earnings"],
        )
        _last_status_by_driver_id[goal_row.driver_id] = result["status"]

    return {
        "driver_id": goal_row.driver_id,
        "status": result["status"],
        "alert": alert,
        "projected_shift_earnings": result["projected_shift_earnings"],
    }