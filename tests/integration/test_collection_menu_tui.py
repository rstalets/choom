from __future__ import annotations

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.notes import create_note
from choom.tui.app import ChoomApp
from choom.tui.collection_bar import CollectionBar
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import ListScreen
from tests.helpers import row_titles, to_collection, type_command


async def test_creating_a_note_while_viewing_meetings_lands_on_notes_after_close(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert app.active == "meetings"

        await type_command(app, pilot, "note.research vendor landscape")
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")  # nothing edited yet, so this pops immediately
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        assert app.active == "notes"

        bar = app.screen.query_one(CollectionBar)
        assert "[reverse] Notes [/reverse]" in str(bar.content)

        assert row_titles(app) == ["vendor landscape"]


async def test_creating_a_meeting_while_viewing_notes_lands_on_meetings_after_close(
    tmp_workspace: Workspace,
) -> None:
    create_note(tmp_workspace, "an idea")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "notes")
        assert app.active == "notes"

        await type_command(app, pilot, "meeting.standup Q3 planning")
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert app.active == "meetings"
        bar = app.screen.query_one(CollectionBar)
        assert "[reverse] Meetings [/reverse]" in str(bar.content)


async def test_bare_daily_note_lands_on_notes_view_after_close(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note")
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert app.active == "notes"
