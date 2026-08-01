from __future__ import annotations

from endpaper.core.models import Workspace
from endpaper.core.tasks import add_task, set_task_state
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListView, TaskRow
from endpaper.tui.scope_pane import CategoryRow
from tests.helpers import list_view, task_rows, type_command


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
    task = add_task(tmp_workspace, "buy milk", type="errand", tags=("home",))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert any(r.record.id == task.id for r in task_rows(app))

        await pilot.press("space")
        await pilot.pause()

        # The TUI's toggle bridges to the same core write the CLI uses, and
        # must preserve the fields already on the line.
        text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
        assert "[x]" in text
        assert "type:errand" in text
        assert "tags:home" in text

        # FR-020: it moved out of To-Do (the default category)...
        assert not any(r.record.id == task.id for r in task_rows(app))

        # ...and into Done.
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        done_rows = task_rows(app)
        assert len(done_rows) == 1
        assert done_rows[0].record.id == task.id
        assert done_rows[0].record.done is True


async def test_preview_pane_renders_the_highlighted_task(tmp_workspace: Workspace) -> None:
    # This feature (007) gives tasks a preview -- see test_task_body_tui.py for
    # the body-rendering contract itself. This test guards the category-pane
    # interaction: moving within the task list keeps the preview in sync with
    # whichever task row is highlighted, and never carries over stale content.
    from textual.widgets import Markdown

    add_task(tmp_workspace, "buy milk")
    add_task(tmp_workspace, "call the vendor")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        preview = app.screen.query_one("#preview", Markdown)
        assert "buy milk" in str(preview._markdown or "")  # type: ignore[attr-defined]

        await pilot.press("j")
        await pilot.pause()
        preview = app.screen.query_one("#preview", Markdown)
        rendered = str(preview._markdown or "")  # type: ignore[attr-defined]
        assert "call the vendor" in rendered
        assert "buy milk" not in rendered


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
        assert len(task_rows(app)) == 1

        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        assert app.task_category == "done"
        assert len(task_rows(app)) == 1

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

        assert len(task_rows(app)) == 1


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
        await type_command(app, pilot, "task a fresh one")

        assert app.task_category == "todo"
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, TaskRow)
        assert highlighted.record.text == "a fresh one"
