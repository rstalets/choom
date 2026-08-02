"""Contract tests for `choom config assistant`'s discovery-file surface
(013-assistant-discovery-file, contracts/cli-config-assistant.md). Covers: the
one-file invariant after any successful set (T030), stdout staying empty on a set,
a read writing nothing anywhere, and the unwritable-profile failure matrix (T035).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from choom.cli.main import main
from choom.core.assistants import PROFILES
from choom.core.discovery import discovery_path
from choom.core.models import Workspace

_COPILOT = next(p for p in PROFILES if p.name == "copilot")


def _installed_paths() -> list[Path]:
    from choom.core.assistants import PROFILES
    from choom.core.discovery import MARKER

    found = []
    for profile in PROFILES:
        path = discovery_path(profile)
        if path is not None and path.is_file() and MARKER in path.read_text(encoding="utf-8"):
            found.append(path)
    return found


# --- the one-file invariant (T030) --------------------------------------------------


def test_at_most_one_file_after_setting_claude(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    assert main(["config", "assistant", "claude"]) == 0
    capsys.readouterr()

    assert len(_installed_paths()) == 1


def test_at_most_one_file_after_switching_assistants(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["config", "assistant", "claude"])
    capsys.readouterr()
    main(["config", "assistant", "copilot"])
    capsys.readouterr()

    installed = _installed_paths()
    assert len(installed) == 1
    assert installed[0] == discovery_path(_COPILOT)


def test_none_removes_every_choom_owned_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["config", "assistant", "claude"])
    capsys.readouterr()
    assert main(["config", "assistant", "none"]) == 0
    capsys.readouterr()

    assert _installed_paths() == []


def test_none_with_nothing_installed_still_succeeds(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    assert main(["config", "assistant", "none"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""


# --- stdout stays empty on a set; a read writes nothing -----------------------------


def test_set_writes_nothing_to_stdout(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    assert main(["config", "assistant", "claude"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_read_writes_nothing_to_the_profile_directory(tmp_path: Path, monkeypatch, capsys) -> None:
    from choom.core.discovery import profile_root

    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["config", "assistant", "claude"])
    capsys.readouterr()

    before = sorted(profile_root().rglob("*"))
    before_mtimes = {p: p.stat().st_mtime_ns for p in before if p.is_file()}

    main(["config", "assistant"])
    main(["config", "assistant", "--json"])
    capsys.readouterr()

    after = sorted(profile_root().rglob("*"))
    after_mtimes = {p: p.stat().st_mtime_ns for p in after if p.is_file()}
    assert after == before
    assert after_mtimes == before_mtimes


# --- unwritable profile directory (T035, contract failure matrix) -------------------


@pytest.mark.skipif(os.name == "nt", reason="chmod-based permission simulation is POSIX-only")
def test_unwritable_profile_directory_still_records_setting_and_reports_on_stderr(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from choom.core.discovery import profile_root

    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    # Lock down the whole fake profile root so the skill directory cannot be created.
    root = profile_root()
    root.chmod(stat.S_IREAD | stat.S_IEXEC)
    try:
        exit_code = main(["config", "assistant", "claude"])
    finally:
        root.chmod(stat.S_IRWXU)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert captured.err != ""

    # The setting itself is still recorded (FR-013) despite the discovery-file
    # failure.
    workspace = Workspace(root=tmp_path)
    from choom.core.config import get_assistant

    assert get_assistant(workspace) == "claude"
