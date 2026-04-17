"""Enumerations for FlowPass domain values.

Using StrEnum (Python 3.11+) so values serialize cleanly to JSON and
render naturally in templates without calling .value everywhere.
"""

from enum import StrEnum


class TransitMode(StrEnum):
    """How the attendee is traveling to and from the venue."""

    METRO = "metro"
    CAR = "car"
    RIDESHARE = "rideshare"
    WALKING = "walking"


class MatchPhase(StrEnum):
    """Phases of a cricket match that affect flow recommendations.

    Only phases the engine branches on are modeled. "in_play" covers
    the long middle of the match where the app stays quiet.
    """

    PRE_MATCH = "pre_match"
    IN_PLAY = "in_play"
    INNINGS_BREAK = "innings_break"
    FINAL_OVERS = "final_overs"
    TROPHY_CEREMONY = "trophy_ceremony"
    POST_MATCH = "post_match"


class CongestionLevel(StrEnum):
    """Human-friendly congestion buckets used in recommendations."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class AppMode(StrEnum):
    """Which of the two FlowPass screens is active.

    Entry mode runs before and during early match phases; Exit mode
    auto-activates on final_overs and stays through post_match.
    """

    ENTRY = "entry"
    QUIET = "quiet"
    EXIT = "exit"
