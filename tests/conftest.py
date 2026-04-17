"""Pytest fixtures shared across engine and integration tests.

conftest.py is automatically discovered by pytest — no import needed.
Defining fixtures here means every test can ask for `venue` or `prefs`
by name and get a fresh instance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import (
    MatchPhase,
    MatchState,
    TransitMode,
    UserPreferences,
    Venue,
)

VENUE_JSON_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "venue.json"


@pytest.fixture(scope="session")
def venue() -> Venue:
    """Load the committed venue.json once per test session."""
    with VENUE_JSON_PATH.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return Venue.model_validate(raw)


@pytest.fixture
def prefs_metro_p1() -> UserPreferences:
    """Typical metro-commuting attendee in Pavilion North."""
    return UserPreferences(
        section_id="P1",
        transit_mode=TransitMode.METRO,
        step_free=False,
        arrive_buffer_minutes=0,
    )


@pytest.fixture
def prefs_step_free() -> UserPreferences:
    """Step-free attendee (wheelchair, stroller, or mobility need)."""
    return UserPreferences(
        section_id="P3",
        transit_mode=TransitMode.METRO,
        step_free=True,
        arrive_buffer_minutes=0,
    )


@pytest.fixture
def pre_match_state() -> MatchState:
    """30 minutes before first ball — peak ingress."""
    return MatchState(
        phase=MatchPhase.PRE_MATCH,
        minutes_into_match=0,
        minutes_until_end_estimate=210,
    )


@pytest.fixture
def mid_match_state() -> MatchState:
    """Deep into the match, nothing dramatic."""
    return MatchState(
        phase=MatchPhase.IN_PLAY,
        minutes_into_match=90,
        minutes_until_end_estimate=120,
    )


@pytest.fixture
def final_overs_state() -> MatchState:
    """Final overs, tight match ending."""
    return MatchState(
        phase=MatchPhase.FINAL_OVERS,
        minutes_into_match=195,
        minutes_until_end_estimate=8,
    )


@pytest.fixture
def trophy_ceremony_state() -> MatchState:
    """Trophy ceremony underway — exit window."""
    return MatchState(
        phase=MatchPhase.TROPHY_CEREMONY,
        minutes_into_match=215,
        minutes_until_end_estimate=10,
    )
