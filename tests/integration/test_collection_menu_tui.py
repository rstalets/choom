from __future__ import annotations

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.tui.app import EndpaperApp
from endpaper.tui.collection_bar import CollectionBar
from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import DocumentRow, ListScreen, ListView


async def test_creating_a_note_while_viewing_meetings_lands_on_notes_after_close(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        assert app.active == "meetings"

        await pilot.press("/")
        await pilot.pause()
        for ch in "note.research vendor landscape":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")  # nothing edited yet, so this pops immediately
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        assert app.active == "notes"

        bar = app.screen.query_one(CollectionBar)
        assert "[reverse] Notes [/reverse]" in str(bar.content)

        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor landscape"]


async def test_creating_a_meeting_while_viewing_notes_lands_on_meetings_after_close(
    tmp_workspace: Workspace,
) -> None:
    create_note(tmp_workspace, "an idea")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        for ch in "notes":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        assert app.active == "notes"

        await pilot.press("/")
        await pilot.pause()
        for ch in "meeting.standup Q3 planning":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert app.active == "meetings"
        bar = app.screen.query_one(CollectionBar)
        assert "[reverse] Meetings [/reverse]" in str(bar.content)


async def test_bare_daily_note_lands_on_notes_view_after_close(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        for ch in "note":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert app.active == "notes"
