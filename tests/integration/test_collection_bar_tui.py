from __future__ import annotations

from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.collection_bar import COLLECTIONS, CollectionBar
from endpaper.tui.command_bar import CommandBar
from endpaper.tui.list_screen import ListView


async def test_bar_lists_three_collections_with_one_active(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert COLLECTIONS == ("tasks", "notes", "meetings")
        assert app.active == "tasks"

        bar = app.screen.query_one(CollectionBar)
        rendered = str(bar.content)
        assert "Tasks" in rendered
        assert "Notes" in rendered
        assert "Meetings" in rendered
        # exactly one collection is styled as active
        assert rendered.count("[reverse]") == 1


async def test_tab_wraps_and_focuses_list(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"

        await pilot.press("tab")
        await pilot.pause()
        assert app.active == "notes"
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert list_view.has_focus
        assert list_view.index == 0

        await pilot.press("tab")
        await pilot.pause()
        assert app.active == "meetings"

        await pilot.press("tab")
        await pilot.pause()
        assert app.active == "tasks"  # wrapped past Meetings back to Tasks

        await pilot.press("shift+tab")
        await pilot.pause()
        assert app.active == "meetings"  # wraps the other way too


async def test_tab_inert_while_command_bar_open(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"

        await pilot.press("/")
        await pilot.pause()
        await pilot.press("f", "i", "l")
        await pilot.pause()

        await pilot.press("tab")
        await pilot.pause()

        assert app.active == "tasks"  # unchanged -- the keystroke belonged to the bar
        assert app.screen.query_one(CommandBar).display is True
