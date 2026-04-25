"""
EEG Simulator
-------------
Produces randomized but physiologically plausible EEG band-power values and
biometric signals. Values are expressed as relative power (0.0 – 1.0) so
that downstream modules can treat them uniformly.

Frequency bands (Hz):
  delta  0.5 –  4  → slow-wave / deep sleep
  theta  4   –  8  → drowsiness / light sleep / REM
  alpha  8   – 13  → relaxed wakefulness
  beta   13  – 30  → active thinking / arousal
  gamma  30  – 100 → high cognitive load / vivid dreaming
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class EEGReading:
    delta: float       # 0.0 – 1.0
    theta: float       # 0.0 – 1.0
    alpha: float       # 0.0 – 1.0
    beta: float        # 0.0 – 1.0
    gamma: float       # 0.0 – 1.0
    heart_rate: int    # beats per minute
    movement: float    # 0.0 – 1.0  (body movement index)

    def to_dict(self) -> dict:
        return {
            "delta": round(self.delta, 4),
            "theta": round(self.theta, 4),
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta, 4),
            "gamma": round(self.gamma, 4),
            "heart_rate": self.heart_rate,
            "movement": round(self.movement, 4),
        }


# Each sleep-stage profile defines (min, max) for every channel.
# The simulator picks from one stage at random (weighted) each call,
# which lets the signal drift naturally over time.
_STAGE_PROFILES: dict[str, dict[str, tuple[float, float]]] = {
    "deep_sleep": {
        "delta":      (0.60, 0.95),
        "theta":      (0.05, 0.20),
        "alpha":      (0.02, 0.10),
        "beta":       (0.01, 0.08),
        "gamma":      (0.00, 0.05),
        "heart_rate": (45, 58),
        "movement":   (0.00, 0.05),
    },
    "light_sleep": {
        "delta":      (0.20, 0.50),
        "theta":      (0.30, 0.60),
        "alpha":      (0.10, 0.30),
        "beta":       (0.05, 0.20),
        "gamma":      (0.01, 0.10),
        "heart_rate": (55, 68),
        "movement":   (0.05, 0.25),
    },
    "rem": {
        "delta":      (0.05, 0.20),
        "theta":      (0.40, 0.75),
        "alpha":      (0.15, 0.35),
        "beta":       (0.20, 0.50),
        "gamma":      (0.10, 0.40),
        "heart_rate": (58, 80),
        "movement":   (0.00, 0.10),  # REM atonia — very little movement
    },
    "transition": {
        "delta":      (0.10, 0.40),
        "theta":      (0.20, 0.50),
        "alpha":      (0.20, 0.45),
        "beta":       (0.15, 0.40),
        "gamma":      (0.05, 0.20),
        "heart_rate": (60, 75),
        "movement":   (0.10, 0.40),
    },
}

# Probability weights for spontaneous stage selection
_STAGE_WEIGHTS = [0.30, 0.30, 0.25, 0.15]  # deep, light, rem, transition
_STAGES = list(_STAGE_PROFILES.keys())


def _gauss_clamp(center: float, sigma: float, lo: float, hi: float) -> float:
    """Gaussian sample clamped to [lo, hi]."""
    return max(lo, min(hi, random.gauss(center, sigma)))


class EEGContinuousSimulator:
    """
    Produces temporally coherent EEG readings.

    Instead of picking a random stage each call, the simulator drifts between
    stages gradually — just like a real sleep cycle. Stage holds for a minimum
    number of frames before considering a change.
    """

    _STAGE_HOLD_MIN = 4      # minimum frames per stage before change is possible
    _STAGE_CHANGE_PROB = 0.2  # probability of changing stage after min hold

    def __init__(self) -> None:
        self._stage: str = random.choices(_STAGES, weights=_STAGE_WEIGHTS, k=1)[0]
        self._frames_in_stage: int = 0

    @property
    def current_stage(self) -> str:
        return self._stage

    def next(self) -> "EEGReading":
        """Return the next temporally coherent EEG reading."""
        self._frames_in_stage += 1
        if (
            self._frames_in_stage >= self._STAGE_HOLD_MIN
            and random.random() < self._STAGE_CHANGE_PROB
        ):
            self._stage = self._pick_next_stage()
            self._frames_in_stage = 0
        return simulate_eeg(stage_hint=self._stage)

    def _pick_next_stage(self) -> str:
        """Prefer adjacent stages; reduce probability of repeating current."""
        weights = list(_STAGE_WEIGHTS)
        idx = _STAGES.index(self._stage)
        weights[idx] *= 0.2  # strongly discourage same stage
        return random.choices(_STAGES, weights=weights, k=1)[0]


def simulate_eeg(stage_hint: str | None = None) -> EEGReading:
    """
    Generate one synthetic EEG reading.

    Parameters
    ----------
    stage_hint : str | None
        If provided, forces sampling from that stage profile.
        Otherwise a stage is chosen randomly with realistic weights.

    Returns
    -------
    EEGReading
    """
    if stage_hint and stage_hint in _STAGE_PROFILES:
        stage = stage_hint
    else:
        stage = random.choices(_STAGES, weights=_STAGE_WEIGHTS, k=1)[0]

    profile = _STAGE_PROFILES[stage]

    def sample(key: str) -> float:
        lo, hi = profile[key]
        center = (lo + hi) / 2
        sigma = (hi - lo) / 6  # ≈ 99.7 % of values within range
        return _gauss_clamp(center, sigma, lo, hi)

    hr_lo, hr_hi = profile["heart_rate"]
    heart_rate = int(random.uniform(hr_lo, hr_hi))

    return EEGReading(
        delta=sample("delta"),
        theta=sample("theta"),
        alpha=sample("alpha"),
        beta=sample("beta"),
        gamma=sample("gamma"),
        heart_rate=heart_rate,
        movement=sample("movement"),
    )
