"""
EEG Analyzer
------------
Classifies a raw EEG reading into a sleep stage, calculates an intensity
score (0–1), and assigns an emotional/perceptual mood label.

Classification logic
--------------------
We use a simple rule-based scoring approach rather than a trained model —
this is intentional for the hackathon so the system has zero inference
overhead and is completely deterministic given the same input.

Stage rules (dominant band heuristic):
  deep_sleep   → delta is the highest band AND gamma < 0.15
  rem          → theta is the highest band AND gamma > 0.10
  light_sleep  → theta is highest OR alpha is highest, and delta is moderate
  transition   → fallback when no band dominates clearly

Intensity = weighted combination of beta + gamma (arousal bands)
Mood      = derived from stage + intensity
"""

from dataclasses import dataclass
from eeg.simulator import EEGReading

# Mood options
MOODS = ["calm", "soft", "vivid", "abstract", "chaotic"]

# Intensity thresholds
_INTENSE_THRESHOLD = 0.55
_CALM_THRESHOLD = 0.25


@dataclass
class EEGAnalysis:
    stage: str      # deep_sleep | light_sleep | rem | transition
    intensity: float  # 0.0 – 1.0
    mood: str       # calm | soft | vivid | abstract | chaotic

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "intensity": round(self.intensity, 4),
            "mood": self.mood,
        }


def _dominant_band(reading: EEGReading) -> str:
    """Return the name of the EEG band with the highest power."""
    bands = {
        "delta": reading.delta,
        "theta": reading.theta,
        "alpha": reading.alpha,
        "beta": reading.beta,
        "gamma": reading.gamma,
    }
    return max(bands, key=bands.__getitem__)


def _classify_stage(reading: EEGReading) -> str:
    """Rule-based sleep-stage classification."""
    dominant = _dominant_band(reading)

    if dominant == "delta" and reading.gamma < 0.15:
        return "deep_sleep"

    if dominant in ("theta", "beta") and reading.gamma > 0.10:
        return "rem"

    if dominant in ("theta", "alpha"):
        return "light_sleep"

    # Mixed or ambiguous signal → transition
    return "transition"


def _compute_intensity(reading: EEGReading) -> float:
    """
    Arousal index: beta and gamma drive intensity.
    Movement adds a small contribution (restless sleep = higher intensity).
    """
    arousal = 0.55 * reading.beta + 0.35 * reading.gamma + 0.10 * reading.movement
    # Clamp to [0, 1]
    return round(min(1.0, max(0.0, arousal)), 4)


def _assign_mood(stage: str, intensity: float) -> str:
    """
    Map stage + intensity to a perceptual mood label.

      deep_sleep  → calm (low) / soft (medium)
      light_sleep → soft (low) / abstract (medium) / chaotic (high)
      rem         → vivid (low-medium) / chaotic (high)
      transition  → abstract (any)
    """
    if stage == "deep_sleep":
        return "calm" if intensity < _INTENSE_THRESHOLD else "soft"

    if stage == "light_sleep":
        if intensity < _CALM_THRESHOLD:
            return "soft"
        if intensity < _INTENSE_THRESHOLD:
            return "abstract"
        return "chaotic"

    if stage == "rem":
        return "chaotic" if intensity >= _INTENSE_THRESHOLD else "vivid"

    # transition
    return "abstract"


def analyze_eeg(reading: EEGReading) -> EEGAnalysis:
    """
    Analyze a single EEG reading and return stage, intensity, and mood.

    Parameters
    ----------
    reading : EEGReading
        Raw EEG data from the simulator.

    Returns
    -------
    EEGAnalysis
    """
    stage = _classify_stage(reading)
    intensity = _compute_intensity(reading)
    mood = _assign_mood(stage, intensity)

    return EEGAnalysis(stage=stage, intensity=intensity, mood=mood)
