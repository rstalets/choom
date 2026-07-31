from __future__ import annotations

from datetime import datetime

from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import DocumentRow, ListView
from endpaper.tui.preview_screen import PreviewScreen


async def _switch(pilot, verb: str) -> None:
    await pilot.press("/")
    await pilot.pause()
    for ch in verb:
        await pilot.press(ch)
    await pilot.press("enter")
    await pilot.pause()


async def test_daily_and_typed_notes_appear_together_sorted_date_descending(
    tmp_workspace: Workspace,
) -> None:
    from endpaper.core.notes import open_daily_note

    create_note(tmp_workspace, "oldest", now=datetime(2026, 7, 20, 9, 0, 0))
    open_daily_note(tmp_workspace, now=datetime(2026, 7, 25, 9, 0, 0))
    create_note(tmp_workspace, "newest", now=datetime(2026, 7, 28, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await _switch(pilot, "notes")

        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["newest", "2026-07-25", "oldest"]


async def test_filter_narrows_visible_note_rows_live(tmp_workspace: Workspace) -> None:
    create_note(tmp_workspace, "vendor renewal", tags=("procurement",))
    create_note(tmp_workspace, "standup notes", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await _switch(pilot, "notes")

        await pilot.press("/")
        await pilot.pause()
        for ch in "filter vendor":
            await pilot.press("space" if ch == " " else ch)
        await pilot.pause()

        visible = app.visible_documents()
        assert len(visible) == 1
        assert visible[0].title == "vendor renewal"


async def test_enter_opens_rendered_note_preview(tmp_workspace: Workspace) -> None:
    create_note(tmp_workspace, "vendor renewal", type="research")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await _switch(pilot, "notes")

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.document is not None
        assert app.screen.document.title == "vendor renewal"


async def test_switching_between_collections_shows_current_content_including_new_notes(
    tmp_workspace: Workspace,
) -> None:
    from endpaper.core.meetings import create_meeting

    create_meeting(tmp_workspace, "Q3 planning")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await _switch(pilot, "meetings")

        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["Q3 planning"]

        # Create a note while viewing meetings.
        await pilot.press("/")
        await pilot.pause()
        for ch in "note.research vendor landscape":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        await _switch(pilot, "notes")
        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor landscape"]

        await _switch(pilot, "meetings")
        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["Q3 planning"]
