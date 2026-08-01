"""Integration tests for the workspace changing while the app is running, made
by a process other than the running app -- most importantly an AI assistant
sharing the same workspace (010-read-on-load, US1).

`test_external_edits.py` is a different concern: foreign formatting written to
a file *before* the app starts, then round-tripped through the editor. This
module covers a change landing *while the app is already running*, observed
purely by navigating -- created, deleted, rewritten, or completed by a
separate call into `choom.core`, never through the running app's own screens.
"""

from __future__ import annotations

import re
from datetime import date

from textual.widgets import Markdown, TextArea

from choom.core.meetings import create_meeting
from choom.core.mirrors import capture_task
from choom.core.models import Workspace
from choom.core.tasks import add_task
from choom.tui.app import ChoomApp
from choom.tui.status_bar import StatusBar
from tests.helpers import (
    complete_task_out_of_process,
    create_document_out_of_process,
    delete_file_out_of_process,
    open_edit,
    row_titles,
    task_rows,
    to_collection,
    type_command,
    write_malformed_document_out_of_process,
)

# --- T003: the four mutation shapes, each observed after navigating away and back --


async def test_document_created_out_of_process_appears_after_navigating_back(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Existing meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert row_titles(app) == ["Existing meeting"]

        create_document_out_of_process(tmp_workspace, "meetings", "Assistant wrote this")

        await to_collection(app, pilot, "notes")
        await to_collection(app, pilot, "meetings")
        assert sorted(row_titles(app)) == ["Assistant wrote this", "Existing meeting"]


async def test_document_deleted_out_of_process_disappears_after_navigating_back(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Existing meeting")
    create_meeting(tmp_workspace, "Another meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert len(row_titles(app)) == 2

        delete_file_out_of_process(meeting.path)

        await to_collection(app, pilot, "notes")
        await to_collection(app, pilot, "meetings")
        assert row_titles(app) == ["Another meeting"]


async def test_document_body_and_title_rewritten_out_of_process_shows_current_content(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Old title")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert row_titles(app) == ["Old title"]

        text = meeting.path.read_text(encoding="utf-8")
        text = re.sub(r"^title: .*$", 'title: "New title"', text, flags=re.MULTILINE)
        meeting.path.write_text(text + "New body written elsewhere.\n", encoding="utf-8")

        await to_collection(app, pilot, "notes")
        await to_collection(app, pilot, "meetings")
        assert row_titles(app) == ["New title"]


async def test_task_completed_out_of_process_shows_done_after_navigating_back(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(tmp_workspace, "Follow up on the thing")
    assert task.id is not None

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert any(r.record.id == task.id and not r.record.done for r in task_rows(app))

        complete_task_out_of_process(tmp_workspace, task.id)

        # Leave the view and return without touching collection or category --
        # the help screen push/dismiss round trip exercises ScreenSuspend/Resume.
        await type_command(app, pilot, "help")
        await pilot.press("escape")
        await pilot.pause()

        # Still scoped to To-Do: a done task is filtered out of that category.
        assert not any(r.record.id == task.id for r in task_rows(app))

        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        done_row = next(r for r in task_rows(app) if r.record.id == task.id)
        assert done_row.record.done is True


# --- T004: a malformed file degrades on every read, never just the first ------


async def test_malformed_document_written_while_running_is_skipped_with_a_current_warning_count(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Good meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        status = app.screen.query_one(StatusBar)
        assert "warning" not in str(status.content)

        broken_dir = tmp_workspace.meetings_dir / f"{date.today():%Y/%m}"
        write_malformed_document_out_of_process(broken_dir / "broken.md")

        await to_collection(app, pilot, "notes")
        await to_collection(app, pilot, "meetings")

        # The rest of the list still renders...
        assert row_titles(app) == ["Good meeting"]
        # ...and the warning count describes the workspace as it is now, not
        # the zero warnings that were true at mount.
        status = app.screen.query_one(StatusBar)
        assert "1 warning" in str(status.content)


# --- T005: the preview's read-on-open, and a checkbox tick reaching Tasks -----


async def test_preview_opened_after_out_of_process_rewrite_shows_current_content(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Original title")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        text = meeting.path.read_text(encoding="utf-8")
        text = re.sub(r"^title: .*$", 'title: "Rewritten title"', text, flags=re.MULTILINE)
        meeting.path.write_text(text, encoding="utf-8")

        await pilot.press("enter")
        await pilot.pause()

        preview = app.screen.query_one("#full-preview", Markdown)
        rendered = str(preview._markdown or "")  # type: ignore[attr-defined]
        assert "Rewritten title" in rendered
        assert "Original title" not in rendered


def _seed_mirror(tmp_workspace: Workspace) -> str:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    text = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(text + line + "\n", encoding="utf-8")
    return task.id


def _flip_checkbox(editor: TextArea, *, done: bool) -> None:
    lines = editor.text.splitlines()
    line_index = next(i for i, line in enumerate(lines) if line.startswith("- ["))
    lines[line_index] = lines[line_index].replace(
        "- [x] " if not done else "- [ ] ",
        "- [x] " if done else "- [ ] ",
    )
    editor.text = "\n".join(lines) + ("\n" if editor.text.endswith("\n") else "")


async def test_ticking_a_mirror_in_the_editor_shows_done_in_tasks_with_no_refresh_call(
    tmp_workspace: Workspace,
) -> None:
    """FR-006, SC-007, contract C2: the task list picks up the tick from
    `ListScreen.on_screen_resume` reading fresh, not from a writer telling it
    what changed -- there is no refresh call to wire (verified by the site-count
    grep in T038)."""
    task_id = _seed_mirror(tmp_workspace)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        _flip_checkbox(editor, done=True)
        await pilot.press("ctrl+o")
        await pilot.pause()

        await pilot.press("escape")  # editor -> preview
        await pilot.pause()
        await pilot.press("escape")  # preview -> list
        await pilot.pause()

        await to_collection(app, pilot, "tasks")  # lands on To-Do, the default
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        rows = task_rows(app)
        assert next(r for r in rows if r.record.id == task_id).record.done is True
