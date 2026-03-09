import csv
import logging
import os
from types import SimpleNamespace

from services.earnings_engine import evaluate_goal
from utils.alert_builder import build_alert

# In-memory cache used only by the demo harness to show
# "alert only when status changes" behaviour per driver.
_last_status_by_driver_id: dict[str, str] = {}


def configure_logging() -> None:
    """Configure basic console logging for test runs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def make_goal_from_row(row: dict) -> SimpleNamespace:
    """
    Create a lightweight goal-like object from a CSV row.

    This mirrors the fields in `DriverGoal` / `GoalPayload` without
    requiring a database session.
    """
    return SimpleNamespace(
        goal_id=row["goal_id"],
        driver_id=row["driver_id"],
        date=row["date"],
        shift_start_time=row["shift_start_time"],
        shift_end_time=row["shift_end_time"],
        target_earnings=float(row["target_earnings"]),
        target_hours=float(row["target_hours"]),
        current_earnings=float(row["current_earnings"]),
        current_hours=float(row["current_hours"]),
        timestamp=row["timestamp"],
    )


def run_earnings_evaluation_demo():
    """
    Load demo goals from `Demo_Data/driver_goal_progress.csv`,
    run them through `evaluate_goal`, and print/log alerts.

    Args:
        limit: Optional cap on number of rows to process (for quick runs).
    """
    logger = logging.getLogger("earnings_test")

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(backend_dir, "..", "Demo_Data", "driver_goal_progress.csv")
    csv_path = os.path.normpath(csv_path)

    if not os.path.exists(csv_path):
        logger.error("Could not find demo CSV at %s", csv_path)
        print(f"ERROR: demo CSV not found at {csv_path}")
        return

    logger.info("Using demo data at %s", csv_path)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, start=1):
            goal = make_goal_from_row(row)
            result = evaluate_goal(goal)

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

            # Log structured info
            logging.info(
                "Goal %s | Driver %s | status=%s | delta=%.2f | current_vel=%.2f | "
                "target_vel=%.2f | expected=%.2f | threshold=%.2f | projected=%.2f",
                goal.goal_id,
                goal.driver_id,
                result["status"],
                result["velocity_delta"],
                result["current_velocity"],
                result["target_velocity"],
                result.get("expected_earnings", 0.0),
                result.get("dynamic_threshold", 0.0),
                result.get("projected_shift_earnings", 0.0),
            )

            # Also print a concise alert to the terminal when there is a status change
            if alert is not None:
                print(
                    f"[{goal.goal_id}] Driver {goal.driver_id} | "
                    f"status={result['status']} | "
                    f"delta={result['velocity_delta']:.2f} | "
                    f"projected={result.get('projected_shift_earnings', 0.0):.2f} | "
                    f"alert='{alert}'"
                )


if __name__ == "__main__":
    configure_logging()
    print("Running earnings evaluation demo against Demo_Data/driver_goal_progress.csv ...")
    run_earnings_evaluation_demo()
