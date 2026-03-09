# heuristics/audio.py
# ─────────────────────────────────────────────────────────────────────────────
# Audio Classifier
#
# KEY INSIGHT FROM DATA:
#   All audio dB ranges overlap completely (50–98 dB across ALL classes).
#   Decibel level alone is USELESS as a discriminator.
#
#   The ONLY reliable signal is sustained_duration_sec:
#     quiet / normal / conversation / loud → sustained_duration ALWAYS = 0
#     very_loud                            → sustained_duration > 0 (mean 78s)
#     argument                             → sustained_duration > 0 (mean 101s)
#
# Therefore the classifier ignores dB level for classification and uses
# sustained_duration as the primary gate.
#
# Audio baseline dB is still tracked for the output log (raw_value field).
# ─────────────────────────────────────────────────────────────────────────────

from dataclasses import dataclass

# ── Thresholds ───────────────────────────────────────────────────────────────
ARGUMENT_DURATION_SEC  = 90.0    # sustained ≥ 90s + 10dB above baseline → argument
VERY_LOUD_DURATION_SEC = 50.0    # sustained ≥ 50s → very loud
ARGUMENT_DB_ABOVE      = 10.0    # dB above baseline required for argument classification

AUDIO_BASELINE_DB      = 68.0    # dataset mean (calibrated in first 60s of trip)
CALIBRATION_WINDOW_SEC = 60.0    # seconds to collect baseline samples


@dataclass
class AudioResult:
    classification: str    # "background" | "elevated" | "very_loud" | "argument"
    score:          float  # 0.0 – 1.0 (audio component of conflict fusion)
    sustained_sec:  float  # raw sustained_duration from sensor
    db_level:       float  # raw dB reading


class AudioClassifier:
    """
    Stateful audio classifier.
    Calibrates a per-trip dB baseline in the first 60 seconds,
    then classifies each sample using sustained_duration_sec.

    State: rolling baseline + elapsed time counter.
    Memory: ~200 bytes.
    """

    def __init__(self):
        self.baseline_db:    float       = AUDIO_BASELINE_DB
        self._baseline_samples: list[float] = []
        self._calibrated:    bool        = False

    def classify(
        self,
        db_level:         float,
        sustained_sec:    float,
        elapsed_seconds:  float,
    ) -> AudioResult:
        """
        Classify one audio sample.

        During the first 60 seconds, accumulate baseline samples.
        After 60 seconds, baseline is fixed and used for argument detection.
        """
        # ── Baseline calibration (first 60s) ────────────────────────────────
        if not self._calibrated:
            if elapsed_seconds <= CALIBRATION_WINDOW_SEC:
                self._baseline_samples.append(db_level)
            else:
                if self._baseline_samples:
                    self.baseline_db = sum(self._baseline_samples) / len(self._baseline_samples)
                self._baseline_samples = []   # free memory
                self._calibrated = True

        # ── Classification (sustained_duration is the only real discriminator) ──
        if sustained_sec == 0:
            # All quiet/normal/conversation/loud classes land here
            # We cannot distinguish them — classify as background
            return AudioResult("background", 0.0, sustained_sec, db_level)

        db_above_baseline = db_level - self.baseline_db

        if sustained_sec >= ARGUMENT_DURATION_SEC and db_above_baseline >= ARGUMENT_DB_ABOVE:
            return AudioResult("argument",  0.92, sustained_sec, db_level)

        if sustained_sec >= VERY_LOUD_DURATION_SEC:
            return AudioResult("very_loud", 0.65, sustained_sec, db_level)

        # sustained > 0 but < 50s — something is elevated
        return AudioResult("elevated",  0.35, sustained_sec, db_level)


def audio_to_flag_type(classification: str) -> str | None:
    """Maps audio classification to output log flag_type."""
    mapping = {
        "argument":  "conflict_moment",
        "very_loud": "audio_spike",
        "elevated":  "sustained_stress",
    }
    return mapping.get(classification)