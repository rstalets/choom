from __future__ import annotations

import pytest

from endpaper.core.errors import UsageError
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListScreen
from endpaper.tui.status_bar import StatusBar
from tests.helpers import type_command


def test_cli_type_daily_rejected_exit_2_naming_note_today(cli) -> None:
    result = cli("note", "new", "x", "--type", "daily")
    assert result.exit_code == 2

    assert result.out == ""
    assert "endpaper note today" in result.err
    assert list((cli.root / "notes").glob("*.md")) == []


async def test_tui_dotted_daily_command_rejected_and_no_file_created(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note.daily anything")

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
