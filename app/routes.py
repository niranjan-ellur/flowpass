"""HTTP routes for FlowPass.

Kept thin. Each handler parses input (Pydantic does the work), calls the
engine (pure), and returns HTML (Jinja). Anything more complex belongs
in the engine or a service.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.engine import recommend
from app.models import (
    MatchPhase,
    MatchState,
    TransitMode,
    UserPreferences,
    Venue,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter()


# Rough time-remaining estimates per phase. In a real build this would come
# from a live sports feed; here it's a plausible mock for the demo scrubber.
_PHASE_TIME_LEFT: dict[MatchPhase, tuple[int, int]] = {
    MatchPhase.PRE_MATCH: (0, 210),
    MatchPhase.IN_PLAY: (60, 150),
    MatchPhase.INNINGS_BREAK: (105, 105),
    MatchPhase.FINAL_OVERS: (195, 8),
    MatchPhase.TROPHY_CEREMONY: (215, 10),
    MatchPhase.POST_MATCH: (220, 0),
}


def _match_state_from_phase(phase: MatchPhase) -> MatchState:
    """Build a plausible MatchState for the demo scrubber's current phase."""
    into, left = _PHASE_TIME_LEFT[phase]
    return MatchState(
        phase=phase,
        minutes_into_match=into,
        minutes_until_end_estimate=left,
    )


@router.post("/api/recommendation", response_class=HTMLResponse)
async def get_recommendation(
    request: Request,
    section_id: str = Form(...),
    transit_mode: str = Form(...),
    step_free: str = Form(default=""),
    phase: str = Form(default="pre_match"),
) -> HTMLResponse:
    """Return an HTML fragment with the current recommendation.

    Called via HTMX from the main page. Returning HTML directly keeps the
    client simple: no JSON parsing, no render logic on the client side.
    """
    venue: Venue = request.app.state.venue

    try:
        prefs = UserPreferences(
            section_id=section_id,
            transit_mode=TransitMode(transit_mode),
            step_free=bool(step_free),
        )
        match_phase = MatchPhase(phase)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}") from exc

    match_state = _match_state_from_phase(match_phase)

    try:
        rec = recommend(venue, prefs, match_state)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return templates.TemplateResponse(
        request=request,
        name="partials/recommendation.html",
        context={"rec": rec, "phase": match_phase.value},
    )
