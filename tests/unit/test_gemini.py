"""Tests for the Gemini service wrapper.

We never call the real Gemini API from tests — that would be slow, flaky,
and cost money. Instead we monkeypatch the google.genai Client to return
canned responses, which tests our wiring without hitting the network.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services import gemini as gemini_module


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_call: dict[str, Any] | None = None

    def generate_content(self, **kwargs: Any) -> _FakeResponse:
        self.last_call = kwargs
        return _FakeResponse(self._response_text)


class _FakeClient:
    def __init__(self, response_text: str) -> None:
        self.models = _FakeModels(response_text)


def _install_fake(monkeypatch: pytest.MonkeyPatch, response_text: str) -> _FakeClient:
    """Patch the gemini module so generate_json uses a fake client."""
    fake = _FakeClient(response_text)
    monkeypatch.setattr(gemini_module, "_client", lambda: fake)
    return fake


def test_generate_json_parses_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake(monkeypatch, '{"hello": "world"}')
    result = gemini_module.generate_json("prompt", "schema")
    assert result == {"hello": "world"}


def test_generate_json_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake(monkeypatch, "not json at all")
    with pytest.raises(ValueError, match="not valid JSON"):
        gemini_module.generate_json("prompt", "schema")


def test_generate_json_raises_on_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake(monkeypatch, "")
    with pytest.raises(ValueError, match="empty"):
        gemini_module.generate_json("prompt", "schema")


def test_generate_json_passes_json_mime_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract: we must request JSON mode so Gemini returns parseable output."""
    fake = _install_fake(monkeypatch, '{"a": 1}')
    gemini_module.generate_json("prompt", "schema")
    assert fake.models.last_call is not None
    cfg = fake.models.last_call.get("config")
    assert cfg is not None
    assert cfg.response_mime_type == "application/json"


def test_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing key must raise, not silently call an unauthenticated API."""
    # Stub settings to return empty key
    fake_settings = MagicMock()
    fake_settings.gemini_api_key = ""
    monkeypatch.setattr(gemini_module, "get_settings", lambda: fake_settings)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gemini_module._client()
