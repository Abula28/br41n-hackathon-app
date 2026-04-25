# Dream Generator — Backend

The backend is a Python / FastAPI server that runs the full EEG-to-image pipeline. It simulates brain activity, classifies it into sleep states, builds evolving image prompts, and streams AI-generated frames to connected clients over WebSocket.

---

## Project Overview

Each WebSocket connection starts a self-contained dream session. The session maintains a persistent visual identity (base scene, color palette, camera composition) that never changes within a session, while atmospheric details evolve frame by frame driven by the simulated EEG signal. This produces a stream of images that feel like a continuous dream rather than unrelated AI outputs.

Generated images are also saved to disk at `assets/generated_images/` for post-session review.

---

## Architecture

```
main.py  (FastAPI + WebSocket handler)
  |
  +-- eeg/simulator.py        EEGContinuousSimulator — temporally coherent EEG readings
  |       |
  +-- eeg/analyzer.py         Classifies EEG into stage / intensity / mood
  |       |
  +-- ai/prompt_builder.py    DreamSession + DreamIdentity — evolving SD prompt
  |       |
  +-- ai/image_generator.py   Cloudflare Workers AI HTTP client
  |
  core/config.py              Settings loaded from .env
```

---

## Module Reference

### `eeg/simulator.py`

Produces synthetic EEG readings modelled on real physiological frequency bands:

| Band  | Hz range | Role                                |
| ----- | -------- | ----------------------------------- |
| Delta | 0.5 – 4  | Deep slow-wave sleep                |
| Theta | 4 – 8    | Drowsiness, light sleep, REM        |
| Alpha | 8 – 13   | Relaxed wakefulness                 |
| Beta  | 13 – 30  | Active arousal                      |
| Gamma | 30 – 100 | High cognitive load, vivid dreaming |

Each reading also includes `heart_rate` (BPM) and `movement` (body movement index 0.0 – 1.0).

**`EEGContinuousSimulator`** maintains a current sleep stage and drifts between stages gradually. A stage holds for a minimum of 4 frames before a change is considered, and then only with 20% probability. When changing, the current stage is down-weighted to prevent immediately repeating the same stage. This replicates a realistic sleep cycle progression rather than random stage jumping.

### `eeg/analyzer.py`

Takes an `EEGReading` and returns an `EEGAnalysis` with three fields:

- **`stage`** — classified by dominant EEG band:
  - `deep_sleep` — delta dominant, gamma < 0.15
  - `rem` — theta or beta dominant, gamma > 0.10
  - `light_sleep` — theta or alpha dominant
  - `transition` — no clear dominant band
- **`intensity`** — arousal index: `0.55 * beta + 0.35 * gamma + 0.10 * movement`, clamped to [0, 1]
- **`mood`** — derived from stage + intensity: `calm`, `soft`, `vivid`, `abstract`, or `chaotic`

### `ai/prompt_builder.py`

The core of the dream continuity system. Contains two key data structures:

**`DreamIdentity`** — created once per session at the first frame and never changes:

- `archetype` — the base scene (e.g. "submerged obsidian cathedral filled with bioluminescent veins")
- `composition` — camera framing (e.g. "extreme wide shot, epic scale, rule of thirds")
- `color_palette` — dominant hues (e.g. "deep indigo and cold bioluminescent teal")

**`DreamSession`** — tracks mutable state across frames:

- `frame` — frame counter
- `phase_index` — dream narrative phase (0–3), advances every 8 frames
- `base_seed` — random integer set at session start; used to derive per-frame seeds
- `prev_stage` / `prev_mood` — used to detect transitions between states

**`build_prompt(analysis, session)`** composes the final prompt by combining:

1. The current dream phase narrative ("as the dream begins to form", "deepening into the dream", etc.)
2. An intensity descriptor based on the current EEG arousal level
3. The locked archetype from `DreamIdentity`
4. An optional stage-transition cue when the sleep stage changes from the previous frame
5. A mood-driven atmosphere layer
6. The locked color palette and composition
7. Fixed style anchors present in every frame: `cinematic volumetric lighting, neon chromatic glow, futuristic surreal dreamscape, ultra-detailed 8k, photorealistic atmosphere, masterpiece`

The session is advanced (frame counter + phase index) inside `build_prompt()` after the prompt is assembled.

### `ai/image_generator.py`

Async HTTP client for the Cloudflare Workers AI Stable Diffusion XL endpoint. Accepts a `seed` integer for reproducibility. Uses the per-frame seed `base_seed + frame * 7` to produce slowly varying but visually related images across frames.

Retries transient 5xx errors up to 3 times with a 1.5 second delay. Raises immediately on permanent 4xx errors.

### `main.py`

FastAPI application with three endpoints:

**`GET /`** — Health check.

**`GET /session/sample`** — Runs one EEG + analysis + prompt cycle without image generation. Useful for testing the pipeline quickly without consuming Cloudflare API credits.

**`WS /ws/dream`** — The main dream stream. Per-connection state:

- One `DreamSession` + one `EEGContinuousSimulator`, both created at connection time
- Two asyncio events: `stop_event` (disconnect), `pause_requested` (pause signal)
- A background `_message_listener` coroutine that reads client control messages

Each loop iteration races three asyncio tasks:

1. `cycle_task` — runs the full EEG → analysis → prompt → image pipeline
2. `stop_task` — resolves when the client disconnects
3. `pause_task` — resolves when the client sends `{"action": "pause"}`

When `pause_task` wins, the in-flight `cycle_task` is cancelled immediately. The loop then blocks until `{"action": "resume"}` is received. This ensures pause takes effect within milliseconds rather than waiting for the current image generation to complete.

Each successful frame payload contains:

```json
{
  "eeg": {
    "delta": 0.82,
    "theta": 0.12,
    "alpha": 0.05,
    "beta": 0.03,
    "gamma": 0.01,
    "heart_rate": 52,
    "movement": 0.02
  },
  "stage": "deep_sleep",
  "mood": "calm",
  "intensity": 0.04,
  "prompt": "as the dream begins to form, ...",
  "phase": "as the dream begins to form",
  "frame": 1,
  "image": "<base64-encoded PNG>"
}
```

---

## Setup and Running

### Prerequisites

- Python 3.11 or higher
- A Cloudflare account with Workers AI enabled
- A Cloudflare API token with Workers AI permissions

### Installation

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env`:

```
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
```

### Running

```bash
# With auto-reload (development)
python main.py

# Or directly via uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server starts at `http://localhost:8000`.

### Verifying the pipeline

Test the EEG + prompt pipeline without spending Cloudflare credits:

```bash
curl http://localhost:8000/session/sample
```

---

## Dependencies

| Package       | Version | Purpose                              |
| ------------- | ------- | ------------------------------------ |
| fastapi       | 0.115.5 | Web framework and WebSocket support  |
| uvicorn       | 0.32.1  | ASGI server                          |
| httpx         | 0.27.2  | Async HTTP client for Cloudflare API |
| websockets    | 13.1    | WebSocket protocol implementation    |
| python-dotenv | 1.0.1   | `.env` file loading                  |
| numpy         | 2.1.3   | Numerical utilities                  |

---

## Configuration Reference

All settings are in `core/config.py` and read from environment variables:

| Setting                 | Default                                        | Description                        |
| ----------------------- | ---------------------------------------------- | ---------------------------------- |
| `CLOUDFLARE_ACCOUNT_ID` | —                                              | Cloudflare account ID              |
| `CLOUDFLARE_API_TOKEN`  | —                                              | Cloudflare API token               |
| `CF_MODEL`              | `@cf/stabilityai/stable-diffusion-xl-base-1.0` | Workers AI model                   |
| `IMAGE_GEN_MAX_RETRIES` | 3                                              | Retry attempts on transient errors |
| `IMAGE_GEN_RETRY_DELAY` | 1.5s                                           | Delay between retries              |
| `WS_INTERVAL_MIN`       | 2.0s                                           | Minimum pause between frames       |
| `WS_INTERVAL_MAX`       | 3.0s                                           | Maximum pause between frames       |
