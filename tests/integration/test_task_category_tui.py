from __future__ import annotations

from endpaper.core.models import Workspace
from endpaper.core.tasks import add_task, set_task_state
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListView, TaskRow
from endpaper.tui.scope_pane import CategoryRow


async def test_todo_is_the_default_category(tmp_workspace: Workspace) -> None:
    add_task(tmp_workspace, "open task")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"
        assert app.task_category == "todo"

        scope_list = app.screen.query_one("#scope-list", ListView)
        highlighted = scope_list.highlighted_child
        assert isinstance(highlighted, CategoryRow)
        assert highlighted.category == "todo"


async def test_toggling_moves_a_task_between_categories(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "buy milk")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert any(isinstance(r, TaskRow) and r.record.id == task.id for r in list_view.children)

        await pilot.press("space")
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert not any(
            isinstance(r, TaskRow) and r.record.id == task.id for r in list_view.children
        )

        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert any(isinstance(r, TaskRow) and r.record.id == task.id for r in list_view.children)


async def test_preview_pane_stays_blank_for_tasks(tmp_workspace: Workspace) -> None:
    from textual.widgets import Markdown

    add_task(tmp_workspace, "buy milk")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        preview = app.screen.query_one("#preview", Markdown)
        assert str(preview._markdown or "") == ""  # type: ignore[attr-defined]

        await pilot.press("j")
        await pilot.pause()
        preview = app.screen.query_one("#preview", Markdown)
        assert str(preview._markdown or "") == ""  # type: ignore[attr-defined]


async def test_creating_a_task_from_done_returns_to_todo(tmp_workspace: Workspace) -> None:
    existing = add_task(tmp_workspace, "existing done task")
    set_task_state(tmp_workspace, existing.id, done=True)  # type: ignore[arg-type]

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        assert app.task_category == "done"

        await pilot.press("l")
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        for ch in "task a fresh one":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()

        assert app.task_category == "todo"
        list_view = app.screen.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        assert isinstance(highlighted, TaskRow)
        assert highlighted.record.text == "a fresh one"
