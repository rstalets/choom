"""US2 end-to-end: the once-only launch offer, driven through the TUI
(013-assistant-discovery-file, tasks.md T024). `Enter` installs and records; `Esc`
installs nothing but still records; a second launch never asks again; and each
suppression case in `should_offer_discovery`'s matrix shows no dialog at all.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from choom.core.config import get_assistant, get_launch_offer_made, set_assistant
from choom.core.discovery import discovery_path, install_discovery_file
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.confirm_dialog import ConfirmDialog
from choom.tui.list_screen import ListScreen
from choom.tui.status_bar import StatusBar


@pytest.fixture
def exactly_claude_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace PATH entirely with a directory holding just a fake `claude`, so
    `available_assistants()` resolves to exactly one -- deterministic regardless of
    what is actually installed on the machine running the suite."""
    bindir = tmp_path / "exactly-claude-bin"
    bindir.mkdir()
    script = bindir / ("claude.cmd" if os.name == "nt" else "claude")
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))


async def test_offered_once_names_the_assistant_and_workspace(
    tmp_workspace: Workspace, exactly_claude_on_path: None
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        rendered = "\n".join(str(w.render()) for w in app.screen.query("Label"))
        assert "Claude Code CLI" in rendered
        assert str(tmp_workspace.root) in rendered
        assert "(Esc) Not Now" in rendered
        assert "(Enter) Tell It" in rendered


async def test_enter_installs_and_records(
    tmp_workspace: Workspace, exactly_claude_on_path: None
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        status = app.screen.query_one(StatusBar)
        assert "told" in str(status.content).lower() or "claude" in str(status.content).lower()

    assert get_assistant(tmp_workspace) == "claude"
    assert get_launch_offer_made(tmp_workspace) is True

    from choom.core.assistants import PROFILES

    claude = next(p for p in PROFILES if p.name == "claude")
    path = discovery_path(claude)
    assert path is not None
    assert path.is_file()
    assert str(tmp_workspace.root) in path.read_text(encoding="utf-8")


async def test_esc_installs_nothing_but_still_records(
    tmp_workspace: Workspace, exactly_claude_on_path: None
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)

    assert get_launch_offer_made(tmp_workspace) is True
    from choom.core.assistants import PROFILES

    claude = next(p for p in PROFILES if p.name == "claude")
    assert discovery_path(claude) is not None
    assert not discovery_path(claude).is_file()  # type: ignore[union-attr]


async def test_a_second_launch_asks_nothing(
    tmp_workspace: Workspace, exactly_claude_on_path: None
) -> None:
    first = ChoomApp(tmp_workspace)
    async with first.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    second = ChoomApp(tmp_workspace)
    async with second.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(second.screen, ListScreen)


async def test_not_offered_when_discovery_file_already_installed(
    tmp_workspace: Workspace, exactly_claude_on_path: None
) -> None:
    from choom.core.assistants import PROFILES

    claude = next(p for p in PROFILES if p.name == "claude")
    install_discovery_file(tmp_workspace, claude)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)


async def test_not_offered_when_assistant_is_none(
    tmp_workspace: Workspace, exactly_claude_on_path: None
) -> None:
    set_assistant(tmp_workspace, "none")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)


async def test_not_offered_when_no_assistant_is_installed(
    tmp_workspace: Workspace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)


async def test_not_offered_when_ambiguous(
    tmp_workspace: Workspace, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bindir = tmp_path / "two-assistants-bin"
    bindir.mkdir()
    for name in ("claude", "copilot"):
        script = bindir / (f"{name}.cmd" if os.name == "nt" else name)
        script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
