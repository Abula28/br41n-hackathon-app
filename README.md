# Dream Generator

A real-time AI dream visualization system that converts simulated EEG brain activity into a continuous, evolving sequence of AI-generated images. The system is designed to feel like watching a single dream unfold rather than viewing a series of disconnected images.

---

## Project Overview

Dream Generator simulates what a sleeping brain might "see" by processing synthetic EEG signals through a pipeline that ends with image generation via Cloudflare Workers AI (Stable Diffusion XL). Each session maintains a persistent visual identity — the same base scene, color palette, and camera framing — that evolves gradually as the simulated sleep stage and dream intensity shift over time.

The application is split into two independent services:

- **Backend** — Python / FastAPI server that runs the EEG simulation, analysis, prompt engineering, and image generation pipeline, streaming results to the frontend over a WebSocket connection.
- **Frontend** — React / TypeScript single-page application that renders the live dream visuals with smooth crossfade transitions and displays real-time EEG signal data.

---

## Architecture

```
Browser (React)
     |
     | WebSocket  ws://localhost:8000/ws/dream
     |
FastAPI Server
     |
     +-- EEG Simulator        generates synthetic brain wave data
     |        |
     +-- EEG Analyzer         classifies sleep stage, intensity, mood
     |        |
     +-- Prompt Builder       builds an evolving SD prompt from session state
     |        |
     +-- Image Generator      calls Cloudflare Workers AI (SD XL)
     |
     +-- WebSocket broadcast  sends JSON frame (EEG + image base64) to client
```

A single WebSocket session maintains one `DreamSession` object and one `EEGContinuousSimulator`. These persist for the entire connection, giving the session its temporal coherence. When the connection closes, the session ends and the next connection starts a fresh dream.

---

## System Flow

1. The frontend opens a WebSocket connection to the backend.
2. The backend starts an infinite loop. Each iteration:
   a. The `EEGContinuousSimulator` produces the next EEG reading, drifting slowly between sleep stages rather than jumping randomly.
   b. The `EEGAnalyzer` classifies the reading into a sleep stage (`deep_sleep`, `light_sleep`, `rem`, `transition`), an intensity score (0.0 to 1.0), and a mood label (`calm`, `soft`, `vivid`, `abstract`, `chaotic`).
   c. The `PromptBuilder` combines the EEG analysis with the persistent `DreamSession` to build a Stable Diffusion prompt. The session locks in a base archetype (scene), color palette, and camera composition at the start of the session. These never change. What evolves per frame is the atmospheric layer, intensity descriptor, and dream phase narrative.
   d. The `ImageGenerator` sends the prompt to Cloudflare Workers AI with a slowly varying seed (`base_seed + frame * 7`), which keeps adjacent frames visually related.
   e. The resulting image (PNG bytes) is base64-encoded and sent to the frontend as a JSON payload along with the EEG data and session metadata.
3. The frontend receives the frame, crossfades the new image over the previous one, and updates the EEG signal readouts in the side panels.
4. The client can send `{"action": "pause"}` or `{"action": "resume"}` at any time. Pause cancels the in-flight generation cycle immediately.

---

## Repository Structure

```
hackathon-back/
  backend/
    ai/
      image_generator.py    Cloudflare Workers AI client
      prompt_builder.py     DreamSession, DreamIdentity, prompt evolution logic
    eeg/
      analyzer.py           Sleep stage classification and mood assignment
      simulator.py          Synthetic EEG data + EEGContinuousSimulator
    core/
      config.py             Environment-based settings
    assets/
      generated_images/     Saved PNG frames (gitignored)
    main.py                 FastAPI app, WebSocket handler
    requirements.txt
    .env.example
  frontend/
    src/
      DreamCanvas.tsx       Main React component (layout, crossfade, controls)
      index.css             Global styles and keyframe animations
      App.tsx               Root component
      main.tsx              Entry point
    package.json
    vite.config.ts
```

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- A Cloudflare account with Workers AI enabled
- A Cloudflare API token with `Workers AI` read/write permissions

### 1. Configure Cloudflare credentials

```bash
cd backend
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
```

### 2. Start the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The API server starts at `http://localhost:8000`.

### 3. Start the frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The app opens at `http://localhost:5173`.

---

## Controls

| Control | Action |
|---|---|
| PAUSE button | Sends `{"action": "pause"}` to the backend. Cancels any in-flight generation and stops new cycles. A "DREAM PAUSED" overlay appears over the canvas. |
| RESUME button | Sends `{"action": "resume"}`. The backend picks up a new cycle immediately. |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Yes | Your Cloudflare account ID |
| `CLOUDFLARE_API_TOKEN` | Yes | API token with Workers AI access |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| ASGI server | Uvicorn |
| HTTP client | httpx (async) |
| Image generation | Cloudflare Workers AI — `@cf/stabilityai/stable-diffusion-xl-base-1.0` |
| Frontend framework | React 19 |
| Frontend build tool | Vite |
| Language (frontend) | TypeScript |
| Transport | WebSocket |
