# Conflict Fusion & Event Gate
#
# Combines motion_score and audio_score into a single conflict_score
# and classifies severity.
#
# Fusion formula:
#   conflict = (motion * 0.55) + (audio * 0.45)
#   if motion >= 0.6 AND audio >= 0.6:
#       conflict = min(conflict * 1.3, 1.0)   ← amplifier for dual-signal events
#
# Severity thresholds:
#   HIGH   ≥ 0.75
#   MEDIUM ≥ 0.45
#   LOW    ≥ 0.25
#   SAFE   < 0.25
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass

from .motion import MotionResult, motion_to_flag_type
from .audio import AudioResult, audio_to_flag_type

# ── Weights ──────────────────────────────────────────────────────────────────
MOTION_WEIGHT  = 0.55
AUDIO_WEIGHT   = 0.45
AMPLIFIER      = 1.30
AMPLIFIER_GATE = 0.60   # both scores must exceed this for amplifier to apply

# ── Severity thresholds ──────────────────────────────────────────────────────
HIGH_THRESHOLD   = 0.75
MEDIUM_THRESHOLD = 0.45
LOW_THRESHOLD    = 0.25


@dataclass
class FusionResult:
    severity:      str    # "high" | "medium" | "low" | "safe"
    conflict:      float  # 0.0 – 1.0
    flag_type:     str | None
    motion_score:  float
    audio_score:   float
    amplified:     bool   # True if dual-signal amplifier was applied


def fuse(motion: MotionResult, audio: AudioResult) -> FusionResult:
    """
    Fuse motion and audio scores into a single conflict score.
    Determine severity.
    """
    ms = motion.score
    aus = audio.score

    # ── Weighted fusion ──────────────────────────────────────────────────────
    conflict = (ms * MOTION_WEIGHT) + (aus * AUDIO_WEIGHT)

    # ── Dual-signal amplifier ────────────────────────────────────────────────
    amplified = False
    if ms >= AMPLIFIER_GATE and aus >= AMPLIFIER_GATE:
        conflict  = min(conflict * AMPLIFIER, 1.0)
        amplified = True

    # ── Severity classification ──────────────────────────────────────────────
    if conflict >= HIGH_THRESHOLD:
        severity = "high"
    elif conflict >= MEDIUM_THRESHOLD:
        severity = "medium"
    elif conflict >= LOW_THRESHOLD:
        severity = "low"
    else:
        severity = "safe"

    # ── Flag type: motion takes priority, fall back to audio ────────────────
    flag_type = None
    if severity != "safe":
        flag_type = motion_to_flag_type(motion.event_type) or audio_to_flag_type(audio.classification)
        if not flag_type:
            flag_type = "sustained_stress"

    return FusionResult(
        severity=severity,
        conflict=round(conflict, 4),
        flag_type=flag_type,
        motion_score=round(ms, 4),
        audio_score=round(aus, 4),
        amplified=amplified,
    )