"""Recommendation engine.

Pure functions that take the domain state, user preferences, optional
weather, and reason templates, and return a single Recommendation.
No I/O, no framework, no global state.

Design principle: every branch that changes the output has a unique
reason_code. That makes recommendations greppable in logs and testable
by asserting on reason_code rather than prose.
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
from app.services.weather import WeatherSnapshot

ReasonTemplates = dict[str, dict[str, str]]


# Fallback strings used when the Gemini-generated templates are unavailable.
_FALLBACK_REASONS: ReasonTemplates = {
    "entry_standard": {
        "headline": "Arrive via {gate_name}",
        "subtext": "Clear path right now. No crowd yet.",
    },
    "entry_beat_crush": {
        "headline": "Arrive via {gate_name} — ingress crush building",
        "subtext": "Go now. Queues at this gate are shortest on this approach.",
    },
    "entry_step_free": {
        "headline": "Arrive via {gate_name}",
        "subtext": "Step-free route. Covered where possible.",
    },
    "entry_weather_covered": {
        "headline": "Rain ahead — arrive via {gate_name}",
        "subtext": "Covered entry. Stay dry on your way in.",
    },
    "exit_standard": {
        "headline": "Leave in 15 min via {gate_name}",
        "subtext": "Plan your path. You have time.",
    },
    "exit_pre_peak": {
        "headline": "Leave now via {gate_name}",
        "subtext": "Exit flood imminent. This gate clears first.",
    },
    "exit_after_ceremony": {
        "headline": "Leave in 8 min via {gate_name}",
        "subtext": "Ceremony wrapping. Metro peak hits right after.",
    },
    "exit_weather_urgent": {
        "headline": "Rain starting — leave now via {gate_name}",
        "subtext": "Covered route. Beat the downpour to the metro.",
    },
}


def _render_reason(
    templates: ReasonTemplates,
    reason_code: str,
    gate_name: str,
) -> tuple[str, str]:
    """Return (headline, subtext) for a reason code, substituting {gate_name}.

    Uses Gemini-generated templates when present, falls back to hardcoded
    strings when not. Either way, the user always gets a valid message.
    """
    template = templates.get(reason_code) or _FALLBACK_REASONS.get(reason_code)
    if template is None:
        return (f"Arrive via {gate_name}", "Clear path.")
    headline = template["headline"].replace("{gate_name}", gate_name)
    subtext = template["subtext"].replace("{gate_name}", gate_name)
    return headline, subtext


def _pick_gate(
    venue: Venue,
    section: Section,
    prefer_step_free: bool,
    prefer_covered: bool,
) -> Gate:
    """Pick the best gate given accessibility and weather needs.

    Priority order:
    1. Step-free if requested (accessibility overrides weather)
    2. Covered gate among preferred if rain is expected
    3. First preferred gate
    """
    if prefer_step_free and section.step_free_gate_ids:
        return venue.gate_by_id(section.step_free_gate_ids[0])

    if prefer_step_free:
        for gate_id in section.preferred_gate_ids:
            gate = venue.gate_by_id(gate_id)
            if gate.is_wheelchair_accessible:
                return gate

    if prefer_covered:
        for gate_id in section.preferred_gate_ids:
            gate = venue.gate_by_id(gate_id)
            if gate.is_covered_entry:
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


def _choose_entry_reason(
    prefs: UserPreferences,
    weather: WeatherSnapshot | None,
    congestion_value: str,
) -> str:
    """Pick the reason code for an entry recommendation."""
    if prefs.step_free:
        return "entry_step_free"
    if weather is not None and weather.rain_expected_within_hour:
        return "entry_weather_covered"
    if congestion_value in {"high", "severe"}:
        return "entry_beat_crush"
    return "entry_standard"


def _choose_exit_reason(
    phase: MatchPhase,
    weather: WeatherSnapshot | None,
    congestion_value: str,
) -> str:
    """Pick the reason code for an exit recommendation."""
    if weather is not None and weather.is_raining:
        return "exit_weather_urgent"
    if phase == MatchPhase.TROPHY_CEREMONY:
        return "exit_after_ceremony"
    if congestion_value == "severe":
        return "exit_pre_peak"
    return "exit_standard"


def recommend_entry(
    venue: Venue,
    prefs: UserPreferences,
    match_state: MatchState,
    *,
    weather: WeatherSnapshot | None = None,
    reason_templates: ReasonTemplates | None = None,
) -> Recommendation:
    """Produce the Entry-mode recommendation."""
    section = venue.section_by_id(prefs.section_id)
    prefer_covered = weather is not None and weather.rain_expected_within_hour
    gate = _pick_gate(
        venue, section, prefer_step_free=prefs.step_free, prefer_covered=prefer_covered
    )
    congestion = expected_gate_congestion(
        match_state.phase,
        match_state.minutes_into_match,
        match_state.minutes_until_end_estimate,
    )
    reason_code = _choose_entry_reason(prefs, weather, congestion.value)
    headline, subtext = _render_reason(reason_templates or {}, reason_code, gate.name)

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


def recommend_exit(
    venue: Venue,
    prefs: UserPreferences,
    match_state: MatchState,
    *,
    weather: WeatherSnapshot | None = None,
    reason_templates: ReasonTemplates | None = None,
) -> Recommendation:
    """Produce the Exit-mode recommendation."""
    section = venue.section_by_id(prefs.section_id)
    prefer_covered = weather is not None and weather.is_raining
    gate = _pick_gate(
        venue, section, prefer_step_free=prefs.step_free, prefer_covered=prefer_covered
    )
    congestion = expected_gate_congestion(
        match_state.phase,
        match_state.minutes_into_match,
        match_state.minutes_until_end_estimate,
    )
    reason_code = _choose_exit_reason(match_state.phase, weather, congestion.value)
    headline, subtext = _render_reason(reason_templates or {}, reason_code, gate.name)

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


def recommend(
    venue: Venue,
    prefs: UserPreferences,
    match_state: MatchState,
    *,
    weather: WeatherSnapshot | None = None,
    reason_templates: ReasonTemplates | None = None,
) -> Recommendation:
    """Route to entry or exit recommender based on match phase.

    Single public entry point for the engine. Callers do not need to
    know about AppMode; the engine decides.
    """
    if should_activate_exit_mode(match_state.phase, match_state.minutes_until_end_estimate):
        return recommend_exit(
            venue, prefs, match_state, weather=weather, reason_templates=reason_templates
        )
    return recommend_entry(
        venue, prefs, match_state, weather=weather, reason_templates=reason_templates
    )
