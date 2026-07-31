from __future__ import annotations

import pytest

import endpaper.core.assistants as assistants
from endpaper.core.assistants import resolve_assistant


def _patch_available(monkeypatch: pytest.MonkeyPatch, names: tuple[str, ...]) -> None:
    monkeypatch.setattr(assistants, "available_assistants", lambda: names)


def test_configured_claude_resolves_to_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_available(monkeypatch, ())
    resolved = resolve_assistant("claude")
    assert resolved.profile is not None
    assert resolved.profile.name == "claude"
    assert resolved.source == "configured"


def test_configured_copilot_resolves_to_copilot(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_available(monkeypatch, ())
    resolved = resolve_assistant("copilot")
    assert resolved.profile is not None
    assert resolved.profile.name == "copilot"
    assert resolved.source == "configured"


def test_configured_none_does_not_fall_back_to_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_available(monkeypatch, ("claude",))
    resolved = resolve_assistant("none")
    assert resolved.profile is None
    assert resolved.source == "none"
    assert resolved.available == ("claude",)


def test_absent_with_exactly_one_available_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_available(monkeypatch, ("claude",))
    resolved = resolve_assistant(None)
    assert resolved.profile is not None
    assert resolved.profile.name == "claude"
    assert resolved.source == "detected"


def test_absent_with_two_available_is_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_available(monkeypatch, ("claude", "copilot"))
    resolved = resolve_assistant(None)
    assert resolved.profile is None
    assert resolved.source == "ambiguous"
    assert resolved.available == ("claude", "copilot")


def test_absent_with_none_available_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_available(monkeypatch, ())
    resolved = resolve_assistant(None)
    assert resolved.profile is None
    assert resolved.source == "unset"


def test_unrecognised_configured_value_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_available(monkeypatch, ())
    resolved = resolve_assistant("gpt")
    assert resolved.profile is None
    assert resolved.source == "unset"


def test_available_assistants_needs_nothing_installed() -> None:
    # No stub, no PATH manipulation -- this must not hang or raise.
    result = assistants.available_assistants()
    assert isinstance(result, tuple)
