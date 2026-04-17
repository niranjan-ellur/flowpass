"""Unit tests for the FlowPass rules engine.

Fast, pure, many. These are the tests that will catch 90% of bugs
introduced in later slices. Keep them readable over clever.
"""

from __future__ import annotations

import pytest

from app.engine import (
    expected_gate_congestion,
    recommend,
    recommend_entry,
    recommend_exit,
    should_activate_exit_mode,
)
from app.models import (
    AppMode,
    CongestionLevel,
    MatchPhase,
    MatchState,
    TransitMode,
    UserPreferences,
    Venue,
)

# ---------------------------------------------------------------------------
# Congestion rules
# ---------------------------------------------------------------------------


class TestCongestion:
    """Behavior of expected_gate_congestion across match phases."""

    def test_trophy_ceremony_is_severe(self) -> None:
        assert (
            expected_gate_congestion(MatchPhase.TROPHY_CEREMONY, 215, 5) == CongestionLevel.SEVERE
        )

    def test_post_match_is_severe(self) -> None:
        assert expected_gate_congestion(MatchPhase.POST_MATCH, 220, 0) == CongestionLevel.SEVERE

    def test_final_overs_close_to_end_is_severe(self) -> None:
        assert expected_gate_congestion(MatchPhase.FINAL_OVERS, 200, 5) == CongestionLevel.SEVERE

    def test_final_overs_with_time_left_is_high(self) -> None:
        assert expected_gate_congestion(MatchPhase.FINAL_OVERS, 180, 20) == CongestionLevel.HIGH

    def test_pre_match_is_high(self) -> None:
        assert expected_gate_congestion(MatchPhase.PRE_MATCH, 0, 210) == CongestionLevel.HIGH

    def test_innings_break_is_moderate(self) -> None:
        assert (
            expected_gate_congestion(MatchPhase.INNINGS_BREAK, 100, 100) == CongestionLevel.MODERATE
        )

    def test_mid_match_in_play_is_low(self) -> None:
        assert expected_gate_congestion(MatchPhase.IN_PLAY, 80, 120) == CongestionLevel.LOW


# ---------------------------------------------------------------------------
# Exit-mode activation
# ---------------------------------------------------------------------------


class TestExitModeActivation:
    """When does the UI flip from quiet to exit mode?"""

    def test_final_overs_activates(self) -> None:
        assert should_activate_exit_mode(MatchPhase.FINAL_OVERS, 30) is True

    def test_trophy_ceremony_activates(self) -> None:
        assert should_activate_exit_mode(MatchPhase.TROPHY_CEREMONY, 10) is True

    def test_in_play_with_little_time_activates(self) -> None:
        assert should_activate_exit_mode(MatchPhase.IN_PLAY, 20) is True

    def test_in_play_mid_match_stays_quiet(self) -> None:
        assert should_activate_exit_mode(MatchPhase.IN_PLAY, 120) is False

    def test_pre_match_never_activates_exit(self) -> None:
        assert should_activate_exit_mode(MatchPhase.PRE_MATCH, 10) is False


# ---------------------------------------------------------------------------
# Entry recommendation
# ---------------------------------------------------------------------------


class TestRecommendEntry:
    """Entry-mode recommendations for the pre-match and early phases."""

    def test_returns_entry_mode(self, venue: Venue, prefs_metro_p1: UserPreferences) -> None:
        state = MatchState(
            phase=MatchPhase.PRE_MATCH, minutes_into_match=0, minutes_until_end_estimate=210
        )
        rec = recommend_entry(venue, prefs_metro_p1, state)
        assert rec.mode == AppMode.ENTRY

    def test_picks_preferred_gate_for_section(
        self, venue: Venue, prefs_metro_p1: UserPreferences, pre_match_state: MatchState
    ) -> None:
        rec = recommend_entry(venue, prefs_metro_p1, pre_match_state)
        # P1's preferred gates start with G1
        assert rec.gate_id == "G1"

    def test_step_free_user_gets_step_free_gate(
        self, venue: Venue, prefs_step_free: UserPreferences, pre_match_state: MatchState
    ) -> None:
        rec = recommend_entry(venue, prefs_step_free, pre_match_state)
        # P3's only step-free gate is G5
        assert rec.gate_id == "G5"
        assert rec.reason_code == "entry_step_free"

    def test_three_steps_in_route(
        self, venue: Venue, prefs_metro_p1: UserPreferences, pre_match_state: MatchState
    ) -> None:
        rec = recommend_entry(venue, prefs_metro_p1, pre_match_state)
        assert len(rec.steps) == 3

    def test_pre_match_reason_is_crush(
        self, venue: Venue, prefs_metro_p1: UserPreferences, pre_match_state: MatchState
    ) -> None:
        rec = recommend_entry(venue, prefs_metro_p1, pre_match_state)
        assert rec.reason_code in {"entry_beat_crush", "entry_step_free"}


# ---------------------------------------------------------------------------
# Exit recommendation
# ---------------------------------------------------------------------------


class TestRecommendExit:
    """Exit-mode recommendations for the final phases."""

    def test_returns_exit_mode(
        self, venue: Venue, prefs_metro_p1: UserPreferences, final_overs_state: MatchState
    ) -> None:
        rec = recommend_exit(venue, prefs_metro_p1, final_overs_state)
        assert rec.mode == AppMode.EXIT

    def test_trophy_ceremony_produces_after_ceremony_reason(
        self,
        venue: Venue,
        prefs_metro_p1: UserPreferences,
        trophy_ceremony_state: MatchState,
    ) -> None:
        rec = recommend_exit(venue, prefs_metro_p1, trophy_ceremony_state)
        assert rec.reason_code == "exit_after_ceremony"

    def test_final_overs_with_low_time_is_pre_peak(
        self, venue: Venue, prefs_metro_p1: UserPreferences, final_overs_state: MatchState
    ) -> None:
        rec = recommend_exit(venue, prefs_metro_p1, final_overs_state)
        assert rec.reason_code == "exit_pre_peak"
        assert rec.congestion == CongestionLevel.SEVERE


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class TestRecommendDispatch:
    """recommend() picks entry or exit based on match phase + time left."""

    def test_pre_match_dispatches_to_entry(
        self, venue: Venue, prefs_metro_p1: UserPreferences, pre_match_state: MatchState
    ) -> None:
        assert recommend(venue, prefs_metro_p1, pre_match_state).mode == AppMode.ENTRY

    def test_mid_match_dispatches_to_entry(
        self, venue: Venue, prefs_metro_p1: UserPreferences, mid_match_state: MatchState
    ) -> None:
        # Quiet during mid-match — engine still falls through to entry
        # for now; a later slice will add a proper quiet mode.
        assert recommend(venue, prefs_metro_p1, mid_match_state).mode == AppMode.ENTRY

    def test_final_overs_dispatches_to_exit(
        self, venue: Venue, prefs_metro_p1: UserPreferences, final_overs_state: MatchState
    ) -> None:
        assert recommend(venue, prefs_metro_p1, final_overs_state).mode == AppMode.EXIT

    def test_trophy_ceremony_dispatches_to_exit(
        self,
        venue: Venue,
        prefs_metro_p1: UserPreferences,
        trophy_ceremony_state: MatchState,
    ) -> None:
        assert recommend(venue, prefs_metro_p1, trophy_ceremony_state).mode == AppMode.EXIT


# ---------------------------------------------------------------------------
# Invariants (lightweight property tests)
# ---------------------------------------------------------------------------


class TestEngineInvariants:
    """Properties that must hold for every recommendation, always."""

    @pytest.mark.parametrize("section_id", ["P1", "P2", "P3", "P4", "G7", "G8", "G9", "C1"])
    def test_recommended_gate_belongs_to_section(self, venue: Venue, section_id: str) -> None:
        prefs = UserPreferences(section_id=section_id, transit_mode=TransitMode.METRO)
        state = MatchState(
            phase=MatchPhase.IN_PLAY, minutes_into_match=60, minutes_until_end_estimate=150
        )
        rec = recommend(venue, prefs, state)
        section = venue.section_by_id(section_id)
        assert rec.gate_id in section.preferred_gate_ids

    @pytest.mark.parametrize(
        "phase",
        [
            MatchPhase.PRE_MATCH,
            MatchPhase.IN_PLAY,
            MatchPhase.INNINGS_BREAK,
            MatchPhase.FINAL_OVERS,
            MatchPhase.TROPHY_CEREMONY,
            MatchPhase.POST_MATCH,
        ],
    )
    def test_recommendation_has_nonempty_fields_for_every_phase(
        self, venue: Venue, prefs_metro_p1: UserPreferences, phase: MatchPhase
    ) -> None:
        state = MatchState(phase=phase, minutes_into_match=60, minutes_until_end_estimate=60)
        rec = recommend(venue, prefs_metro_p1, state)
        assert rec.headline
        assert rec.subtext
        assert rec.gate_id
        assert rec.gate_name
        assert len(rec.steps) >= 1

    def test_step_free_user_never_gets_inaccessible_gate(
        self, venue: Venue, prefs_step_free: UserPreferences, pre_match_state: MatchState
    ) -> None:
        rec = recommend(venue, prefs_step_free, pre_match_state)
        gate = venue.gate_by_id(rec.gate_id)
        assert gate.is_wheelchair_accessible is True


# ---------------------------------------------------------------------------
# Model validation edge cases
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Pydantic should reject bogus inputs at the model layer."""

    def test_unknown_section_raises(self, venue: Venue, prefs_metro_p1: UserPreferences) -> None:
        state = MatchState(
            phase=MatchPhase.IN_PLAY, minutes_into_match=10, minutes_until_end_estimate=180
        )
        bad = prefs_metro_p1.model_copy(update={"section_id": "Z9"})
        with pytest.raises(KeyError):
            recommend(venue, bad, state)

    def test_malformed_section_id_rejected_by_pydantic(self) -> None:
        with pytest.raises(ValueError):
            UserPreferences(section_id="bad-id", transit_mode=TransitMode.METRO)

    def test_negative_minutes_rejected(self) -> None:
        with pytest.raises(ValueError):
            MatchState(
                phase=MatchPhase.IN_PLAY,
                minutes_into_match=-1,
                minutes_until_end_estimate=100,
            )
