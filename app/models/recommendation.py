"""Models for runtime engine inputs and outputs.

Recommendation is what the engine returns — one per call, ready to render.
MatchState is the snapshot of where the match is when the user polls.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AppMode, CongestionLevel, MatchPhase, TransitMode


class MatchState(BaseModel):
    """Current match clock and phase.

    For the demo, a scrubber in the UI sets these values directly. In a real
    deployment they'd be fed by a sports data provider.
    """

    model_config = ConfigDict(extra="forbid")

    phase: MatchPhase
    minutes_into_match: int = Field(ge=0, le=600)
    minutes_until_end_estimate: int = Field(
        ge=0, le=600, description="Best guess of time left including expected ceremony"
    )


class UserPreferences(BaseModel):
    """What the user has picked on the onboarding step."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(pattern=r"^[A-Z]\d+$")
    transit_mode: TransitMode
    step_free: bool = Field(
        default=False,
        description="Avoid stairs: wheelchair user, stroller, injury, etc.",
    )
    arrive_buffer_minutes: int = Field(
        default=0, ge=0, le=60, description="Extra slack the user wants before gates"
    )


class RouteStep(BaseModel):
    """One step in the rendered recommendation route."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    detail: str = Field(min_length=1, max_length=200)
    walk_seconds: int = Field(ge=0, le=3600)


class Recommendation(BaseModel):
    """The single hero card plus three-step route the UI renders."""

    model_config = ConfigDict(extra="forbid")

    mode: AppMode
    headline: str = Field(min_length=1, max_length=80)
    subtext: str = Field(min_length=1, max_length=200)
    target_time_iso: str | None = Field(
        default=None, description="When to leave (exit) or arrive (entry), ISO format"
    )
    gate_id: str = Field(pattern=r"^G\d+$")
    gate_name: str
    steps: list[RouteStep] = Field(min_length=1, max_length=5)
    congestion: CongestionLevel
    reason_code: str = Field(
        min_length=1, max_length=64, description="Machine ID for the reason, e.g. 'exit_pre_peak'"
    )
