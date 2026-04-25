# Dream Generator — Frontend

The frontend is a React / TypeScript single-page application that connects to the backend over WebSocket and renders a real-time, cinematic display of AI-generated dream imagery alongside live EEG signal data.

---

## Project Overview

The interface is designed as a full-screen HUD (heads-up display). The center canvas shows the evolving dream image with smooth crossfade transitions between frames. The left panel displays the live EEG frequency band readings and biometric data. The right panel shows the classified neural state: sleep stage, mood, intensity, dream phase, and the active image generation prompt.

The visual design uses a dark futuristic aesthetic with neon accents, scanline overlays, and a monospace font system. All transitions are handled with CSS keyframe animations rather than JavaScript timers to stay smooth even under load.

---

## Architecture

The application is a single component tree with no routing and no external state management library. All WebSocket logic lives in a `useEffect` inside `DreamCanvas.tsx`.

```
App.tsx
  |
  DreamCanvas.tsx       (main component — layout, state, WebSocket)
    |
    +-- EEGBar               renders one EEG frequency band as a labeled progress bar
    +-- StageBadge           renders the current sleep stage label with stage-specific color
    +-- IntensityMeter       renders a segmented bar showing arousal level
    +-- ConnectionDot        renders the live / connecting / error status indicator
    +-- DreamPhaseIndicator  renders the current dream narrative phase
```

---

## Layout

The app uses a CSS Grid layout with three rows: header (48px), main content (flexible), footer (36px).

The main content area is a three-column grid:

| Column | Width | Content |
|---|---|---|
| Left panel | 220px | EEG signal bars, heart rate, movement, decorative waveform |
| Center canvas | Flexible (1fr) | Dream image with crossfade layers, animated grid background, corner brackets |
| Right panel | 260px | Dream phase, sleep stage, mood, intensity meter, active prompt, error notices |

---

## Component Reference

### `DreamCanvas.tsx`

The root component. Manages all state and the WebSocket connection.

**State:**

| State | Type | Description |
|---|---|---|
| `frame` | `DreamFrame \| null` | Latest full payload from the backend |
| `currentImage` | `string` | Data URI of the image currently displayed |
| `prevImage` | `string` | Data URI of the previous image, used for the crossfade out layer |
| `imageKey` | `number` | Incremented on each new image; used as React `key` to re-trigger CSS animations |
| `status` | `"connecting" \| "live" \| "error"` | WebSocket connection state |
| `frameCount` | `number` | Total frames received in this session |
| `isGenerating` | `boolean` | Whether the backend is currently generating (controls pause/resume) |

**Refs:**

| Ref | Purpose |
|---|---|
| `wsRef` | Holds the `WebSocket` instance so `toggleGeneration()` can send messages outside the `useEffect` closure |
| `currentImageRef` | Mirrors `currentImage` state as a ref so the `onmessage` handler always sees the latest value without stale closure issues |
| `isGeneratingRef` | Mirrors `isGenerating` state as a ref for the same reason |

**Crossfade implementation:**

Two `<img>` elements are rendered, absolutely positioned and centered over each other in the canvas section. When a new image arrives:

1. The old `currentImage` is stored in `prevImage` via `currentImageRef` (avoids stale closure).
2. `currentImage` is updated to the new URI.
3. `imageKey` is incremented, causing React to remount both `<img>` elements with new keys.
4. The previous image element (`prev-{key}`) plays `crossfade-out`: starts at full opacity and fades to zero with a blur.
5. The current image element (`curr-{key}`) plays `crossfade-in`: starts blurred and dark, arrives at full sharpness and brightness.

Both animations run for 1.6 seconds. The transition feels like one dream image dissolving into the next rather than a hard swap.

**Pause / Resume:**

The PAUSE / RESUME button calls `toggleGeneration()`, which:
1. Reads the current state from `isGeneratingRef.current` (not stale React state)
2. Updates both the ref and the React state
3. Sends `{"action": "pause"}` or `{"action": "resume"}` over the WebSocket

While `isGenerating` is false, a semi-transparent overlay with "DREAM PAUSED" is rendered over the canvas. The `onmessage` handler also checks `isGeneratingRef.current` before processing new image data, so if the backend sends a late frame during the pause window, the image will not update.

### `EEGBar`

Renders a labeled progress bar for a single EEG band. The bar width transitions smoothly over 0.8 seconds with a cubic-bezier easing when the value changes between frames.

### `StageBadge`

Renders the sleep stage label as a bordered badge. The border, text, background tint, and glow use the stage-specific color from `STAGE_COLOR`.

### `IntensityMeter`

Renders 20 segments. Each active segment is colored with `hsl(120 - hue * 1.2, 100%, 55%)`, producing a green-to-red gradient as intensity increases. Transitions are 0.6 seconds.

### `DreamPhaseIndicator`

Displays the current dream phase label received from the backend alongside a phase glyph (◌ → ◎ → ● → ◑) that advances through the session narrative arc.

---

## WebSocket Protocol

The frontend connects to `ws://localhost:8000/ws/dream` on mount and closes the connection on unmount.

**Incoming messages** (from server, JSON):

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
  "image": "<base64-encoded PNG>",
  "error": null
}
```

**Outgoing messages** (from client, JSON):

```json
{ "action": "pause" }
{ "action": "resume" }
```

---

## Animations

All keyframe animations are defined in `index.css`:

| Animation | Duration | Description |
|---|---|---|
| `crossfade-in` | 1.6s | New image: blurred and dark to sharp and full brightness |
| `crossfade-out` | 1.6s | Previous image: sharp to blurred and fully transparent |
| `pulse-ring` | 2s | Connection status dot ring pulse when live |
| `blink` | 1s | Status dot blink when connecting or in error state |
| `slide-in` | 0.4s | Stage badge, mood label, prompt text entrance |
| `flicker` | 8s | Header logo subtle opacity flicker |
| `grid-move` | 8s | Canvas background grid scrolling diagonally |
| `spin` | 1.2s | Loading spinner shown before the first image arrives |

---

## Setup and Running

### Prerequisites

- Node.js 18 or higher
- npm
- Backend running at `http://localhost:8000`

### Installation

```bash
cd frontend
npm install
```

### Running (development)

Start the backend first, then:

```bash
npm run dev
```

The app starts at `http://localhost:5173` with hot module replacement enabled.

### Building for production

```bash
npm run build
```

Output is written to `dist/`. Preview the production build locally:

```bash
npm run preview
```

---

## Dependencies

**Runtime:**

| Package | Version | Purpose |
|---|---|---|
| react | 19.2.5 | UI framework |
| react-dom | 19.2.5 | DOM rendering |

**Development:**

| Package | Version | Purpose |
|---|---|---|
| vite | 8.0.10 | Build tool and dev server |
| typescript | 6.0.2 | Type checking |
| @vitejs/plugin-react | 6.0.1 | React fast refresh integration |
| eslint | 10.2.1 | Linting |

---

## Fonts

Two fonts are loaded from Google Fonts at runtime:

| Font | CSS variable | Usage |
|---|---|---|
| Orbitron | `--font-hud` | Headers, labels, badges, buttons |
| Share Tech Mono | `--font-mono` | EEG values, prompt text, numeric readouts |

---

## Color Reference

| CSS variable | Value | Meaning |
|---|---|---|
| `--bg` | `#00000f` | Page background |
| `--surface` | `#080818` | Panel background |
| `--border` | `#1a1a3e` | Dividers and borders |
| `--cyan` | `#00e5ff` | Primary accent, connection indicators |
| `--purple` | `#7c3aed` | Deep sleep stage, abstract mood |
| `--pink` | `#ff007f` | REM stage, vivid mood, heart rate display |
| `--green` | `#00ff88` | Transition stage, calm mood, live status |
| `--text` | `#c8d0e8` | Primary text |
| `--text-dim` | `#4a5080` | Labels and secondary text |
