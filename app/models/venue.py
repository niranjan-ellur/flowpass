"""Pydantic models describing the static venue graph.

These are loaded once at startup from venue.json and never mutated.
Every ID referenced elsewhere in the app (gate_id, section_id) must
validate against this graph.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RouteSegment(BaseModel):
    """One walkable step in a multi-step route.

    A segment is deliberately simple: a human-readable instruction plus
    metadata the engine uses to route around stairs, uncovered areas,
    and known congestion pinch points.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_id: str = Field(min_length=1, max_length=32)
    to_id: str = Field(min_length=1, max_length=32)
    instruction: str = Field(min_length=1, max_length=200)
    distance_m: int = Field(ge=0, le=2000)
    has_stairs: bool = False
    is_covered: bool = True
    wheelchair_accessible: bool = True
    base_walk_seconds: int = Field(ge=0, le=3600)


class Gate(BaseModel):
    """An ingress/egress point on the venue perimeter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^G\d+$", description="e.g. G1, G2, G10")
    name: str = Field(min_length=1, max_length=64)
    bearing_deg: int = Field(ge=0, le=359, description="Compass bearing from venue center")
    is_wheelchair_accessible: bool = True
    is_covered_entry: bool = False
    nearest_transit_id: str | None = None
    capacity_per_minute: int = Field(
        ge=1, le=10000, description="Realistic throughput when flowing normally"
    )


class Section(BaseModel):
    """A seating section the user can pick."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[A-Z]\d+$", description="e.g. P3, G7")
    name: str = Field(min_length=1, max_length=64)
    tier: int = Field(ge=1, le=5, description="1=lower bowl, higher=upper tiers")
    preferred_gate_ids: list[str] = Field(min_length=1, max_length=4)
    step_free_gate_ids: list[str] = Field(
        default_factory=list,
        description="Subset of preferred gates reachable without stairs",
    )

    @field_validator("preferred_gate_ids", "step_free_gate_ids")
    @classmethod
    def _validate_gate_id_shape(cls, v: list[str]) -> list[str]:
        for gate_id in v:
            if not gate_id.startswith("G") or not gate_id[1:].isdigit():
                raise ValueError(f"invalid gate id '{gate_id}' (expected Gn)")
        return v


class TransitStop(BaseModel):
    """A metro station, bus stop, or drop-off point near the venue."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    mode: str = Field(pattern=r"^(metro|bus|rideshare_zone|parking)$")
    walk_seconds_to_gate: dict[str, int] = Field(
        description="Map of gate_id -> walk seconds from this stop"
    )


class Venue(BaseModel):
    """The full static venue graph loaded from venue.json."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=32)
    name: str
    city: str
    capacity: int = Field(ge=100, le=200_000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    sections: list[Section] = Field(min_length=1)
    gates: list[Gate] = Field(min_length=1)
    transit_stops: list[TransitStop] = Field(default_factory=list)
    route_segments: list[RouteSegment] = Field(default_factory=list)
    generated_at: str | None = Field(
        default=None, description="ISO timestamp set by the Gemini generator"
    )
    source_prompt_hash: str | None = Field(
        default=None, description="Hash of the prompt used to generate this data"
    )

    def section_by_id(self, section_id: str) -> Section:
        """Return the section with the given id, or raise KeyError."""
        for section in self.sections:
            if section.id == section_id:
                return section
        raise KeyError(f"unknown section id: {section_id}")

    def gate_by_id(self, gate_id: str) -> Gate:
        """Return the gate with the given id, or raise KeyError."""
        for gate in self.gates:
            if gate.id == gate_id:
                return gate
        raise KeyError(f"unknown gate id: {gate_id}")
