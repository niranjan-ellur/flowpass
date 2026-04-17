"""Tests for the Weather API adapter.

Never hits the real API. Uses httpx MockTransport to return canned
responses so tests are fast and hermetic.
"""

from __future__ import annotations

import httpx
import pytest

from app.services import weather as weather_module


def _transport_returning(payload: dict, status: int = 200) -> httpx.MockTransport:
    """Build a mock transport that returns a fixed JSON payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


def _transport_raising() -> httpx.MockTransport:
    """Build a mock transport that simulates a network error."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("simulated timeout")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_returns_none_when_no_api_key() -> None:
    result = await weather_module.fetch_current_conditions(12.0, 77.0, api_key="")
    assert result is None


@pytest.mark.asyncio
async def test_parses_sunny_conditions() -> None:
    payload = {
        "temperature": {"degrees": 28.5},
        "relativeHumidity": 60,
        "weatherCondition": {
            "type": "CLEAR",
            "description": {"text": "Clear sky"},
        },
        "precipitation": {"probability": {"percent": 10}},
    }
    transport = _transport_returning(payload)
    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await weather_module.fetch_current_conditions(
            12.0, 77.0, api_key="fake-key", client=client
        )

    assert snapshot is not None
    assert snapshot.temperature_c == 28.5
    assert snapshot.is_raining is False
    assert snapshot.rain_expected_within_hour is False
    assert snapshot.humidity_percent == 60


@pytest.mark.asyncio
async def test_parses_rainy_conditions() -> None:
    payload = {
        "temperature": {"degrees": 22.0},
        "relativeHumidity": 85,
        "weatherCondition": {
            "type": "RAIN_HEAVY",
            "description": {"text": "Heavy rain"},
        },
        "precipitation": {"probability": {"percent": 95}},
    }
    transport = _transport_returning(payload)
    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await weather_module.fetch_current_conditions(
            12.0, 77.0, api_key="fake-key", client=client
        )

    assert snapshot is not None
    assert snapshot.is_raining is True
    assert snapshot.rain_expected_within_hour is True


@pytest.mark.asyncio
async def test_detects_impending_rain_from_probability() -> None:
    payload = {
        "temperature": {"degrees": 25.0},
        "relativeHumidity": 70,
        "weatherCondition": {
            "type": "PARTLY_CLOUDY",
            "description": {"text": "Partly cloudy"},
        },
        "precipitation": {"probability": {"percent": 65}},
    }
    transport = _transport_returning(payload)
    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await weather_module.fetch_current_conditions(
            12.0, 77.0, api_key="fake-key", client=client
        )

    assert snapshot is not None
    assert snapshot.is_raining is False
    assert snapshot.rain_expected_within_hour is True


@pytest.mark.asyncio
async def test_returns_none_on_network_error() -> None:
    transport = _transport_raising()
    async with httpx.AsyncClient(transport=transport) as client:
        result = await weather_module.fetch_current_conditions(
            12.0, 77.0, api_key="fake-key", client=client
        )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_on_http_error() -> None:
    transport = _transport_returning({"error": "bad request"}, status=400)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await weather_module.fetch_current_conditions(
            12.0, 77.0, api_key="fake-key", client=client
        )
    assert result is None
