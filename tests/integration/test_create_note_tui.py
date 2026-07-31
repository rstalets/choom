from __future__ import annotations

from endpaper.core.documents import _read_document
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen


async def _type(pilot, text: str) -> None:
    for ch in text:
        await pilot.press("space" if ch == " " else ch)


async def test_dotted_note_command_creates_typed_note(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "note.research vendor landscape #procurement")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        document = _read_document(app.screen.file.path)
        assert document is not None
        assert document.title == "vendor landscape"
        assert document.type == "research"
        assert document.tags == ("procurement",)
        assert document.path.is_relative_to(tmp_workspace.notes_dir)


async def test_bare_note_with_description_creates_untyped_note_not_daily(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "note vendor landscape")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        document = _read_document(app.screen.file.path)
        assert document is not None
        assert document.title == "vendor landscape"
        assert document.type == ""

        # The daily note must not exist -- a description means a note, never
        # the daily note (spec Assumptions, R5).
        assert list(tmp_workspace.daily_dir.glob("*.md")) == []
