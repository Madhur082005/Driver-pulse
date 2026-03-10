"""Heuristics package: motion, audio, gravity, and conflict fusion.

Each module is small and focused so it can run cheaply on the edge.
"""

from .audio import AudioClassifier, AudioResult, audio_to_flag_type
from .motion import classify_motion, MotionResult, motion_to_flag_type
from .gravity import GravityCompensator
from .fusion import fuse, FusionResult

__all__ = [
    "AudioClassifier",
    "AudioResult",
    "audio_to_flag_type",
    "classify_motion",
    "MotionResult",
    "motion_to_flag_type",
    "GravityCompensator",
    "fuse",
    "FusionResult",
]
