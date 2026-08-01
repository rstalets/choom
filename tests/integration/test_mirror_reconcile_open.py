from __future__ import annotations

from textual.widgets import TextArea

from choom.core.meetings import create_meeting
from choom.core.mirrors import capture_task
from choom.core.models import Workspace
from choom.core.notes import create_note
from choom.core.tasks import set_task_state
from choom.tui.app import ChoomApp
from tests.helpers import open_edit


def _seed_mirror(tmp_workspace: Workspace, *, done_on_disk: bool = False) -> tuple[str, str]:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    text = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(text + line + "\n", encoding="utf-8")
    if done_on_disk:
        set_task_state(tmp_workspace, task.id, done=True)
    return task.id, line


# --- T048: a task completed outside the app is reflected on open ---------------


async def test_a_task_completed_outside_the_app_is_reflected_on_open(
    tmp_workspace: Workspace,
) -> None:
    _task_id, _line = _seed_mirror(tmp_workspace, done_on_disk=True)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        assert "- [x] [call Terry]" in editor.text


async def test_a_pasted_mirror_reflects_the_tasks_real_state_when_opened(
    tmp_workspace: Workspace,
) -> None:
    task_id, line = _seed_mirror(tmp_workspace, done_on_disk=True)
    note = create_note(tmp_workspace, "scratch")
    text = note.path.read_text(encoding="utf-8")
    note.path.write_text(text + line + "\n", encoding="utf-8")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await open_edit(app, pilot, collection="notes")
        editor = app.screen.query_one("#editor", TextArea)
        assert "- [x] [call Terry]" in editor.text
        assert f"#{task_id}" in editor.text


# --- T049: no correction needed means no write ----------------------------------


async def test_reconciliation_that_changes_nothing_writes_nothing(
    tmp_workspace: Workspace,
) -> None:
    _task_id, _line = _seed_mirror(tmp_workspace, done_on_disk=False)
    meeting_path = next(tmp_workspace.meetings_dir.rglob("*.md"))
    mtime_before = meeting_path.stat().st_mtime_ns

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        assert screen.is_dirty is False
        await pilot.press("escape")
        await pilot.pause()

    assert meeting_path.stat().st_mtime_ns == mtime_before


# --- T050: a correction writes only the one document, unstamped ----------------


async def test_reconciliation_that_changes_something_writes_only_that_document(
    tmp_workspace: Workspace,
) -> None:
    _task_id, _line = _seed_mirror(tmp_workspace, done_on_disk=True)
    meeting_path = next(tmp_workspace.meetings_dir.rglob("*.md"))
    tasks_mtime_before = tmp_workspace.tasks_file.stat().st_mtime_ns
    updated_before = meeting_path.read_text(encoding="utf-8")

    import re

    updated_match_before = re.search(r"^updated: (.+)$", updated_before, re.MULTILINE)
    assert updated_match_before is not None

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await open_edit(app, pilot)

    # tasks.md itself was only read, never written, by reconcile-on-open.
    assert tmp_workspace.tasks_file.stat().st_mtime_ns == tasks_mtime_before

    after = meeting_path.read_text(encoding="utf-8")
    updated_match_after = re.search(r"^updated: (.+)$", after, re.MULTILINE)
    assert updated_match_after is not None
    assert updated_match_after.group(1) == updated_match_before.group(1)
    assert "- [x] [call Terry]" in after
