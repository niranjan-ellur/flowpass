"""Tests for weather-aware recommendation behavior.

Separated from test_engine.py so the two concerns are visible at a glance.
"""

from __future__ import annotations

import pytest

from app.engine import recommend, recommend_entry, recommend_exit
from app.models import (
    CongestionLevel,
    MatchState,
    UserPreferences,
    Venue,
)
from app.services.weather import WeatherSnapshot


@pytest.fixture
def sunny() -> WeatherSnapshot:
    return WeatherSnapshot(
        temperature_c=28.0,
        condition="Clear sky",
        is_raining=False,
        rain_expected_within_hour=False,
        humidity_percent=55,
    )


@pytest.fixture
def rain_expected() -> WeatherSnapshot:
    return WeatherSnapshot(
        temperature_c=25.0,
        condition="Partly cloudy",
        is_raining=False,
        rain_expected_within_hour=True,
        humidity_percent=75,
    )


@pytest.fixture
def raining_now() -> WeatherSnapshot:
    return WeatherSnapshot(
        temperature_c=22.0,
        condition="Heavy rain",
        is_raining=True,
        rain_expected_within_hour=True,
        humidity_percent=92,
    )


class TestWeatherInfluencesEntry:
    """Expected rain should change gate selection and reason code."""

    def test_sunny_weather_keeps_default_gate(
        self,
        venue: Venue,
        prefs_metro_p1: UserPreferences,
        pre_match_state: MatchState,
        sunny: WeatherSnapshot,
    ) -> None:
        rec = recommend_entry(venue, prefs_metro_p1, pre_match_state, weather=sunny)
        assert rec.gate_id == "P1" or rec.gate_id.startswith("G")
        assert rec.reason_code != "entry_weather_covered"

    def test_expected_rain_triggers_covered_reason(
        self,
        venue: Venue,
        prefs_metro_p1: UserPreferences,
        pre_match_state: MatchState,
        rain_expected: WeatherSnapshot,
    ) -> None:
        rec = recommend_entry(venue, prefs_metro_p1, pre_match_state, weather=rain_expected)
        assert rec.reason_code == "entry_weather_covered"

    def test_expected_rain_picks_covered_gate(
        self,
        venue: Venue,
        prefs_metro_p1: UserPreferences,
        pre_match_state: MatchState,
        rain_expected: WeatherSnapshot,
    ) -> None:
        rec = recommend_entry(venue, prefs_metro_p1, pre_match_state, weather=rain_expected)
        gate = venue.gate_by_id(rec.gate_id)
        assert gate.is_covered_entry is True

    def test_step_free_overrides_weather(
        self,
        venue: Venue,
        prefs_step_free: UserPreferences,
        pre_match_state: MatchState,
        rain_expected: WeatherSnapshot,
    ) -> None:
        """Accessibility is not negotiable; weather cannot reroute a wheelchair user."""
        rec = recommend_entry(venue, prefs_step_free, pre_match_state, weather=rain_expected)
        assert rec.reason_code == "entry_step_free"


class TestWeatherInfluencesExit:
    """Rain happening now should escalate exit urgency."""

    def test_rain_now_triggers_urgent_weather_reason(
        self,
        venue: Venue,
        prefs_metro_p1: UserPreferences,
        final_overs_state: MatchState,
        raining_now: WeatherSnapshot,
    ) -> None:
        rec = recommend_exit(venue, prefs_metro_p1, final_overs_state, weather=raining_now)
        assert rec.reason_code == "exit_weather_urgent"

    def test_sunny_exit_uses_standard_reasons(
        self,
        venue: Venue,
        prefs_metro_p1: UserPreferences,
        final_overs_state: MatchState,
        sunny: WeatherSnapshot,
    ) -> None:
        rec = recommend_exit(venue, prefs_metro_p1, final_overs_state, weather=sunny)
        assert rec.reason_code in {"exit_pre_peak", "exit_standard"}


class TestReasonTemplatesUsed:
    """Engine should prefer provided templates over fallback strings."""

    def test_custom_template_rendered(
        self, venue: Venue, prefs_metro_p1: UserPreferences, pre_match_state: MatchState
    ) -> None:
        templates = {
            "entry_beat_crush": {
                "headline": "CUSTOM: head to {gate_name}",
                "subtext": "CUSTOM: queues forming.",
            }
        }
        rec = recommend(venue, prefs_metro_p1, pre_match_state, reason_templates=templates)
        if rec.reason_code == "entry_beat_crush":
            assert rec.headline.startswith("CUSTOM:")
            assert "Gate" in rec.headline  # {gate_name} substituted

    def test_empty_templates_falls_back_to_defaults(
        self, venue: Venue, prefs_metro_p1: UserPreferences, pre_match_state: MatchState
    ) -> None:
        rec = recommend(venue, prefs_metro_p1, pre_match_state, reason_templates={})
        assert rec.headline  # something rendered
        assert "{gate_name}" not in rec.headline  # placeholder substituted
        assert rec.congestion in set(CongestionLevel)
