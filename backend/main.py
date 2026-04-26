"""
Dream Generator — FastAPI backend
==================================
Streams AI-generated dream images derived from real CSV or simulated EEG
brain activity.

Endpoints
---------
GET  /              → health check
GET  /session/sample → single EEG + analysis + prompt cycle (no image)
WS   /ws/dream      → real-time dream stream with pause/resume control
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ai.image_generator import generate_image
from ai.prompt_builder import build_prompt, DreamSession
from eeg.analyzer import analyze_eeg
from eeg.csv_reader import EEGDataSource
from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("dream_generator")

IMAGES_DIR = Path(__file__).parent / "assets" / "generated_images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

sample_data_source = EEGDataSource()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Dream Generator starting up.")
    logger.info(
        "Cloudflare account configured: %s",
        bool(settings.CLOUDFLARE_ACCOUNT_ID and settings.CLOUDFLARE_API_TOKEN),
    )
    yield
    logger.info("Dream Generator shutting down.")


app = FastAPI(
    title="Dream Generator API",
    description="Real-time EEG-to-dream image generation backend.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _run_dream_cycle(
    session: DreamSession,
    data_source: EEGDataSource,
    include_image: bool = True,
) -> dict:
    """
    One complete EEG → analysis → prompt → image pipeline.
    Uses session state for temporal continuity and per-frame seed for
    visual consistency.
    """
    sample = data_source.next()
    eeg = sample.reading
    analysis = analyze_eeg(eeg)

    # Capture seed before advance (frame N)
    frame_seed = session.get_frame_seed()

    prompt_data = build_prompt(analysis, session)  # advances session internally

    image_b64: str | None = None
    error: str | None = None

    if include_image:
        try:
            image_bytes = await generate_image(
                prompt=prompt_data["prompt"],
                negative_prompt=prompt_data["negative_prompt"],
                seed=frame_seed,
            )
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            filename = f"{timestamp}_{analysis.stage}_{analysis.mood}.png"
            (IMAGES_DIR / filename).write_bytes(image_bytes)
            logger.info("Saved image → %s", filename)
        except Exception as exc:
            logger.error("Image generation failed; continuing stream: %s", exc)
            error = str(exc)

    return {
        "source": sample.source,
        "eeg": eeg.to_dict(),
        "analysis": analysis.to_dict(),
        "stage": analysis.stage,
        "mood": analysis.mood,
        "intensity": analysis.intensity,
        "prompt": prompt_data["prompt"],
        "negative_prompt": prompt_data["negative_prompt"],
        "selected_prompt_id": prompt_data["selected_prompt_id"],
        "world_name": prompt_data["world_name"],
        "phase": session.current_phase,
        "frame": session.frame,
        "image": image_b64,
        "error": error,
    }


@app.get("/", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "dream-generator"}


@app.get("/session/sample", tags=["session"])
async def sample_session():
    """Single EEG + analysis + prompt cycle without image generation."""
    session = DreamSession()
    return await _run_dream_cycle(session, sample_data_source, include_image=False)


@app.post("/session/reset-data", tags=["session"])
async def reset_session_data():
    """Reset CSV-backed sampling to the first CSV row."""
    sample_data_source.reset_csv()
    return {
        "status": "ok",
        "message": "CSV data position reset.",
    }


@app.websocket("/ws/dream")
async def dream_websocket(websocket: WebSocket):
    """
    Real-time dream stream.

    Client can send:
      {"action": "pause"}  → suspend image generation
      {"action": "resume"} → resume image generation

    Each frame payload includes:
      eeg, stage, mood, intensity, prompt, phase, frame, image (base64)
    """
    await websocket.accept()
    logger.info("WebSocket client connected: %s", websocket.client)

    session = DreamSession()
    data_source = EEGDataSource()
    stop_event = asyncio.Event()
    pause_event = asyncio.Event()
    pause_event.set()           # not paused at start
    pause_requested = asyncio.Event()  # fires when client sends "pause"

    async def _message_listener() -> None:
        """Background task: listen for pause/resume control messages."""
        try:
            while not stop_event.is_set():
                text = await websocket.receive_text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue
                action = data.get("action", "")
                if action == "pause":
                    pause_event.clear()
                    pause_requested.set()   # interrupt any in-flight cycle
                    logger.info("Dream stream paused by client.")
                elif action == "resume":
                    pause_requested.clear()
                    pause_event.set()
                    logger.info("Dream stream resumed by client.")
        except WebSocketDisconnect:
            stop_event.set()
        except Exception:
            stop_event.set()

    listener_task = asyncio.create_task(_message_listener())

    try:
        while not stop_event.is_set():
            # Block while paused
            while not pause_event.is_set() and not stop_event.is_set():
                await asyncio.sleep(0.2)

            if stop_event.is_set():
                break

            # Clear pause_requested so the new cycle isn't cancelled immediately
            pause_requested.clear()

            interval = random.uniform(settings.WS_INTERVAL_MIN, settings.WS_INTERVAL_MAX)

            cycle_task: asyncio.Task = asyncio.create_task(
                _run_dream_cycle(session, data_source)
            )
            stop_task: asyncio.Task = asyncio.create_task(stop_event.wait())
            pause_task: asyncio.Task = asyncio.create_task(pause_requested.wait())

            done, _ = await asyncio.wait(
                {cycle_task, stop_task, pause_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the helper sentinel tasks
            for t in (stop_task, pause_task):
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await t

            if stop_event.is_set():
                cycle_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await cycle_task
                break

            # Pause arrived mid-cycle → cancel cycle, loop back to pause-wait
            if cycle_task not in done:
                cycle_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await cycle_task
                continue

            try:
                payload = cycle_task.result()
            except Exception as exc:
                logger.exception("Unexpected error in dream cycle: %s", exc)
                await asyncio.sleep(interval)
                continue

            try:
                await websocket.send_text(json.dumps(payload))
                logger.info(
                    "Sent frame %d — stage=%s mood=%s phase=%s seed=%d",
                    payload["frame"],
                    payload["stage"],
                    payload["mood"],
                    payload["phase"],
                    session.base_seed,
                )
            except Exception:
                break

            await asyncio.sleep(interval)

    except Exception as exc:
        logger.exception("Fatal WebSocket error: %s", exc)
    finally:
        stop_event.set()
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener_task
        logger.info("WebSocket disconnected: %s", websocket.client)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
