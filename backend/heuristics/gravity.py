# heuristics/gravity.py
# ─────────────────────────────────────────────────────────────────────────────
# Gravity Compensation
#
# A phone mounted in a car is tilted — the Z-axis isn't perfectly vertical.
# We calibrate a baseline from the first few stationary samples (speed = 0)
# and subtract it from every reading so only real motion registers.
#
# From the dataset: mean Z at stationary = 9.742g (not 9.8 due to tilt).
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK_Z_BASELINE = 9.742   # from dataset mean (stationary samples)
CALIBRATION_SAMPLES = 3       # number of stationary samples needed to calibrate


class GravityCompensator:
    """
    Stateful calibrator. Calibrates once using the first N stationary samples.
    After calibration, compensate() subtracts the baseline from every reading.

    State: 3 floats (baseline_x, baseline_y, baseline_z) + calibrated bool.
    Memory: ~100 bytes total.
    """

    def __init__(self):
        self._samples_x: list[float] = []
        self._samples_y: list[float] = []
        self._samples_z: list[float] = []
        self.baseline_x: float = 0.0
        self.baseline_y: float = 0.0
        self.baseline_z: float = FALLBACK_Z_BASELINE
        self.calibrated: bool = False

    def feed(self, ax: float, ay: float, az: float, speed_kmh: float) -> bool:
        """
        Feed a raw sample. Returns True once calibration is complete.
        Only accepts samples where the vehicle is stationary (speed = 0).
        """
        if self.calibrated:
            return True

        if speed_kmh == 0.0:
            self._samples_x.append(ax)
            self._samples_y.append(ay)
            self._samples_z.append(az)

        if len(self._samples_x) >= CALIBRATION_SAMPLES:
            self.baseline_x = sum(self._samples_x) / len(self._samples_x)
            self.baseline_y = sum(self._samples_y) / len(self._samples_y)
            self.baseline_z = sum(self._samples_z) / len(self._samples_z)
            self.calibrated = True
            # Free temp buffers
            self._samples_x = []
            self._samples_y = []
            self._samples_z = []

        return self.calibrated

    def compensate(self, ax: float, ay: float, az: float) -> tuple[float, float, float]:
        """
        Returns (cx, cy, cz) — gravity-compensated accelerations.
        Safe to call before calibration (uses fallback baseline).
        """
        return (
            ax - self.baseline_x,
            ay - self.baseline_y,
            az - self.baseline_z,
        )