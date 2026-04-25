"""
Prompt Builder
--------------
Converts an EEGAnalysis into an evolving, cinematically consistent text prompt.

A DreamSession persists across frames. Each call to build_prompt() evolves the
prompt incrementally — the scene morphs rather than jumps, producing visual
continuity. Style anchors (volumetric neon, cinematic, futuristic surreal) are
fixed in every frame so SD maintains a consistent aesthetic direction.
"""

import random
from dataclasses import dataclass, field
from eeg.analyzer import EEGAnalysis

# ---------------------------------------------------------------------------
# Fixed style anchors — appear in EVERY prompt for visual consistency
# ---------------------------------------------------------------------------

_STYLE_ANCHORS = (
    "cinematic volumetric lighting, neon chromatic glow, "
    "futuristic surreal dreamscape, ultra-detailed 8k, "
    "photorealistic atmosphere, masterpiece, artstation"
)

_NEGATIVE_PROMPT = (
    "blurry, low quality, watermark, text, signature, ugly, deformed, "
    "poorly drawn, duplicate, extra limbs, bad anatomy, "
    "cartoon, anime, flat colors, overexposed, noise, grain"
)

# ---------------------------------------------------------------------------
# Base dream archetypes — one chosen at session start, persistent all session
# ---------------------------------------------------------------------------

_ARCHETYPES: dict[str, list[str]] = {
    "deep_sleep": [
        "submerged obsidian cathedral filled with bioluminescent veins",
        "infinite crystalline abyss glowing from within",
        "ancient frozen palace suspended in dark space",
        "colossal underwater ruin wrapped in cold blue light",
    ],
    "light_sleep": [
        "floating island archipelago dissolving into violet mist",
        "half-melted clockwork city suspended at dusk",
        "fog-shrouded coastline where reality bleeds into watercolor",
        "spiraling greenhouse tower drifting above silent clouds",
    ],
    "rem": [
        "fractal alien metropolis beneath twin neon suns",
        "impossible staircase city folded through a nebula",
        "living organic architecture breathing with neon light",
        "mirrored labyrinth with dimensions folding into each other",
    ],
    "transition": [
        "threshold portal between two colliding worlds",
        "bridge of liquid starlight over a void of galaxies",
        "corridor of shifting doorways each opening to another reality",
        "lone figure at the edge of a universe being born",
    ],
}

# ---------------------------------------------------------------------------
# Dominant color palettes per archetype stage — fixed for session
# ---------------------------------------------------------------------------

_PALETTES: dict[str, list[str]] = {
    "deep_sleep": [
        "deep indigo and cold bioluminescent teal",
        "midnight blue and faint violet bioluminescence",
        "obsidian black and electric indigo",
    ],
    "light_sleep": [
        "soft lavender and warm amber haze",
        "dusty rose and pale gold shimmer",
        "muted violet and soft cerulean glow",
    ],
    "rem": [
        "electric magenta and neon cyan",
        "plasma orange and ultraviolet blue",
        "chromatic acid green and deep crimson",
    ],
    "transition": [
        "iridescent violet and liquid gold",
        "prismatic silver and aurora green",
        "deep teal and burning amber",
    ],
}

# ---------------------------------------------------------------------------
# Mood atmosphere layers — evolve per frame based on current EEG mood
# ---------------------------------------------------------------------------

_MOOD_ATMOSPHERE: dict[str, list[str]] = {
    "calm": [
        "bathed in soft indigo moonlight, perfectly still, quiet majesty",
        "suffused with deep violet radiance, serene and timeless",
        "glowing faintly with cold bioluminescence, absolute silence",
    ],
    "soft": [
        "wrapped in pastel aurora light, hazy and tender",
        "veiled in iridescent mist with warm golden undertones",
        "shimmering with soft prismatic refraction, dreamlike",
    ],
    "vivid": [
        "electrified with hyper-saturated neon plasma, intensely alive",
        "blazing with chromatic aberration, colors bleeding through space",
        "pulsing with electric cyan and magenta energy waves",
    ],
    "abstract": [
        "fractured into non-euclidean geometries, layered reality planes",
        "dissolving into symbolic shapes and fragmented dimensions",
        "tessellated across impossible space-time folds",
    ],
    "chaotic": [
        "shattered by turbulent energy vortices, kinetic explosion of light",
        "torn by recursive fractal storms, violent chromatic distortion",
        "overwhelmed by cascading dimensional collapse",
    ],
}

# ---------------------------------------------------------------------------
# Intensity descriptors
# ---------------------------------------------------------------------------

_INTENSITY_DESCRIPTORS: dict[str, list[str]] = {
    "low":  ["barely visible traces of", "ghostly outline of", "whispered suggestion of"],
    "mid":  ["richly detailed", "glowing presence of", "clearly emerging"],
    "high": ["blazing manifestation of", "overwhelming surge of", "violently vivid"],
}

# ---------------------------------------------------------------------------
# Dream phase narrative arc — advances every ~8 frames
# ---------------------------------------------------------------------------

PHASE_TRANSITIONS = [
    "as the dream begins to form",
    "deepening into the dream",
    "fully immersed in the dream",
    "approaching the edge of waking",
]

# ---------------------------------------------------------------------------
# Cinematic composition modifiers — fixed for session
# ---------------------------------------------------------------------------

_COMPOSITIONS = [
    "extreme wide shot, epic scale, rule of thirds",
    "dramatic low angle, towering perspective, deep focus",
    "bird's eye view, infinite depth, overhead",
    "Dutch angle, disorienting beauty, asymmetric framing",
    "medium shot, intimate scale, centered symmetry",
]


@dataclass
class DreamIdentity:
    """Persistent visual identity chosen once at session start."""
    archetype: str        # base scene — never changes
    composition: str      # camera framing — never changes
    color_palette: str    # dominant hues — never changes


@dataclass
class DreamSession:
    """
    Per-connection temporal state. Pass into build_prompt() each cycle.
    Maintains dream continuity across frames.
    """
    frame: int = 0
    identity: DreamIdentity | None = None
    base_seed: int = field(default_factory=lambda: random.randint(100_000, 999_999))
    prev_stage: str = ""
    prev_mood: str = ""
    phase_index: int = 0  # 0-3

    def get_frame_seed(self) -> int:
        """Slowly varying seed: maintains visual consistency while evolving."""
        return self.base_seed + self.frame * 7

    @property
    def current_phase(self) -> str:
        return PHASE_TRANSITIONS[self.phase_index]

    def initialize(self, first_stage: str) -> None:
        """Called on first frame. Locks the dream identity for the session."""
        archetype = random.choice(_ARCHETYPES[first_stage])
        composition = random.choice(_COMPOSITIONS)
        color_palette = random.choice(_PALETTES[first_stage])
        self.identity = DreamIdentity(
            archetype=archetype,
            composition=composition,
            color_palette=color_palette,
        )

    def advance(self, stage: str, mood: str) -> None:
        self.frame += 1
        self.prev_stage = stage
        self.prev_mood = mood
        if self.frame % 8 == 0 and self.phase_index < 3:
            self.phase_index += 1


def _intensity_band(intensity: float) -> str:
    if intensity < 0.33:
        return "low"
    if intensity < 0.66:
        return "mid"
    return "high"


def build_prompt(analysis: EEGAnalysis, session: DreamSession) -> dict[str, str]:
    """
    Build an evolving SD prompt from EEG analysis + session state.

    The archetype, composition, and color palette are locked for the session.
    Atmospherics evolve per-frame with EEG mood and intensity.
    Stage transitions inject a morphing cue for narrative flow.
    """
    if session.identity is None:
        session.initialize(analysis.stage)

    identity = session.identity

    # Atmosphere varies with mood but stays mood-coherent
    atmosphere = random.choice(_MOOD_ATMOSPHERE[analysis.mood])

    # Intensity descriptor
    energy = random.choice(_INTENSITY_DESCRIPTORS[_intensity_band(analysis.intensity)])

    # Stage transition cue — only when stage changes from last frame
    stage_cue = ""
    if session.prev_stage and session.prev_stage != analysis.stage:
        stage_cue = (
            f", transitioning from {session.prev_stage.replace('_', ' ')} "
            f"into {analysis.stage.replace('_', ' ')}"
        )

    prompt = (
        f"{session.current_phase}, {energy} {identity.archetype}{stage_cue}, "
        f"{atmosphere}, {identity.color_palette} color palette, "
        f"{identity.composition}, {_STYLE_ANCHORS}"
    )

    session.advance(analysis.stage, analysis.mood)

    return {
        "prompt": prompt,
        "negative_prompt": _NEGATIVE_PROMPT,
    }
