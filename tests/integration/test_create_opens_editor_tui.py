from __future__ import annotations

from datetime import datetime

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace, YearMonth
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import ListScreen
from tests.helpers import list_view, to_collection, type_command


def _one_month_before(dt: datetime) -> datetime:
    if dt.month == 1:
        return dt.replace(year=dt.year - 1, month=12, day=1)
    return dt.replace(month=dt.month - 1, day=1)


async def test_creating_a_meeting_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "meeting.standup Q3 planning")

        assert isinstance(app.screen, EditScreen)


async def test_creating_a_note_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note.research vendor landscape")

        assert isinstance(app.screen, EditScreen)


async def test_creating_the_daily_note_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note")

        assert isinstance(app.screen, EditScreen)


async def test_create_moves_scope_to_new_month(tmp_workspace: Workspace) -> None:
    now = datetime.now()
    last_month = _one_month_before(now)
    create_meeting(tmp_workspace, "an older meeting", now=last_month)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # move to the older month
        await pilot.pause()
        assert app.scope_selection["meetings"] == YearMonth(last_month.year, last_month.month)

        await pilot.press("l")
        await pilot.pause()
        await type_command(app, pilot, "meeting.standup a new one")
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")  # nothing edited yet, pops immediately
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        current_month = YearMonth(now.year, now.month)
        assert app.scope_selection["meetings"] == current_month
        highlighted = list_view(app).highlighted_child
        assert highlighted is not None
        assert highlighted.document.title == "a new one"  # type: ignore[union-attr]


async def test_exiting_after_create_lands_on_the_list_in_the_new_documents_month(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note.research vendor landscape")
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert app.active == "notes"
        highlighted = list_view(app).highlighted_child
        assert highlighted is not None
        assert highlighted.document.title == "vendor landscape"  # type: ignore[union-attr]
