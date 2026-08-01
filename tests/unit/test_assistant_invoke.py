from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from choom.core.assistants import PROFILES, compose_prompt, start_request

_CLAUDE = next(p for p in PROFILES if p.name == "claude")


def test_echo_mode_proves_the_composed_prompt_reached_argv(
    tmp_path: Path, stub_assistant: Callable[[str], None]
) -> None:
    stub_assistant("echo")
    prompt = compose_prompt("summarise the bullets above", tmp_path / "note.md", 7)

    request = start_request(_CLAUDE, prompt, cwd=tmp_path)
    reply = request.wait()

    assert reply.ok is True
    assert "summarise the bullets above" in reply.text
    assert str(tmp_path / "note.md") in reply.text


def test_non_zero_exit_reports_failure_naming_the_assistant(
    tmp_path: Path, stub_assistant: Callable[[str], None]
) -> None:
    stub_assistant("fail")
    request = start_request(_CLAUDE, "anything", cwd=tmp_path)
    reply = request.wait()

    assert reply.ok is False
    assert reply.cancelled is False
    assert "Claude Code CLI" in reply.message
    assert "stub failure" in reply.message


def test_empty_output_is_reported_as_empty_reply(
    tmp_path: Path, stub_assistant: Callable[[str], None]
) -> None:
    stub_assistant("empty")
    request = start_request(_CLAUDE, "anything", cwd=tmp_path)
    reply = request.wait()

    assert reply.ok is False
    assert reply.text == ""
    assert "empty reply" in reply.message


def test_missing_binary_is_reported_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # PATH is replaced with an empty directory -- not just "no stub fixture" -- so
    # this is deterministic even on a machine that has a real `claude` installed
    # (as this one does, being run by Claude Code itself).
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    request = start_request(_CLAUDE, "anything", cwd=tmp_path)
    reply = request.wait()

    assert reply.ok is False
    assert "not installed" in reply.message or "not on your PATH" in reply.message


def test_reply_mode_returns_the_fixed_multiline_text(
    tmp_path: Path, stub_assistant: Callable[[str], None]
) -> None:
    stub_assistant("reply")
    request = start_request(_CLAUDE, "anything", cwd=tmp_path)
    reply = request.wait()

    assert reply.ok is True
    assert reply.text == "line one\nline two\nline three"


def test_claude_build_args_grants_read_only_permission() -> None:
    args = _CLAUDE.build_args("a prompt")
    assert args == ["-p", "a prompt", "--allowedTools", "Read"]


def test_copilot_build_args_grants_read_only_permission() -> None:
    copilot = next(p for p in PROFILES if p.name == "copilot")
    args = copilot.build_args("a prompt")
    assert args == ["-p", "a prompt", "--allow-tool", "read", "-s"]


def test_echo_mode_shows_the_permission_flag_reached_argv(
    tmp_path: Path, stub_assistant: Callable[[str], None]
) -> None:
    # Without --allowedTools "Read", a real Claude Code CLI in -p mode silently
    # denies the file read compose_prompt asks it to do (research R13) -- this
    # locks the flag into the actual argv, not just the pure build_args() return.
    stub_assistant("echo")
    request = start_request(_CLAUDE, "a prompt", cwd=tmp_path)
    reply = request.wait()

    assert reply.ok is True
    assert "--allowedTools" in reply.text
    assert "Read" in reply.text
