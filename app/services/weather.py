"""Google Maps Platform Weather API client.

Fetches current conditions and a short forecast for the venue
coordinates. The snapshot feeds into the engine so recommendations
react to imminent rain (prefer covered gates, more urgency to leave).

Kept small on purpose: one async fetch function, one Pydantic model for
the response. Failures degrade gracefully — if the API is down, the
engine falls back to weather-agnostic behavior.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

_WEATHER_API_BASE = "https://weather.googleapis.com/v1"
_REQUEST_TIMEOUT_SECONDS = 5.0


class WeatherSnapshot(BaseModel):
    """Minimal weather signal used by the recommendation engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature_c: float = Field(ge=-50, le=60)
    condition: str = Field(min_length=1, max_length=64)
    is_raining: bool
    rain_expected_within_hour: bool
    humidity_percent: int = Field(ge=0, le=100)


def _parse_current_conditions(payload: dict) -> WeatherSnapshot:  # type: ignore[type-arg]
    """Convert the Weather API response to our minimal snapshot.

    The Weather API schema is large. We pluck only what the engine needs.
    If a field is missing, default to a neutral value so the engine still
    gets a valid snapshot rather than a partial failure.
    """
    temp_c = float(payload.get("temperature", {}).get("degrees", 25.0))
    humidity = int(payload.get("relativeHumidity", 50))
    condition = str(payload.get("weatherCondition", {}).get("description", {}).get("text", "Clear"))
    condition_type = str(payload.get("weatherCondition", {}).get("type", ""))

    is_raining = "RAIN" in condition_type.upper() or "SHOWER" in condition_type.upper()
    precip_probability = int(
        payload.get("precipitation", {}).get("probability", {}).get("percent", 0)
    )
    rain_expected = is_raining or precip_probability >= 40

    return WeatherSnapshot(
        temperature_c=temp_c,
        condition=condition,
        is_raining=is_raining,
        rain_expected_within_hour=rain_expected,
        humidity_percent=humidity,
    )


async def fetch_current_conditions(
    latitude: float,
    longitude: float,
    api_key: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> WeatherSnapshot | None:
    """Fetch current weather for a coordinate.

    Returns None on any failure (network, auth, parse). The engine treats
    None as "no weather signal" and falls back to base rules.

    The `client` parameter lets tests inject a mock client.
    """
    if not api_key:
        logger.warning("Weather API key not configured; returning None")
        return None

    url = f"{_WEATHER_API_BASE}/currentConditions:lookup"
    params: dict[str, str | float] = {
        "key": api_key,
        "location.latitude": latitude,
        "location.longitude": longitude,
    }

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS)

    try:
        response = await http.get(url, params=params)
        response.raise_for_status()
        return _parse_current_conditions(response.json())
    except httpx.HTTPError as exc:
        logger.warning("Weather API request failed: %s", exc)
        return None
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Weather API response could not be parsed: %s", exc)
        return None
    finally:
        if owns_client:
            await http.aclose()
