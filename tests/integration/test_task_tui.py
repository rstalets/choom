from __future__ import annotations

from choom.core.meetings import create_meeting, scan_meetings
from choom.core.models import Workspace
from choom.core.notes import create_note
from choom.core.tasks import load_tasks
from choom.tui.app import ChoomApp
from choom.tui.collection_bar import CollectionBar
from choom.tui.list_screen import TaskRow
from choom.tui.status_bar import StatusBar
from tests.helpers import list_view, row_titles, type_command


async def test_command_bar_creates_task_and_lands_on_tasks_selected(
    tmp_workspace: Workspace,
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "task.followup send the vendor comparison #procurement")

        assert app.active == "tasks"
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, TaskRow)
        assert highlighted.record.text == "send the vendor comparison"
        assert highlighted.record.type == "followup"
        assert highlighted.record.tags == ("procurement",)


async def test_bare_task_command_shows_error(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "task")

        status = app.screen.query_one(StatusBar)
        assert "needs a description" in str(status.content)


async def test_space_is_noop_on_meetings_and_notes(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        assert app.active == "meetings"

        await pilot.press("space")
        await pilot.pause()

        assert app.active == "meetings"
        meetings, _ = scan_meetings(tmp_workspace)
        assert len(meetings) == 1


async def test_footer_advertises_space_only_on_tasks(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"
        tasks_text = str(app.screen.query_one(StatusBar).content)
        assert "space toggle" in tasks_text
        assert " a " not in tasks_text
        assert "a all" not in tasks_text

        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        assert app.active == "meetings"
        meetings_text = str(app.screen.query_one(StatusBar).content)
        assert "space" not in meetings_text


async def test_task_created_from_another_collection_does_not_change_the_view(
    tmp_workspace: Workspace,
) -> None:
    # Regression: /task.followup from Notes used to flip the left/middle panes
    # to Tasks without updating the top bar's active marker, leaving the
    # screen in an inconsistent state. Adding a task is a quick, background
    # capture -- it must never change which collection is displayed.
    create_note(tmp_workspace, "an idea")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("tab")  # tasks -> notes
        await pilot.pause()
        assert app.active == "notes"

        await type_command(app, pilot, "task.followup Call Sam")

        assert app.active == "notes"
        bar = app.screen.query_one(CollectionBar)
        assert "[reverse] Notes [/reverse]" in str(bar.content)

        assert row_titles(app) == ["an idea"]

        tasks, _ = load_tasks(tmp_workspace)
        assert any(t.text == "Call Sam" and t.type == "followup" for t in tasks)
