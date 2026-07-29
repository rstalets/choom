from __future__ import annotations

from pathlib import Path

import pytest

from endpaper.cli.main import main
from endpaper.core.errors import UsageError
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListScreen
from endpaper.tui.status_bar import StatusBar


def test_cli_type_daily_rejected_exit_2_naming_note_today(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["note", "new", "x", "--type", "daily"])
    assert exit_code == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "endpaper note today" in captured.err
    assert list((tmp_path / "notes").glob("*.md")) == []


async def test_tui_dotted_daily_command_rejected_and_no_file_created(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        for ch in "note.daily anything":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        status = app.screen.query_one(StatusBar)
        assert "endpaper note today" in str(status.content)
        assert list(tmp_workspace.notes_dir.glob("*.md")) == []
        assert list(tmp_workspace.daily_dir.glob("*.md")) == []


@pytest.mark.parametrize("bad_type", ["../evil", "a/b", "a\\b", "-leading", "a.b"])
def test_type_with_path_hazard_characters_rejected_before_any_write(
    tmp_workspace: Workspace, bad_type: str
) -> None:
    with pytest.raises(UsageError):
        create_note(tmp_workspace, "hack", type=bad_type)

    assert list(tmp_workspace.notes_dir.glob("*.md")) == []
