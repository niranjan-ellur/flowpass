"""Venue graph loader.

Loads venue.json once at app startup and returns the validated Venue
object to callers. Kept in app.services because it's I/O; the engine
stays pure.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models import Venue


def load_venue(path: str | Path) -> Venue:
    """Read venue.json from disk and validate against the Venue schema.

    Raises pydantic.ValidationError if the file is malformed. That error
    is fatal: if the venue graph is wrong, no recommendation can be trusted.
    """
    venue_path = Path(path)
    with venue_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return Venue.model_validate(raw)
