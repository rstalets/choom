from __future__ import annotations

from datetime import datetime

from choom.core.meetings import create_meeting
from choom.core.models import Workspace, YearMonth
from choom.tui.app import ChoomApp
from choom.tui.edit_screen import EditorPane
from choom.tui.list_screen import ListScreen
from tests.helpers import editor_pane, list_view, to_collection, type_command


def _one_month_before(dt: datetime) -> datetime:
    if dt.month == 1:
        return dt.replace(year=dt.year - 1, month=12, day=1)
    return dt.replace(month=dt.month - 1, day=1)


async def test_creating_a_meeting_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    # Creating from the list opens inline (contract C1, US4): the list is
    # never left, and the new record is already the highlighted row while
    # the editor is open (FR-016, research R8) -- the list and the pane agree
    # about what is being edited rather than catching up on close.
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "meeting.standup Q3 planning")

        assert isinstance(app.screen, ListScreen)
        editor_pane(app)  # asserts one is mounted
        highlighted = list_view(app).highlighted_child
        assert highlighted is not None
        assert highlighted.document.title == "Q3 planning"  # type: ignore[union-attr]


async def test_creating_a_note_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note.research vendor landscape")

        assert isinstance(app.screen, ListScreen)
        editor_pane(app)  # asserts one is mounted
        highlighted = list_view(app).highlighted_child
        assert highlighted is not None
        assert highlighted.document.title == "vendor landscape"  # type: ignore[union-attr]


async def test_creating_the_daily_note_opens_the_editor_directly(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note")

        assert isinstance(app.screen, ListScreen)
        editor_pane(app)  # asserts one is mounted
        highlighted = list_view(app).highlighted_child
        assert highlighted is not None


async def test_create_moves_scope_to_new_month(tmp_workspace: Workspace) -> None:
    now = datetime.now()
    last_month = _one_month_before(now)
    create_meeting(tmp_workspace, "an older meeting", now=last_month)

    app = ChoomApp(tmp_workspace)
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
        assert isinstance(app.screen, ListScreen)
        editor_pane(app)  # asserts one is mounted

        await pilot.press("escape")  # nothing edited yet, closes immediately
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert not app.screen.query(EditorPane)
        current_month = YearMonth(now.year, now.month)
        assert app.scope_selection["meetings"] == current_month
        highlighted = list_view(app).highlighted_child
        assert highlighted is not None
        assert highlighted.document.title == "a new one"  # type: ignore[union-attr]


async def test_exiting_after_create_lands_on_the_list_in_the_new_documents_month(
    tmp_workspace: Workspace,
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note.research vendor landscape")
        assert isinstance(app.screen, ListScreen)
        editor_pane(app)  # asserts one is mounted

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert not app.screen.query(EditorPane)
        assert app.active == "notes"
        highlighted = list_view(app).highlighted_child
        assert highlighted is not None
        assert highlighted.document.title == "vendor landscape"  # type: ignore[union-attr]
