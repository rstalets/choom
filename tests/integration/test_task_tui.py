from __future__ import annotations

from endpaper.core.meetings import create_meeting, scan_meetings
from endpaper.core.models import Workspace
from endpaper.core.tasks import add_task, set_task_state
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListView, TaskRow
from endpaper.tui.status_bar import StatusBar


async def _type(pilot, text: str) -> None:  # type: ignore[no-untyped-def]
    for ch in text:
        await pilot.press("space" if ch == " " else ch)


async def test_command_bar_creates_task_and_lands_on_tasks_selected(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "task.followup send the vendor comparison #procurement")
        await pilot.press("enter")
        await pilot.pause()

        assert app.active == "tasks"
        list_view = app.screen.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        assert isinstance(highlighted, TaskRow)
        assert highlighted.record.text == "send the vendor comparison"
        assert highlighted.record.type == "followup"
        assert highlighted.record.tags == ("procurement",)


async def test_bare_task_command_shows_error(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "task")
        await pilot.press("enter")
        await pilot.pause()

        status = app.screen.query_one(StatusBar)
        assert "needs a description" in str(status.content)


async def test_space_toggles_task_and_moves_it_to_done(tmp_workspace: Workspace) -> None:
    add_task(tmp_workspace, "buy milk", type="errand", tags=("home",))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert isinstance(list_view.highlighted_child, TaskRow)

        await pilot.press("space")
        await pilot.pause()

        text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
        assert "[x]" in text
        assert "type:errand" in text
        assert "tags:home" in text

        # FR-020: it moved out of To-Do (the default category)...
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert not any(
            isinstance(r, TaskRow) and r.record.text == "buy milk" for r in list_view.children
        )

        # ...and into Done.
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        done_rows = [r for r in list_view.children if isinstance(r, TaskRow)]
        assert len(done_rows) == 1
        assert done_rows[0].record.text == "buy milk"
        assert done_rows[0].record.done is True


async def test_done_category_lists_only_completed_and_survives_collection_switch(
    tmp_workspace: Workspace,
) -> None:
    add_task(tmp_workspace, "open task")
    done_task = add_task(tmp_workspace, "done task")
    set_task_state(tmp_workspace, done_task.id, done=True)  # type: ignore[arg-type]

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"
        assert app.task_category == "todo"

        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len([r for r in list_view.children if isinstance(r, TaskRow)]) == 1

        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        assert app.task_category == "done"
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len([r for r in list_view.children if isinstance(r, TaskRow)]) == 1

        # Switching away and back resets to To-Do (FR-018).
        await pilot.press("l")
        await pilot.pause()
        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        assert app.active == "meetings"
        await pilot.press("tab")  # meetings -> tasks, wrapping
        await pilot.pause()
        assert app.active == "tasks"
        assert app.task_category == "todo"

        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len([r for r in list_view.children if isinstance(r, TaskRow)]) == 1


async def test_space_is_noop_on_meetings_and_notes(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = EndpaperApp(tmp_workspace)
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
    app = EndpaperApp(tmp_workspace)
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
