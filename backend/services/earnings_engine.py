import logging

# Fraction of the overall goal we use to personalize the absolute threshold.
# For example, 5% of a ₹2,000 goal → ₹100.
BASE_ABS_FRACTION_OF_GOAL = 0.05
BASE_ABS_THRESHOLD_MIN = 50.0
BASE_ABS_THRESHOLD_MAX = 250.0

# Relative threshold as a fraction of expected earnings so far (e.g. 10%)
REL_THRESHOLD_FRACTION = 0.10

# Don't flag "at_risk" until we have at least this many hours of driving
MIN_HOURS_FOR_AT_RISK = 1.0

# Early in the shift, expected earnings are noisy.
# We slightly soften the expectation when elapsed hours < this.
EARLY_HOURS_WINDOW = 1.0
EARLY_EXPECTED_SCALE = 0.8  # e.g. treat expected as 80% of linear in first hour

# Upper bound multiplier for projected earnings relative to target_earnings.
# Keeps the forecast from exploding due to a lucky early trip.
MAX_PROJECTION_MULTIPLIER = 2.0

logger = logging.getLogger(__name__)


def evaluate_goal(goal):
    """
    Evaluate a driver's earnings goal and classify their status.

    The goal object only needs these numeric fields:
      - target_earnings, target_hours
      - current_earnings, current_hours
    It can be a Pydantic model, a SimpleNamespace, or any object with
    those attributes. This keeps the logic easy to reuse on the edge.
    """

    if goal.target_hours == 0:
        logger.warning(
            "Goal %s for driver %s has target_hours=0. "
            "Falling back to zero velocities to avoid division by zero.",
            getattr(goal, "goal_id", None),
            getattr(goal, "driver_id", None),
        )
        target_velocity = 0
    else:
        target_velocity = goal.target_earnings / goal.target_hours

    if goal.current_hours == 0:
        result = {
            "status": "on_track",
            "current_velocity": 0,
            "target_velocity": target_velocity,
            "velocity_delta": 0,
        }
        logger.info(
            "Evaluated goal %s for driver %s (no hours yet): %s",
            getattr(goal, "goal_id", None),
            getattr(goal, "driver_id", None),
            result,
        )
        return result

    current_velocity = goal.current_earnings / goal.current_hours

    expected = target_velocity * goal.current_hours

    # Be more forgiving early in the shift where variance is naturally high.
    # Smooth ramp: scale goes from EARLY_EXPECTED_SCALE (0.8) at hour 0
    # to 1.0 at EARLY_HOURS_WINDOW (1 hour).  This eliminates the
    # discontinuity that a hard if-branch would create at exactly 1 hour.
    if goal.current_hours < EARLY_HOURS_WINDOW:
        scale = EARLY_EXPECTED_SCALE + (
            (1.0 - EARLY_EXPECTED_SCALE)
            * (goal.current_hours / EARLY_HOURS_WINDOW)
        )
        expected *= scale

    # NOTE: despite the name, velocity_delta is an EARNINGS gap (₹) not a
    # velocity gap (₹/hr).  It answers "how many rupees ahead/behind am I
    # compared to where I should be right now?"  Kept for API compatibility.
    velocity_delta = goal.current_earnings - expected

    # Projected end-of-shift earnings based on current velocity.
    # Only meaningful once some driving time has elapsed.
    if goal.current_hours > 0:
        remaining_hours = max(goal.target_hours - goal.current_hours, 0)
        projected_shift_earnings = goal.current_earnings + remaining_hours * current_velocity

        # Clamp to a sane range to avoid unrealistic projections from short-term noise.
        projected_shift_earnings = max(projected_shift_earnings, 0)
        if goal.target_earnings > 0:
            projected_cap = goal.target_earnings * MAX_PROJECTION_MULTIPLIER
            projected_shift_earnings = min(projected_shift_earnings, projected_cap)
    else:
        projected_shift_earnings = goal.current_earnings

    # Goal-personalized absolute threshold
    base_abs_threshold = goal.target_earnings * BASE_ABS_FRACTION_OF_GOAL
    base_abs_threshold = max(
        BASE_ABS_THRESHOLD_MIN, min(BASE_ABS_THRESHOLD_MAX, base_abs_threshold)
    )

    # Mixed absolute + relative threshold
    dynamic_threshold = max(
        base_abs_threshold,
        abs(expected) * REL_THRESHOLD_FRACTION,
    )

    if velocity_delta >= dynamic_threshold:
        status = "ahead"
    elif (
        velocity_delta <= -dynamic_threshold
        and goal.current_hours >= MIN_HOURS_FOR_AT_RISK
    ):
        # We only allow "at_risk" once we've seen enough driving time
        status = "at_risk"
    else:
        status = "on_track"

    result = {
        "status": status,
        "current_velocity": current_velocity,
        "target_velocity": target_velocity,
        "velocity_delta": velocity_delta,
        "expected_earnings": expected,
        "dynamic_threshold": dynamic_threshold,
        "projected_shift_earnings": projected_shift_earnings,
    }

    logger.info(
        "Evaluated goal %s for driver %s | expected=%.2f | delta=%.2f | "
        "threshold=%.2f | hours=%.2f | status=%s",
        getattr(goal, "goal_id", None),
        getattr(goal, "driver_id", None),
        expected,
        velocity_delta,
        dynamic_threshold,
        goal.current_hours,
        status,
    )

    return result