# Motion Classifier — Braking & Cornering

# Thresholds derived from dataset percentile analysis:
#   accel_y (braking):   p80=1.60g  p90=1.80g  p95=2.00g  harsh_mean=3.24g
#   accel_x (cornering): p80=2.60g  p90=2.80g  p95=2.90g  harsh_mean=4.30g

# Speed-delta validation: a large Y-axis spike without a corresponding
# speed drop is road noise / pothole, not braking. We store only the
# previous speed (1 float) to validate.

# All functions are stateless per-sample (O(1), no rolling windows).
# Variable sampling rate in the dataset means rolling windows are unsafe.

from dataclasses import dataclass

#Braking thresholds (accel_y, gravity-compensated) 
EMERGENCY_STOP_G  = 4.0    # score 1.00
HARSH_BRAKE_G     = 2.8    # score 0.82
MODERATE_BRAKE_G  = 1.80   # score 0.48
SOFT_BRAKE_G      = 1.60   # score 0.20

# Speed-delta gates: spike must have matching deceleration to count as braking
EMERGENCY_SPEED_DELTA  = -15.0   # km/h change required
HARSH_SPEED_DELTA      = -10.0
MODERATE_SPEED_DELTA   = -5.0

#Cornering thresholds (abs(accel_x), gravity-compensated)
HARSH_CORNER_G    = 3.5    # score 0.85
MODERATE_CORNER_G = 2.80   # score 0.50


@dataclass
class MotionResult:
    event_type:  str    # "emergency_stop" | "harsh_brake" | "moderate_brake" |
                        # "soft_brake" | "harsh_corner" | "moderate_corner" |
                        # "road_noise" | "normal"
    score:       float  # 0.0 – 1.0 (motion component of conflict fusion)
    axis:        str    # "y_brake" | "x_corner" | "none"


def classify_motion(
    comp_y:       float,   # gravity-compensated accel_y (braking axis)
    comp_x:       float,   # gravity-compensated accel_x (lateral axis)
    speed_kmh:    float,   # current speed
    prev_speed:   float,   # speed from the previous sample (for delta validation)
) -> MotionResult:
    """
    Classifies one sensor sample into a motion event.

    Returns the single most severe event detected (braking takes priority
    over cornering when both exceed thresholds simultaneously).

    Speed-delta validation prevents potholes/road bumps from being
    misclassified as braking events.
    """
    speed_delta = speed_kmh - prev_speed   # negative = decelerating

    abs_y = abs(comp_y)
    abs_x = abs(comp_x)

    # ── Braking (Y axis) ────────────────────────────────────────────────────
    if abs_y >= EMERGENCY_STOP_G:
        if speed_delta <= EMERGENCY_SPEED_DELTA:
            return MotionResult("emergency_stop", 1.00, "y_brake")
        else:
            # Big spike but no speed drop → road bump, downgrade
            return MotionResult("road_noise", 0.05, "none")

    if abs_y >= HARSH_BRAKE_G:
        if speed_delta <= HARSH_SPEED_DELTA:
            return MotionResult("harsh_brake", 0.82, "y_brake")
        else:
            return MotionResult("road_noise", 0.05, "none")

    if abs_y >= MODERATE_BRAKE_G:
        if speed_delta <= MODERATE_SPEED_DELTA:
            return MotionResult("moderate_brake", 0.48, "y_brake")
        else:
            return MotionResult("road_noise", 0.05, "none")

    # Soft brakes intentionally have NO speed-delta gate.  At 1.6g the
    # deceleration is gentle enough to occur without a large speed drop
    # (e.g., rolling to a stop or speed-bump response).  Higher tiers
    # require a matching speed change to distinguish real braking from
    # road noise / potholes.
    if abs_y >= SOFT_BRAKE_G:
        return MotionResult("soft_brake", 0.20, "y_brake")

    #  Cornering (X axis)
    if abs_x >= HARSH_CORNER_G:
        return MotionResult("harsh_corner", 0.85, "x_corner")

    if abs_x >= MODERATE_CORNER_G:
        return MotionResult("moderate_corner", 0.50, "x_corner")

    return MotionResult("normal", 0.0, "none")


def motion_to_flag_type(event_type: str) -> str | None:
    """Maps internal event_type to the flag_type used in the output log."""
    mapping = {
        "emergency_stop": "harsh_braking",
        "harsh_brake":    "harsh_braking",
        "moderate_brake": "moderate_brake",
        "harsh_corner":   "harsh_braking",   # same flag bucket
        "moderate_corner": "moderate_brake",
    }
    return mapping.get(event_type)