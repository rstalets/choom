from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

from endpaper.cli.main import main
from endpaper.core.meetings import create_meeting
from endpaper.core.mirrors import capture_task, propagate_to_documents
from endpaper.core.models import Workspace
from endpaper.core.tasks import add_task, load_tasks
from endpaper.core.workspace import find_workspace
from endpaper.tui.app import EndpaperApp
from tests.helpers import to_collection

_UPDATED = re.compile(r"^updated: (.+)$", re.MULTILINE)


def _capture(tmp_workspace: Workspace) -> tuple[str, Path]:
    """Capture a task and actually leave its mirror in the document -- what the
    editor's `/task` gesture does, but `capture_task` itself deliberately does
    not, since only the caller knows whether the buffer is dirty."""
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    text = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(text + line + "\n", encoding="utf-8")
    return task.id, meeting.path


# --- T029: completing propagates, parametrized across CLI and TUI --------------


def test_cli_task_done_splices_the_mirror_and_leaves_updated_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    workspace = find_workspace(tmp_path)

    task_id, meeting_path = _capture(workspace)
    before_updated = _UPDATED.search(meeting_path.read_text(encoding="utf-8"))
    assert before_updated is not None

    exit_code = main(["task", "done", task_id])
    capsys.readouterr()
    assert exit_code == 0

    text_after = meeting_path.read_text(encoding="utf-8")
    assert "- [x] [call Terry]" in text_after
    after_updated = _UPDATED.search(text_after)
    assert after_updated is not None
    assert after_updated.group(1) == before_updated.group(1)

    # tasks.md was written first, and holds the new state.
    tasks_text = workspace.tasks_file.read_text(encoding="utf-8")
    assert f"- [x] call Terry <!-- id:{task_id}" in tasks_text


async def test_tui_space_splices_the_mirror_and_leaves_updated_unchanged(
    tmp_workspace: Workspace,
) -> None:
    task_id, meeting_path = _capture(tmp_workspace)
    before_updated = _UPDATED.search(meeting_path.read_text(encoding="utf-8"))
    assert before_updated is not None

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "tasks")
        await pilot.press("space")
        await pilot.pause()

        text_after = meeting_path.read_text(encoding="utf-8")
        assert "- [x] [call Terry]" in text_after
        after_updated = _UPDATED.search(text_after)
        assert after_updated is not None
        assert after_updated.group(1) == before_updated.group(1)

        tasks, _warnings = load_tasks(tmp_workspace)
        assert next(t for t in tasks if t.id == task_id).done is True


# --- T030: a reworded, reindented mirror is still found and flipped ------------


def test_a_reworded_and_reindented_mirror_is_still_found_by_id(
    tmp_workspace: Workspace,
) -> None:
    task_id, meeting_path = _capture(tmp_workspace)

    text = meeting_path.read_text(encoding="utf-8")
    text = text.replace("[call Terry]", "[ring Terry instead, since he moved teams]")
    text = text.replace("- [ ] [ring Terry", "  - [ ] [ring Terry")
    meeting_path.write_text(text, encoding="utf-8")

    from endpaper.core.tasks import set_task_state

    set_task_state(tmp_workspace, task_id, done=True)
    written, _warnings = propagate_to_documents(
        tmp_workspace, next(t for t in load_tasks(tmp_workspace)[0] if t.id == task_id)
    )
    assert meeting_path in written

    after = meeting_path.read_text(encoding="utf-8")
    assert "  - [x] [ring Terry instead, since he moved teams]" in after


# --- T031: a missing/unwritable document warns but does not block the toggle ---


def test_missing_document_produces_a_warning_but_tasks_md_still_updates(
    tmp_workspace: Workspace,
) -> None:
    task_id, meeting_path = _capture(tmp_workspace)
    meeting_path.unlink()

    from endpaper.core.tasks import set_task_state

    task = set_task_state(tmp_workspace, task_id, done=True)
    written, warnings = propagate_to_documents(tmp_workspace, task)

    assert written == ()
    assert len(warnings) == 1
    assert task.done is True

    tasks, _warnings = load_tasks(tmp_workspace)
    assert next(t for t in tasks if t.id == task_id).done is True


def test_unwritable_document_warns_and_does_not_reverse_the_toggle(
    tmp_workspace: Workspace,
) -> None:
    # The atomic writer replaces via a same-directory temp file, which needs
    # write permission on the *directory*, not the target file's own bits --
    # so the directory, not the file, is what has to be locked down here.
    task_id, meeting_path = _capture(tmp_workspace)
    directory = meeting_path.parent
    original_mode = directory.stat().st_mode
    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        from endpaper.core.tasks import set_task_state

        task = set_task_state(tmp_workspace, task_id, done=True)
        _written, warnings = propagate_to_documents(tmp_workspace, task)
        assert len(warnings) == 1

        tasks, _warnings = load_tasks(tmp_workspace)
        assert next(t for t in tasks if t.id == task_id).done is True
    finally:
        directory.chmod(original_mode)


# --- T032: a task with no links does no document work at all -------------------


def test_task_with_no_links_reads_no_document(
    tmp_workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = add_task(tmp_workspace, "buy milk")
    assert task.links == ()

    from endpaper.core import mirrors as mirrors_module

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("load_for_edit must not be called for a task with no links")

    monkeypatch.setattr(mirrors_module, "load_for_edit", _boom)

    written, warnings = propagate_to_documents(tmp_workspace, task)
    assert written == ()
    assert warnings == ()
