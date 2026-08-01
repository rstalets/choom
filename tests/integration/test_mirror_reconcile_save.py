from __future__ import annotations

from textual.widgets import TextArea

from endpaper.core.meetings import create_meeting
from endpaper.core.mirrors import capture_task
from endpaper.core.models import Workspace
from endpaper.core.tasks import load_tasks
from endpaper.tui.app import EndpaperApp
from tests.helpers import open_edit


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


async def test_ticking_a_mirror_and_saving_marks_the_task_done(tmp_workspace: Workspace) -> None:
    task_id = _seed_mirror(tmp_workspace)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        _flip_checkbox(editor, done=True)
        await pilot.press("ctrl+o")
        await pilot.pause()

        tasks, _warnings = load_tasks(tmp_workspace)
        assert next(t for t in tasks if t.id == task_id).done is True


async def test_unticking_and_saving_reopens_the_task(tmp_workspace: Workspace) -> None:
    task_id = _seed_mirror(tmp_workspace)
    from endpaper.core.tasks import set_task_state

    set_task_state(tmp_workspace, task_id, done=True)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        # The mirror was reconciled to [x] on open (the task is done); untick it.
        assert "- [x] [call Terry]" in editor.text

        _flip_checkbox(editor, done=False)
        await pilot.press("ctrl+o")
        await pilot.pause()

        tasks, _warnings = load_tasks(tmp_workspace)
        assert next(t for t in tasks if t.id == task_id).done is False


async def test_saving_with_no_mirror_change_writes_nothing_to_tasks_md(
    tmp_workspace: Workspace,
) -> None:
    _seed_mirror(tmp_workspace)
    tasks_mtime_before = tmp_workspace.tasks_file.stat().st_mtime_ns

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = editor.text + "\nan unrelated line\n"
        await pilot.press("ctrl+o")
        await pilot.pause()

    assert tmp_workspace.tasks_file.stat().st_mtime_ns == tasks_mtime_before


async def test_a_tasks_md_write_does_not_cascade_back_into_the_document(
    tmp_workspace: Workspace,
) -> None:
    task_id = _seed_mirror(tmp_workspace)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        meeting_path = screen.target.display_path
        mtime_before_save = meeting_path.stat().st_mtime_ns

        _flip_checkbox(editor, done=True)
        await pilot.press("ctrl+o")
        await pilot.pause()

        # The document was written exactly once by this save (the mirror tick
        # the user made); tasks.md's own write from reconciliation never
        # triggers a second write back into the document that supplied it.
        mtime_after_save = meeting_path.stat().st_mtime_ns
        assert mtime_after_save != mtime_before_save

        tasks, _warnings = load_tasks(tmp_workspace)
        assert next(t for t in tasks if t.id == task_id).done is True

        mtime_settled = meeting_path.stat().st_mtime_ns
        await pilot.pause()
        assert meeting_path.stat().st_mtime_ns == mtime_settled
