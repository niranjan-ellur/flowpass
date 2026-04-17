"""Integration tests for the recommendation API and updated index.

These exercise the full request pipeline: FastAPI routing, Pydantic
validation, engine call, and template rendering.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_index_contains_section_dropdown() -> None:
    """The picker form must list venue sections so the user can pick one."""
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert 'name="section_id"' in response.text
    assert "Pavilion North" in response.text
    assert "Chinnaraya Stadium" in response.text


def test_index_contains_phase_scrubber() -> None:
    """All six phases must be selectable in the demo scrubber."""
    with TestClient(app) as client:
        response = client.get("/")
    for phase in (
        "pre_match",
        "in_play",
        "innings_break",
        "final_overs",
        "trophy_ceremony",
        "post_match",
    ):
        assert f'value="{phase}"' in response.text


def test_recommendation_endpoint_returns_html_for_entry() -> None:
    """Posting pre-match phase should return an entry-mode card."""
    with TestClient(app) as client:
        response = client.post(
            "/api/recommendation",
            data={
                "section_id": "P1",
                "transit_mode": "metro",
                "phase": "pre_match",
            },
        )
    assert response.status_code == 200
    assert "Entry mode" in response.text
    assert "Gate 1" in response.text  # P1 -> G1


def test_recommendation_endpoint_returns_exit_mode_in_final_overs() -> None:
    """Final overs should return an exit-mode card."""
    with TestClient(app) as client:
        response = client.post(
            "/api/recommendation",
            data={
                "section_id": "P1",
                "transit_mode": "metro",
                "phase": "final_overs",
            },
        )
    assert response.status_code == 200
    assert "Exit mode" in response.text


def test_recommendation_endpoint_rejects_bad_section() -> None:
    """Unknown section id must fail validation, not crash."""
    with TestClient(app) as client:
        response = client.post(
            "/api/recommendation",
            data={
                "section_id": "ZZ9",
                "transit_mode": "metro",
                "phase": "pre_match",
            },
        )
    assert response.status_code == 422


def test_recommendation_endpoint_rejects_bad_transit() -> None:
    """Unknown transit mode must fail validation, not crash."""
    with TestClient(app) as client:
        response = client.post(
            "/api/recommendation",
            data={
                "section_id": "P1",
                "transit_mode": "teleporter",
                "phase": "pre_match",
            },
        )
    assert response.status_code == 422


def test_recommendation_endpoint_rejects_bad_phase() -> None:
    """Unknown match phase must fail validation, not crash."""
    with TestClient(app) as client:
        response = client.post(
            "/api/recommendation",
            data={
                "section_id": "P1",
                "transit_mode": "metro",
                "phase": "lunchtime",
            },
        )
    assert response.status_code == 422


def test_step_free_flag_is_honored_in_response() -> None:
    """Ticking step-free for P3 should route via G5, not the default first gate."""
    with TestClient(app) as client:
        response = client.post(
            "/api/recommendation",
            data={
                "section_id": "P3",
                "transit_mode": "metro",
                "step_free": "1",
                "phase": "pre_match",
            },
        )
    assert response.status_code == 200
    assert "Gate 5" in response.text
