"""Smoke tests for the FastAPI app.

These assert the app boots, serves the index, and returns security headers.
They catch the 80% of regressions that break everything downstream.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    """The liveness probe must return 200 with status ok."""
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_index_renders() -> None:
    """The root page must render successfully and contain the app name."""
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "FlowPass" in response.text


def test_security_headers_present() -> None:
    """Every response must include the standard security headers."""
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert "Referrer-Policy" in response.headers


def test_unknown_route_returns_404() -> None:
    """Unknown routes return 404, not 500, and leak no stack trace."""
    with TestClient(app) as client:
        response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert "Traceback" not in response.text
