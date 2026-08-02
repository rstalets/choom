from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from choom.cli.main import main
from choom.core.workspace import init_workspace
from choom.tui.app import ChoomApp
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import ListView, TaskRow
from tests.helpers import type_command

_MASKED_FIELDS = re.compile(r"^(id|created|updated):.*$", re.MULTILINE)


def _normalize(text: str) -> str:
    return _MASKED_FIELDS.sub(r"\1: <masked>", text)


async def _create_via_tui(workspace, command_text: str) -> Path:  # type: ignore[no-untyped-def]
    app = ChoomApp(workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, command_text)
        assert isinstance(app.screen, EditScreen)
        return app.screen.pane.target.display_path


@pytest.mark.parametrize(
    ("argv", "command_text"),
    [
        pytest.param(
            ["meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform"],
            "meeting.standup Q3 planning #platform",
            id="meeting",
        ),
        pytest.param(
            ["note", "new", "vendor landscape", "--type", "research", "--tag", "procurement"],
            "note.research vendor landscape #procurement",
            id="note",
        ),
    ],
)
def test_cli_and_tui_create_identical_except_id_and_timestamps(
    tmp_path: Path, monkeypatch, capsys, argv: list[str], command_text: str
) -> None:
    cli_dir = tmp_path / "cli"
    cli_dir.mkdir()
    monkeypatch.chdir(cli_dir)
    main(["init"])
    capsys.readouterr()
    main(argv)
    cli_relative_path = capsys.readouterr().out.strip()
    cli_text = (cli_dir / cli_relative_path).read_text(encoding="utf-8")

    tui_dir = tmp_path / "tui"
    tui_dir.mkdir()
    workspace = init_workspace(tui_dir).workspace
    tui_path = asyncio.run(_create_via_tui(workspace, command_text))
    tui_text = tui_path.read_text(encoding="utf-8")

    assert _normalize(cli_text) == _normalize(tui_text)


_SEED = "- [ ] send the vendor comparison <!-- id:task_a1b2 type:followup created:2026-07-28 -->\n"


async def _toggle_via_tui(workspace) -> None:  # type: ignore[no-untyped-def]
    app = ChoomApp(workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert isinstance(list_view.highlighted_child, TaskRow)
        await pilot.press("space")
        await pilot.pause()


def test_cli_and_tui_toggle_produce_byte_identical_files(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    cli_dir = tmp_path / "cli"
    cli_dir.mkdir()
    monkeypatch.chdir(cli_dir)
    main(["init"])
    capsys.readouterr()
    (cli_dir / "tasks.md").write_text(_SEED, encoding="utf-8", newline="\n")

    main(["task", "done", "task_a1b2"])
    capsys.readouterr()
    cli_text = (cli_dir / "tasks.md").read_text(encoding="utf-8")

    tui_dir = tmp_path / "tui"
    workspace = init_workspace(tui_dir).workspace
    workspace.tasks_file.write_text(_SEED, encoding="utf-8", newline="\n")

    asyncio.run(_toggle_via_tui(workspace))
    tui_text = workspace.tasks_file.read_text(encoding="utf-8")

    assert tui_text == cli_text
    assert "[x]" in tui_text
