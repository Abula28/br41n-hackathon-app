"""
Image Generator
---------------
Calls Cloudflare Workers AI (Stable Diffusion XL) to generate an image from
a text prompt and returns raw PNG bytes.

Retry strategy
--------------
On transient HTTP failures (5xx, network timeouts) the generator waits
`IMAGE_GEN_RETRY_DELAY` seconds and retries up to `IMAGE_GEN_MAX_RETRIES`
times.  On permanent failures (4xx, credential errors) it raises immediately.

The caller is responsible for converting bytes to base64 for transport.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

# Cloudflare returns raw image bytes (PNG) directly — not JSON
_HEADERS = {
    "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json",
}

# Timeout for a single image-generation request (SD-XL can be slow)
_REQUEST_TIMEOUT = 60.0  # seconds


async def generate_image(
    prompt: str,
    negative_prompt: str = "",
    seed: int | None = None,
) -> bytes:
    """
    Request an image from Cloudflare Workers AI.

    Parameters
    ----------
    prompt          : positive prompt string
    negative_prompt : negative prompt string (optional)
    seed            : deterministic seed for visual consistency across frames

    Returns
    -------
    bytes
        Raw PNG image data.

    Raises
    ------
    RuntimeError
        If all retries are exhausted or a permanent error is encountered.
    """
    if not settings.CLOUDFLARE_ACCOUNT_ID or not settings.CLOUDFLARE_API_TOKEN:
        raise RuntimeError(
            "Cloudflare credentials not configured. "
            "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN."
        )

    payload: dict = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": 1024,
        "height": 1024,
        "num_steps": 20,
        "guidance": 7.5,
    }
    if seed is not None:
        payload["seed"] = seed
        logger.debug("Using seed %d for image generation.", seed)

    url = settings.cf_ai_url
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        for attempt in range(1, settings.IMAGE_GEN_MAX_RETRIES + 1):
            try:
                logger.info(
                    "Image generation attempt %d/%d — url=%s",
                    attempt,
                    settings.IMAGE_GEN_MAX_RETRIES,
                    url,
                )
                response = await client.post(url, json=payload, headers=_HEADERS)

                # Permanent auth / bad-request errors — do not retry
                if response.status_code in (400, 401, 403):
                    raise RuntimeError(
                        f"Cloudflare API permanent error {response.status_code}: "
                        f"{response.text}"
                    )

                # Transient server errors — retry
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()

                # Cloudflare returns raw image bytes
                image_bytes = response.content
                if len(image_bytes) < 100:
                    # Suspiciously small — probably an error JSON
                    raise RuntimeError(
                        f"Unexpectedly small response ({len(image_bytes)} bytes): "
                        f"{image_bytes[:200]}"
                    )

                logger.info(
                    "Image generated successfully (%d bytes) on attempt %d.",
                    len(image_bytes),
                    attempt,
                )
                return image_bytes

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                logger.warning(
                    "Image generation attempt %d failed: %s. Retrying in %.1fs…",
                    attempt,
                    exc,
                    settings.IMAGE_GEN_RETRY_DELAY,
                )
                if attempt < settings.IMAGE_GEN_MAX_RETRIES:
                    await asyncio.sleep(settings.IMAGE_GEN_RETRY_DELAY)

    raise RuntimeError(
        f"Image generation failed after {settings.IMAGE_GEN_MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )
