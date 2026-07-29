from __future__ import annotations

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.tasks import add_task
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


async def test_space_toggles_checkbox_and_preserves_metadata(tmp_workspace: Workspace) -> None:
    add_task(tmp_workspace, "buy milk", type="errand", tags=("home",))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("left")
        await pilot.pause()
        await pilot.press("j", "j")  # tasks is the third menu row
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()

        assert app.active == "tasks"
        # Show completed too, so the row stays visible once toggled -- otherwise
        # the default open-only filter would make the toggled row disappear, and
        # "selection kept on the toggled task" only makes sense while it's shown.
        await pilot.press("a")
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        selected_id = list_view.highlighted_child.record.id  # type: ignore[union-attr]

        await pilot.press("space")
        await pilot.pause()

        text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
        assert "[x]" in text
        assert "type:errand" in text
        assert "tags:home" in text

        list_view = app.screen.query_one("#meeting-list", ListView)
        assert list_view.highlighted_child.record.id == selected_id  # type: ignore[union-attr]
        assert list_view.highlighted_child.record.done is True  # type: ignore[union-attr]


async def test_a_reveals_and_hides_completed_and_survives_collection_switch(
    tmp_workspace: Workspace,
) -> None:
    add_task(tmp_workspace, "open task")
    done_task = add_task(tmp_workspace, "done task")
    from endpaper.core.tasks import set_task_state

    set_task_state(tmp_workspace, done_task.id, done=True)  # type: ignore[arg-type]

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("left")
        await pilot.pause()
        await pilot.press("j", "j")
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len([r for r in list_view.children if isinstance(r, TaskRow)]) == 1

        await pilot.press("a")
        await pilot.pause()
        assert len([r for r in list_view.children if isinstance(r, TaskRow)]) == 2
        assert app.show_done is True

        # Survives switching away and back.
        await pilot.press("left")
        await pilot.pause()
        await pilot.press("k", "k")
        await pilot.pause()
        assert app.active == "meetings"
        await pilot.press("j", "j")
        await pilot.pause()
        assert app.active == "tasks"
        assert app.show_done is True

        await pilot.press("right")
        await pilot.press("a")
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len([r for r in list_view.children if isinstance(r, TaskRow)]) == 1


async def test_space_and_a_noop_on_meetings_and_notes(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "meetings"

        await pilot.press("space")
        await pilot.press("a")
        await pilot.pause()

        assert app.active == "meetings"
        assert len(app.meetings) == 1


async def test_footer_advertises_space_and_a_only_on_tasks(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "meetings"
        status = app.screen.query_one(StatusBar)
        meetings_text = str(status.content)
        assert "space" not in meetings_text
        assert " a " not in meetings_text

        await pilot.press("left")
        await pilot.pause()
        await pilot.press("j", "j")
        await pilot.pause()
        assert app.active == "tasks"
        tasks_text = str(app.screen.query_one(StatusBar).content)
        assert "space" in tasks_text
        assert "a all" in tasks_text
