"""Thin adapter around google-genai for Gemini calls.

Kept small on purpose: one function for build-time JSON generation,
one for the runtime Ask feature. Everything returns plain Python objects;
callers never see SDK types.

Why we fall back to templates instead of raising: a user-facing stadium
app cannot show 500 errors during a match. If Gemini is rate-limited or
the network is flaky, we serve degraded-but-useful recommendations
instead of nothing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

# Build-time model: cheapest flash variant, plenty for structured JSON generation.
# Use latest alias so we pick up improvements without a code change.
_BUILD_MODEL = "gemini-flash-latest"


def _client() -> genai.Client:
    """Construct a Gemini client using the key from settings.

    Raises RuntimeError if the key isn't configured, so callers don't
    silently call an unauthenticated API.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env or export it before running.")
    return genai.Client(api_key=settings.gemini_api_key)


def generate_json(prompt: str, schema_hint: str) -> dict[str, Any]:
    """Call Gemini and parse the response as JSON.

    The prompt is responsible for being explicit about the JSON shape;
    schema_hint is appended to reinforce the expected structure. If the
    model returns anything unparseable, raises ValueError so the caller
    (a build-time script) fails loudly. Runtime paths should catch this
    and fall back to static templates instead.
    """
    client = _client()
    full_prompt = (
        f"{prompt}\n\n"
        f"Respond with valid JSON only. No prose, no markdown fences, no commentary. "
        f"Schema hint: {schema_hint}"
    )

    response = client.models.generate_content(
        model=_BUILD_MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            temperature=0.4,
            response_mime_type="application/json",
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise ValueError("Gemini returned an empty response")

    try:
        result: dict[str, Any] = json.loads(text)
        return result
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON payload: %r", text[:500])
        raise ValueError(f"Gemini response was not valid JSON: {exc}") from exc
