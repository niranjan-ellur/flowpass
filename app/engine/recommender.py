"""Recommendation engine.

Pure functions that take the domain state and user preferences and return
a single Recommendation. No I/O, no framework, no global state. This is
the module that must stay fast, predictable, and heavily tested.

The design principle: every branch that changes the output has a unique
reason_code. This makes recommendations greppable in logs and testable by
asserting on reason_code rather than prose.
"""

from __future__ import annotations

from app.engine.congestion import (
    expected_gate_congestion,
    should_activate_exit_mode,
)
from app.models.enums import AppMode, MatchPhase, TransitMode
from app.models.recommendation import (
    MatchState,
    Recommendation,
    RouteStep,
    UserPreferences,
)
from app.models.venue import Gate, Section, Venue


def _pick_gate(venue: Venue, section: Section, prefer_step_free: bool) -> Gate:
    """Pick the best gate for this section given accessibility needs.

    Step-free users get a step-free gate if one is listed; otherwise we
    fall back to the first preferred gate that is wheelchair-accessible.
    Regular users get the section's first preferred gate.
    """
    if prefer_step_free and section.step_free_gate_ids:
        return venue.gate_by_id(section.step_free_gate_ids[0])

    if prefer_step_free:
        # Section has no declared step-free gates; fall back to any
        # preferred gate marked wheelchair-accessible at the gate level.
        for gate_id in section.preferred_gate_ids:
            gate = venue.gate_by_id(gate_id)
            if gate.is_wheelchair_accessible:
                return gate

    return venue.gate_by_id(section.preferred_gate_ids[0])


def _transit_label(mode: TransitMode) -> str:
    """Human label for the starting point of the inbound route."""
    labels = {
        TransitMode.METRO: "From your metro exit",
        TransitMode.CAR: "From parking",
        TransitMode.RIDESHARE: "From the rideshare drop-off",
        TransitMode.WALKING: "From your approach path",
    }
    return labels[mode]


def _entry_steps(gate: Gate, section: Section, prefs: UserPreferences) -> list[RouteStep]:
    """Three-step inbound route: transit -> gate -> section."""
    return [
        RouteStep(
            label=_transit_label(prefs.transit_mode),
            detail=f"Walk toward {gate.name}. Covered path if available.",
            walk_seconds=300,
        ),
        RouteStep(
            label=f"Enter via {gate.name}",
            detail="Have your ticket QR ready. Security scan, then proceed.",
            walk_seconds=120,
        ),
        RouteStep(
            label=f"To your seat in {section.name}",
            detail="Concourse signage will guide you to the section entrance.",
            walk_seconds=180,
        ),
    ]


def _exit_steps(gate: Gate, section: Section, prefs: UserPreferences) -> list[RouteStep]:
    """Three-step outbound route: section -> gate -> transit."""
    return [
        RouteStep(
            label=f"Leave {section.name}",
            detail="Head down the concourse toward the marked exit ramp.",
            walk_seconds=180,
        ),
        RouteStep(
            label=f"Exit via {gate.name}",
            detail="Stay right to keep the flow moving. Staff will direct you.",
            walk_seconds=90,
        ),
        RouteStep(
            label=_transit_label(prefs.transit_mode).replace("From", "To"),
            detail="Follow the illuminated path to your transit point.",
            walk_seconds=360,
        ),
    ]


def recommend_entry(
    venue: Venue, prefs: UserPreferences, match_state: MatchState
) -> Recommendation:
    """Produce the Entry-mode recommendation.

    Called before and during early match phases. Focus: get the user
    through security and into their seat without missing the first ball.
    """
    section = venue.section_by_id(prefs.section_id)
    gate = _pick_gate(venue, section, prefer_step_free=prefs.step_free)
    congestion = expected_gate_congestion(
        match_state.phase,
        match_state.minutes_into_match,
        match_state.minutes_until_end_estimate,
    )

    if prefs.step_free:
        reason_code = "entry_step_free"
        headline = f"Arrive via {gate.name}"
        subtext = "Step-free route. Covered where possible."
    elif congestion.value in {"high", "severe"}:
        reason_code = "entry_beat_crush"
        headline = f"Arrive via {gate.name} — ingress crush building"
        subtext = "Go now. Queues at this gate are shortest on this approach."
    else:
        reason_code = "entry_standard"
        headline = f"Arrive via {gate.name}"
        subtext = "Clear path right now. No crowd yet."

    return Recommendation(
        mode=AppMode.ENTRY,
        headline=headline,
        subtext=subtext,
        target_time_iso=None,
        gate_id=gate.id,
        gate_name=gate.name,
        steps=_entry_steps(gate, section, prefs),
        congestion=congestion,
        reason_code=reason_code,
    )


def recommend_exit(venue: Venue, prefs: UserPreferences, match_state: MatchState) -> Recommendation:
    """Produce the Exit-mode recommendation.

    Called in the final phases. Focus: leave at the right moment so the
    user misses the transit platform peak without missing the trophy.
    """
    section = venue.section_by_id(prefs.section_id)
    gate = _pick_gate(venue, section, prefer_step_free=prefs.step_free)
    congestion = expected_gate_congestion(
        match_state.phase,
        match_state.minutes_into_match,
        match_state.minutes_until_end_estimate,
    )

    if match_state.phase == MatchPhase.TROPHY_CEREMONY:
        reason_code = "exit_after_ceremony"
        headline = f"Leave in 8 min via {gate.name}"
        subtext = "Ceremony wrapping. Metro peak hits right after."
    elif congestion.value == "severe":
        reason_code = "exit_pre_peak"
        headline = f"Leave now via {gate.name}"
        subtext = "Exit flood imminent. This gate clears first."
    else:
        reason_code = "exit_standard"
        headline = f"Leave in 15 min via {gate.name}"
        subtext = "Plan your path. You have time."

    return Recommendation(
        mode=AppMode.EXIT,
        headline=headline,
        subtext=subtext,
        target_time_iso=None,
        gate_id=gate.id,
        gate_name=gate.name,
        steps=_exit_steps(gate, section, prefs),
        congestion=congestion,
        reason_code=reason_code,
    )


def recommend(venue: Venue, prefs: UserPreferences, match_state: MatchState) -> Recommendation:
    """Route to entry or exit recommender based on match phase.

    This is the single public entry point for the engine. Callers don't
    need to know about AppMode; the engine decides.
    """
    if should_activate_exit_mode(match_state.phase, match_state.minutes_until_end_estimate):
        return recommend_exit(venue, prefs, match_state)
    return recommend_entry(venue, prefs, match_state)
