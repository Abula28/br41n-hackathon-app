"""
Prompt Builder
--------------
Maps EEG analysis to one of six fixed dream-world prompts using deterministic
rules based on sleep stage, mood, and intensity.

Each world has a clear visual identity designed for a centered walking-path
perspective, so the generated image always feels like an environment the viewer
is walking through.

DreamSession is kept for per-connection state: seed derivation, frame counting,
and dream-phase narrative progression.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from eeg.analyzer import EEGAnalysis

# ---------------------------------------------------------------------------
# Six fixed world prompts — selected deterministically from EEG state
# ---------------------------------------------------------------------------

_WORLD_PROMPTS: dict[int, str] = {
    1: (
        "surreal dream landscape with floating islands, glowing sky, fantasy pathway, "
        "cinematic perspective, vibrant colors, soft clouds, ultra detailed, 8k"
    ),
    2: (
        "coastal walkway toward ocean sunset, golden hour lighting, waves and cliffs, "
        "centered path perspective, cinematic colors, dreamy atmosphere, ultra detailed, 8k"
    ),
    3: (
        "cyberpunk neon city street, glowing signs, rain reflections, centered road perspective, "
        "cinematic night lighting, purple blue neon atmosphere, ultra detailed, 8k"
    ),
    4: (
        "modern cozy house interior hallway with open view to garden, centered walking perspective, "
        "warm lighting, wooden floor, soft sunlight, cinematic composition, ultra detailed, 8k"
    ),
    5: (
        "sunny summer park path, green grass, colorful flowers, trees on both sides, "
        "centered walking path perspective, warm sunlight, peaceful atmosphere, "
        "cinematic composition, ultra detailed, 8k"
    ),
    6: (
        "cinematic winter forest path, snow covered trees, centered walking path perspective, "
        "soft fog, blue cold atmosphere, ground level camera, leading lines, "
        "ultra detailed, photorealistic, 8k, cinematic lighting"
    ),
}

_WORLD_NAMES: dict[int, str] = {
    1: "Floating Islands",
    2: "Coastal Sunset",
    3: "Neon City",
    4: "Cozy Hallway",
    5: "Summer Park",
    6: "Winter Forest",
}

_NEGATIVE_PROMPT = (
    "blurry, low quality, watermark, text, signature, ugly, deformed, "
    "poorly drawn, duplicate, extra limbs, bad anatomy, "
    "cartoon, anime, flat colors, overexposed, noise, grain"
)

# ---------------------------------------------------------------------------
# Dream phase narrative — advances every ~8 frames
# ---------------------------------------------------------------------------

PHASE_TRANSITIONS = [
    "as the dream begins to form",
    "deepening into the dream",
    "fully immersed in the dream",
    "approaching the edge of waking",
]


# ---------------------------------------------------------------------------
# Prompt selection — deterministic, driven by EEG analysis
# ---------------------------------------------------------------------------

def _select_prompt(analysis: EEGAnalysis) -> tuple[int, str, str]:
    """
    Map EEG analysis to a world prompt ID.

    Priority order (first match wins):
      1. chaotic mood                         → Neon City (high arousal)
      2. REM + vivid mood                     → Floating Islands
      3. calm mood                            → Summer Park
      4. deep_sleep stage                     → Winter Forest
      5. light_sleep + soft mood              → Coastal Sunset
      6. everything else (transition/abstract)→ Cozy Hallway
    """
    stage = analysis.stage
    mood = analysis.mood

    if mood == "chaotic":
        pid = 3
    elif stage == "rem" and mood == "vivid":
        pid = 1
    elif mood == "calm":
        pid = 5
    elif stage == "deep_sleep":
        pid = 6
    elif stage == "light_sleep" and mood == "soft":
        pid = 2
    else:
        pid = 4

    return pid, _WORLD_PROMPTS[pid], _WORLD_NAMES[pid]


# ---------------------------------------------------------------------------
# Session state — per-connection, persists across frames
# ---------------------------------------------------------------------------

@dataclass
class DreamSession:
    """
    Tracks frame count, seed, and dream-phase progression for one WebSocket
    connection. Prompt content is now fixed per EEG state, so session state
    is used only for seed derivation and phase narrative.
    """
    frame: int = 0
    base_seed: int = field(default_factory=lambda: random.randint(100_000, 999_999))
    phase_index: int = 0  # 0–3

    def get_frame_seed(self) -> int:
        """Slowly varying seed: keeps adjacent frames visually related."""
        return self.base_seed + self.frame * 7

    @property
    def current_phase(self) -> str:
        return PHASE_TRANSITIONS[self.phase_index]

    def advance(self) -> None:
        self.frame += 1
        if self.frame % 8 == 0 and self.phase_index < 3:
            self.phase_index += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_prompt(analysis: EEGAnalysis, session: DreamSession) -> dict[str, str | int]:
    """
    Select the appropriate world prompt for the current EEG state and advance
    the session by one frame.

    Returns a dict with:
        prompt             → positive prompt string
        negative_prompt    → negative prompt string
        selected_prompt_id → int 1–6
        world_name         → human-readable world label
    """
    prompt_id, prompt_text, world_name = _select_prompt(analysis)
    session.advance()

    return {
        "prompt": prompt_text,
        "negative_prompt": _NEGATIVE_PROMPT,
        "selected_prompt_id": prompt_id,
        "world_name": world_name,
    }
