from __future__ import annotations

from datetime import datetime

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace, YearMonth
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import ListScreen, ListView


def _one_month_before(dt: datetime) -> datetime:
    if dt.month == 1:
        return dt.replace(year=dt.year - 1, month=12, day=1)
    return dt.replace(month=dt.month - 1, day=1)


async def _type(pilot, text: str) -> None:  # type: ignore[no-untyped-def]
    for ch in text:
        await pilot.press("space" if ch == " " else ch)


async def test_creating_a_meeting_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "meeting.standup Q3 planning")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)


async def test_creating_a_note_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "note.research vendor landscape")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)


async def test_creating_the_daily_note_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "note")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)


async def test_create_moves_scope_to_new_month(tmp_workspace: Workspace) -> None:
    now = datetime.now()
    last_month = _one_month_before(now)
    create_meeting(tmp_workspace, "an older meeting", now=last_month)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # move to the older month
        await pilot.pause()
        assert app.scope_selection["meetings"] == YearMonth(last_month.year, last_month.month)

        await pilot.press("l")
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "meeting.standup a new one")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")  # nothing edited yet, pops immediately
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        current_month = YearMonth(now.year, now.month)
        assert app.scope_selection["meetings"] == current_month
        list_view = app.screen.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        assert highlighted is not None
        assert highlighted.document.title == "a new one"  # type: ignore[union-attr]


async def test_exiting_after_create_lands_on_the_list_in_the_new_documents_month(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "note.research vendor landscape")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert app.active == "notes"
        list_view = app.screen.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        assert highlighted is not None
        assert highlighted.document.title == "vendor landscape"  # type: ignore[union-attr]
