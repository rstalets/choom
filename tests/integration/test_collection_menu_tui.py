from __future__ import annotations

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import CollectionRow, DocumentRow, ListScreen, ListView
from endpaper.tui.preview_screen import PreviewScreen


async def test_menu_shows_both_collections_with_meetings_active_at_launch(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        menu = app.screen.query_one("#collection-menu", ListView)
        names = [row.collection_name for row in menu.children if isinstance(row, CollectionRow)]
        assert names == ["meetings", "notes"]
        assert menu.index == 0
        assert app.active == "meetings"


async def test_left_then_down_switches_to_notes_and_updates_list_live(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    create_note(tmp_workspace, "vendor landscape", type="research")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("left")
        await pilot.pause()

        menu = app.screen.query_one("#collection-menu", ListView)
        assert menu.has_focus

        await pilot.press("j")
        await pilot.pause()

        assert app.active == "notes"
        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor landscape"]


async def test_right_from_menu_returns_focus_to_list(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("left")
        await pilot.pause()
        assert app.screen.query_one("#collection-menu", ListView).has_focus

        await pilot.press("right")
        await pilot.pause()
        assert app.screen.query_one("#meeting-list", ListView).has_focus


async def test_enter_on_menu_row_moves_focus_to_list(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("left")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.query_one("#meeting-list", ListView).has_focus


async def test_creating_a_note_while_viewing_meetings_lands_on_notes_after_escape(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "meetings"

        await pilot.press("/")
        await pilot.pause()
        for ch in "note.research vendor landscape":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PreviewScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        assert app.active == "notes"

        menu = app.screen.query_one("#collection-menu", ListView)
        assert menu.index == 1

        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor landscape"]


async def test_creating_a_meeting_while_viewing_notes_lands_on_meetings_after_escape(
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
        assert isinstance(app.screen, PreviewScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert app.active == "meetings"
        menu = app.screen.query_one("#collection-menu", ListView)
        assert menu.index == 0


async def test_bare_daily_note_lands_on_notes_view_after_escape(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        for ch in "note":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PreviewScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert app.active == "notes"
