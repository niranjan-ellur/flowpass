"""Congestion estimation from match phase and time.

The rule of thumb: crowds concentrate at phase transitions. The first
20 minutes after gates open are the ingress crush; the final 15 minutes
around the last ball and trophy ceremony are the egress flood. In
between, the stadium is calm.

This module is pure. No I/O. Given a MatchState, it returns a
CongestionLevel. Easy to test, easy to reason about.
"""

from app.models.enums import CongestionLevel, MatchPhase


def expected_gate_congestion(
    phase: MatchPhase,
    minutes_into_match: int,
    minutes_until_end: int,
) -> CongestionLevel:
    """Estimate crowd level at gates right now.

    Rules, in priority order:
    1. Trophy ceremony / final overs with <10 min left -> SEVERE (everyone will leave together)
    2. Post match within 20 min of end -> SEVERE
    3. Pre-match within 20 min of first ball -> HIGH (ingress crush)
    4. Innings break -> MODERATE (food/restroom spikes but gates are quiet)
    5. In play with lots of time left -> LOW
    """
    if phase in {MatchPhase.TROPHY_CEREMONY, MatchPhase.POST_MATCH}:
        return CongestionLevel.SEVERE

    if phase == MatchPhase.FINAL_OVERS and minutes_until_end <= 10:
        return CongestionLevel.SEVERE

    if phase == MatchPhase.FINAL_OVERS:
        return CongestionLevel.HIGH

    if phase == MatchPhase.PRE_MATCH and minutes_into_match >= -20:
        # minutes_into_match is 0 at first ball; -20 means 20 min before.
        # We don't model negatives in MatchState, so pre-match always counts as HIGH here.
        return CongestionLevel.HIGH

    if phase == MatchPhase.PRE_MATCH:
        return CongestionLevel.MODERATE

    if phase == MatchPhase.INNINGS_BREAK:
        return CongestionLevel.MODERATE

    return CongestionLevel.LOW


def should_activate_exit_mode(phase: MatchPhase, minutes_until_end: int) -> bool:
    """Decide whether the UI should flip from quiet to exit mode.

    Triggers:
    - Phase is FINAL_OVERS (batting side's last few overs)
    - Phase is TROPHY_CEREMONY (ceremony ongoing, good time to plan exit)
    - Less than 25 minutes of match remaining
    """
    if phase in {MatchPhase.FINAL_OVERS, MatchPhase.TROPHY_CEREMONY}:
        return True
    return minutes_until_end <= 25 and phase != MatchPhase.PRE_MATCH
